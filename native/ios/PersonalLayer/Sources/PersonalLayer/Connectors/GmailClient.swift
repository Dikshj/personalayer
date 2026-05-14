import Foundation

struct GmailClient {
    static func syncMetadata(token: String) async throws -> [RawEvent] {
        let url = URL(string: "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=100&labelIds=INBOX")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, _) = try await URLSession.shared.data(for: request)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let messages = json?["messages"] as? [[String: Any]] ?? []
        return messages.map { msg in
            RawEvent(id: nil, eventType: "gmail_metadata", payload: String(data: try! JSONSerialization.data(withJSONObject: msg), encoding: .utf8)!, createdAt: Date(), privacyFiltered: false)
        }
    }
}
