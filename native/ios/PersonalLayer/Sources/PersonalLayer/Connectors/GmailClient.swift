import Foundation

/// Gmail API client with incremental sync and rate limiting.
actor GmailClient {
    private let baseURL = "https://gmail.googleapis.com/gmail/v1"
    private var lastRequestTime: Date = .distantPast
    private let minInterval: TimeInterval = 0.1  // 10 req/sec max
    private var retryCount = 0
    private let maxRetries = 3

    /// Fetch message metadata since last sync.
    func syncMetadata(accessToken: String, cursorStore: ConnectorCursorStore) async throws -> [GmailMessage] {
        let after = cursorStore.loadCursor("gmail") ?? "0"
        let query = after == "0" ? "in:inbox" : "after:\(after)"

        let url = URL(string: "\(baseURL)/users/me/messages?q=\(query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")&maxResults=100")!
        let data = try await fetch(url: url, accessToken: accessToken)

        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let messages = json["messages"] as? [[String: Any]] else {
            throw ConnectorError.invalidResponse
        }

        var result: [GmailMessage] = []
        for msg in messages {
            if let id = msg["id"] as? String {
                let detailData = try await fetchMessageDetail(id: id, accessToken: accessToken)
                result.append(detailData)
            }
        }

        // Update cursor to newest message internalDate
        if let newest = result.last {
            cursorStore.saveCursor("gmail", newest.internalDate)
        }

        return result
    }

    private func fetchMessageDetail(id: String, accessToken: String) async throws -> GmailMessage {
        let url = URL(string: "\(baseURL)/users/me/messages/\(id)?format=metadata&metadataHeaders=Subject&metadataHeaders=From")!
        let data = try await fetch(url: url, accessToken: accessToken)
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw ConnectorError.invalidResponse
        }
        return GmailMessage(
            id: id,
            threadId: json["threadId"] as? String ?? "",
            labelIds: json["labelIds"] as? [String] ?? [],
            snippet: json["snippet"] as? String ?? "",
            internalDate: json["internalDate"] as? String ?? "\(Int(Date().timeIntervalSince1970 * 1000))"
        )
    }

    private func fetch(url: URL, accessToken: String) async throws -> Data {
        // Rate limiting
        let elapsed = Date().timeIntervalSince(lastRequestTime)
        if elapsed < minInterval {
            try await Task.sleep(nanoseconds: UInt64((minInterval - elapsed) * 1_000_000_000))
        }

        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        let (data, response) = try await URLSession.shared.data(for: request)
        lastRequestTime = Date()

        guard let httpResponse = response as? HTTPURLResponse else {
            throw ConnectorError.invalidResponse
        }

        if httpResponse.statusCode == 429 {
            let retryAfter = Int(httpResponse.value(forHTTPHeaderField: "Retry-After") ?? "60") ?? 60
            if retryCount < maxRetries {
                retryCount += 1
                try await Task.sleep(nanoseconds: UInt64(retryAfter * 1_000_000_000))
                return try await fetch(url: url, accessToken: accessToken)
            }
            throw ConnectorError.rate_limited(retryAfter: retryAfter)
        }

        retryCount = 0

        if httpResponse.statusCode == 401 {
            throw ConnectorError.unauthorized
        }
        guard httpResponse.statusCode == 200 else {
            throw ConnectorError.api_error(status: httpResponse.statusCode,
                message: String(data: data, encoding: .utf8) ?? "Unknown")
        }

        return data
    }
}

struct GmailMessage: Codable {
    let id: String
    let threadId: String
    let labelIds: [String]
    let snippet: String
    let internalDate: String
}
