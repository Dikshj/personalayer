import Foundation

struct SpotifyClient {
    private static let baseURL = "https://api.spotify.com/v1/me/player/recently-played"

    static func recentlyPlayed(token: String) async throws -> [RawEvent] {
        var allEvents: [RawEvent] = []
        var after: String?

        for _ in 0..<5 {
            var components = URLComponents(string: baseURL)!
            var queryItems = [URLQueryItem(name: "limit", value: "50")]
            if let a = after { queryItems.append(URLQueryItem(name: "after", value: a)) }
            components.queryItems = queryItems

            var request = URLRequest(url: components.url!)
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw ConnectorError.invalidResponse
            }

            if httpResponse.statusCode == 429, let retryAfter = httpResponse.value(forHTTPHeaderField: "Retry-After"),
               let seconds = Int(retryAfter) {
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
                return RawEvent(
                    id: nil,
                    eventType: "spotify_play",
                    payload: String(data: payload, encoding: .utf8) ?? "{}",
                    createdAt: Date(),
                    privacyFiltered: false
                )
            })

            if let next = json["next"] as? String, let nextAfter = extractAfter(from: next) {
                after = nextAfter
            } else {
                break
            }
        }

        return allEvents
    }

    private static func extractAfter(from urlString: String) -> String? {
        guard let url = URL(string: urlString),
              let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let items = components.queryItems,
              let after = items.first(where: { $0.name == "after" })?.value else {
            return nil
        }
        return after
    }
}
