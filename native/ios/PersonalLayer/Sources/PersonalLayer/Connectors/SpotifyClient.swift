import Foundation

/// Spotify API client with cursor-based pagination.
actor SpotifyClient {
    private let baseURL = "https://api.spotify.com/v1"
    private var lastRequestTime: Date = .distantPast
    private let minInterval: TimeInterval = 0.05  // 20 req/sec

    func syncRecentlyPlayed(accessToken: String, cursorStore: ConnectorCursorStore) async throws -> [SpotifyTrack] {
        var after = cursorStore.loadCursor("spotify")
        var allTracks: [SpotifyTrack] = []
        var hasMore = true

        while hasMore {
            var urlComponents = URLComponents(string: "\(baseURL)/me/player/recently-played")!
            urlComponents.queryItems = [URLQueryItem(name: "limit", value: "50")]
            if let after = after {
                urlComponents.queryItems?.append(URLQueryItem(name: "after", value: after))
            }

            let data = try await fetch(url: urlComponents.url!, accessToken: accessToken)
            guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let items = json["items"] as? [[String: Any]] else {
                throw ConnectorError.invalidResponse
            }

            for item in items {
                if let track = item["track"] as? [String: Any],
                   let name = track["name"] as? String,
                   let id = track["id"] as? String {
                    allTracks.append(SpotifyTrack(
                        id: id,
                        name: name,
                        playedAt: item["played_at"] as? String ?? ""
                    ))
                }
            }

            // Update cursor from last item
            if let lastItem = items.last,
               let playedAt = lastItem["played_at"] as? String {
                after = playedAt
                cursorStore.saveCursor("spotify", playedAt)
            }

            hasMore = items.count == 50
        }

        return allTracks
    }

    private func fetch(url: URL, accessToken: String) async throws -> Data {
        let elapsed = Date().timeIntervalSince(lastRequestTime)
        if elapsed < minInterval {
            try await Task.sleep(nanoseconds: UInt64((minInterval - elapsed) * 1_000_000_000))
        }

        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await URLSession.shared.data(for: request)
        lastRequestTime = Date()

        guard let httpResponse = response as? HTTPURLResponse else {
            throw ConnectorError.invalidResponse
        }

        if httpResponse.statusCode == 429 {
            let retryAfter = Int(httpResponse.value(forHTTPHeaderField: "Retry-After") ?? "60") ?? 60
            try await Task.sleep(nanoseconds: UInt64(retryAfter * 1_000_000_000))
            return try await fetch(url: url, accessToken: accessToken)
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

struct SpotifyTrack: Codable {
    let id: String
    let name: String
    let playedAt: String
}
