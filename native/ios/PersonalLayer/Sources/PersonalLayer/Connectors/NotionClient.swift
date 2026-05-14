import Foundation

struct NotionClient {
    private static let baseURL = "https://api.notion.com/v1/search"
    private static let version = "2022-06-28"

    static func search(token: String) async throws -> [RawEvent] {
        var allEvents: [RawEvent] = []
        var cursor: String?

        for _ in 0..<5 {
            var request = URLRequest(url: URL(string: baseURL)!)
            request.httpMethod = "POST"
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            request.setValue(version, forHTTPHeaderField: "Notion-Version")
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")

            var body: [String: Any] = ["page_size": 100]
            if let startCursor = cursor { body["start_cursor"] = startCursor }
            request.httpBody = try JSONSerialization.data(withJSONObject: body)

            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw ConnectorError.invalidResponse
            }

            if httpResponse.statusCode == 429 {
                let retryAfter = httpResponse.value(forHTTPHeaderField: "Retry-After").flatMap(Int.init) ?? 5
                try await Task.sleep(nanoseconds: UInt64(retryAfter) * 1_000_000_000)
                continue
            }

            guard httpResponse.statusCode == 200 else {
                throw ConnectorError.apiError(status: httpResponse.statusCode, message: String(data: data, encoding: .utf8) ?? "")
            }

            guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let results = json["results"] as? [[String: Any]] else {
                break
            }

            allEvents.append(contentsOf: results.map { r in
                let payload = (try? JSONSerialization.data(withJSONObject: r)) ?? Data()
                return RawEvent(
                    id: nil,
                    eventType: "notion_page",
                    payload: String(data: payload, encoding: .utf8) ?? "{}",
                    createdAt: Date(),
                    privacyFiltered: false
                )
            })

            if let hasMore = json["has_more"] as? Bool, hasMore,
               let nextCursor = json["next_cursor"] as? String {
                cursor = nextCursor
            } else {
                break
            }
        }

        return allEvents
    }
}
