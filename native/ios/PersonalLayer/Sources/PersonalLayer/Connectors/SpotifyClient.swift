import Foundation

struct SpotifyClient {
    private static let baseURL = "https://api.spotify.com/v1/me/player/recently-played"

    static func recentlyPlayed(token: String) async throws -> [RawEvent] {
        var allEvents: [RawEvent] = []
        var after = ConnectorCursorStore.load(for: "spotify")

        for _ in 0..<5 {
            var components = URLComponents(string: baseURL)!
            var queryItems = [URLQueryItem(name: "limit", value: "50")]
            if let a = after { queryItems.append(URLQueryItem(name: "after", value: a)) }
            components.queryItems = queryItems

            var request = URLRequest(url: components.url!)
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else { throw ConnectorError.invalidResponse }
            if httpResponse.statusCode == 429, let retryAfter = httpResponse.value(forHTTPHeaderField: "Retry-After"), let seconds = Int(retryAfter) {
                try await Task.sleep(nanoseconds: UInt64(seconds) * 1_000_000_000)
                continue
            }
            guard httpResponse.statusCode == 200 else {
                throw ConnectorError.apiError(status: httpResponse.statusCode, message: String(data: data, encoding: .utf8) ?? "")
            }
            guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let items = json["items"] as? [[String: Any]] else { break }

            allEvents.append(contentsOf: items.map { item in
                let payload = (try? JSONSerialization.data(withJSONObject: item)) ?? Data()
                return RawEvent(id: nil, eventType: "spotify_play", payload: String(data: payload, encoding: .utf8) ?? "{}", createdAt: Date(), privacyFiltered: false, connectorType: "spotify")
            })

            if let cursors = json["cursors"] as? [String: String],
               let nextAfter = cursors["after"] {
                after = nextAfter
                ConnectorCursorStore.save(cursor: nextAfter, for: "spotify")
            } else {
                break
            }
        }

        ConnectorCursorStore.saveTimestamp(for: "spotify")
        return allEvents
    }
}
