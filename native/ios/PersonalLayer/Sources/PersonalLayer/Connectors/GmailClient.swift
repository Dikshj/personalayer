import Foundation

struct GmailClient {
    private static let baseURL = "https://gmail.googleapis.com/gmail/v1/users/me"
    private static let maxResults = 100

    static func syncMetadata(token: String) async throws -> [RawEvent] {
        var allEvents: [RawEvent] = []
        var pageToken: String?

        for page in 0..<10 { // max 1000 messages
            var components = URLComponents(string: "\(baseURL)/messages")!
            var queryItems = [
                URLQueryItem(name: "maxResults", value: "\(maxResults)"),
                URLQueryItem(name: "labelIds", value: "INBOX")
            ]
            if let pt = pageToken { queryItems.append(URLQueryItem(name: "pageToken", value: pt)) }
            components.queryItems = queryItems

            var request = URLRequest(url: components.url!)
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw ConnectorError.invalidResponse
            }

            if httpResponse.statusCode == 429 {
                // Rate limited — exponential backoff
                try await Task.sleep(nanoseconds: UInt64(pow(2.0, Double(page))) * 1_000_000_000)
                continue
            }

            guard httpResponse.statusCode == 200 else {
                let body = String(data: data, encoding: .utf8) ?? ""
                throw ConnectorError.apiError(status: httpResponse.statusCode, message: body)
            }

            guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let messages = json["messages"] as? [[String: Any]] else {
                break
            }

            let events = messages.map { msg -> RawEvent in
                let payload = (try? JSONSerialization.data(withJSONObject: msg)) ?? Data()
                return RawEvent(
                    id: nil,
                    eventType: "gmail_metadata",
                    payload: String(data: payload, encoding: .utf8) ?? "{}",
                    createdAt: Date(),
                    privacyFiltered: false
                )
            }
            allEvents.append(contentsOf: events)

            pageToken = json["nextPageToken"] as? String
            if pageToken == nil { break }
        }

        return allEvents
    }
}
