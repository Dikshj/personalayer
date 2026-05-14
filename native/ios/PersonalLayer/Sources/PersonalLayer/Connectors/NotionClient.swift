import Foundation

struct NotionClient {
    static func search(token: String) async throws -> [RawEvent] {
        let url = URL(string: "https://api.notion.com/v1/search")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("2022-06-28", forHTTPHeaderField: "Notion-Version")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let (data, _) = try await URLSession.shared.data(for: request)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let results = json?["results"] as? [[String: Any]] ?? []
        return results.map { r in
            RawEvent(id: nil, eventType: "notion_page", payload: String(data: try! JSONSerialization.data(withJSONObject: r), encoding: .utf8)!, createdAt: Date(), privacyFiltered: false)
        }
    }
}
