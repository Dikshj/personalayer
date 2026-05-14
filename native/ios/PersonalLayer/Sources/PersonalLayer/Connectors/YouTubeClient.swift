import Foundation

struct YouTubeClient {
    static func metadata(token: String) async throws -> [RawEvent] {
        let url = URL(string: "https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails&chart=mostPopular&maxResults=10&mine=true")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, _) = try await URLSession.shared.data(for: request)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let items = json?["items"] as? [[String: Any]] ?? []
        return items.map { item in
            RawEvent(id: nil, eventType: "youtube_metadata", payload: String(data: try! JSONSerialization.data(withJSONObject: item), encoding: .utf8)!, createdAt: Date(), privacyFiltered: false)
        }
    }
}
