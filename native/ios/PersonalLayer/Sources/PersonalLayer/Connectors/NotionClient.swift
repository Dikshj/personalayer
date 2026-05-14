import Foundation

/// Notion API client with start_cursor pagination.
actor NotionClient {
    private let baseURL = "https://api.notion.com/v1"
    private let apiVersion = "2022-06-28"
    private var lastRequestTime: Date = .distantPast
    private let minInterval: TimeInterval = 0.34  // 3 req/sec (Notion rate limit)

    func syncSearch(accessToken: String, cursorStore: ConnectorCursorStore) async throws -> [NotionPage] {
        var startCursor = cursorStore.loadCursor("notion")
        var allPages: [NotionPage] = []

        repeat {
            var body: [String: Any] = ["page_size": 100]
            if let startCursor = startCursor {
                body["start_cursor"] = startCursor
            }

            let data = try await post(path: "/search", accessToken: accessToken, body: body)
            guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let results = json["results"] as? [[String: Any]] else {
                throw ConnectorError.invalidResponse
            }

            for result in results {
                if let id = result["id"] as? String,
                   let properties = result["properties"] as? [String: Any] {
                    let title = ((properties["title"] as? [String: Any])?["title"] as? [[String: Any]])?.first?["plain_text"] as? String ?? ""
                    allPages.append(NotionPage(
                        id: id,
                        title: title,
                        createdTime: result["created_time"] as? String ?? "",
                        lastEditedTime: result["last_edited_time"] as? String ?? ""
                    ))
                }
            }

            startCursor = json["next_cursor"] as? String
            cursorStore.saveCursor("notion", startCursor ?? "")

        } while startCursor != nil

        return allPages
    }

    private func post(path: String, accessToken: String, body: [String: Any]) async throws -> Data {
        let elapsed = Date().timeIntervalSince(lastRequestTime)
        if elapsed < minInterval {
            try await Task.sleep(nanoseconds: UInt64((minInterval - elapsed) * 1_000_000_000))
        }

        let url = URL(string: "\(baseURL)\(path)")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        request.setValue("\(apiVersion)", forHTTPHeaderField: "Notion-Version")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        lastRequestTime = Date()

        guard let httpResponse = response as? HTTPURLResponse else {
            throw ConnectorError.invalidResponse
        }

        if httpResponse.statusCode == 429 {
            let retryAfter = Int(httpResponse.value(forHTTPHeaderField: "Retry-After") ?? "60") ?? 60
            try await Task.sleep(nanoseconds: UInt64(retryAfter * 1_000_000_000))
            return try await post(path: path, accessToken: accessToken, body: body)
        }

        if httpResponse.statusCode == 401 {
            throw ConnectorError.unauthorized
        }
        guard httpResponse.statusCode == 200 else {
            throw ConnectorError.api_error(status: httpResponse.statusCode,
                message: String(data: data, encoding: .utf8) ?? "")
        }

        return data
    }
}

struct NotionPage: Codable {
    let id: String
    let title: String
    let createdTime: String
    let lastEditedTime: String
}
