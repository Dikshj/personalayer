import Foundation

struct SpotifyClient {
    static func recentlyPlayed(token: String) async throws -> [RawEvent] {
        let url = URL(string: "https://api.spotify.com/v1/me/player/recently-played?limit=50")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, _) = try await URLSession.shared.data(for: request)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let items = json?["items"] as? [[String: Any]] ?? []
        return items.map { item in
            RawEvent(id: nil, eventType: "spotify_play", payload: String(data: try! JSONSerialization.data(withJSONObject: item), encoding: .utf8)!, createdAt: Date(), privacyFiltered: false)
        }
    }
}
