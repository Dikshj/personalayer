import Foundation

struct YouTubeClient {
    private static let baseURL = "https://www.googleapis.com/youtube/v3/videos"

    static func metadata(token: String) async throws -> [RawEvent] {
        var allEvents: [RawEvent] = []
        var pageToken: String?

        for _ in 0..<5 {
            var components = URLComponents(string: baseURL)!
            var queryItems = [
                URLQueryItem(name: "part", value: "snippet,contentDetails"),
                URLQueryItem(name: "chart", value: "mostPopular"),
                URLQueryItem(name: "maxResults", value: "50")
            ]
            if let pt = pageToken { queryItems.append(URLQueryItem(name: "pageToken", value: pt)) }
            components.queryItems = queryItems

            var request = URLRequest(url: components.url!)
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw ConnectorError.invalidResponse
            }

            if httpResponse.statusCode == 403,
               let errorBody = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = errorBody["error"] as? [String: Any],
               let errors = error["errors"] as? [[String: Any]],
               let first = errors.first,
               let reason = first["reason"] as? String,
               reason == "quotaExceeded" {
                throw ConnectorError.apiError(status: 403, message: "YouTube API quota exceeded")
            }

            guard httpResponse.statusCode == 200 else {
                throw ConnectorError.apiError(status: httpResponse.statusCode, message: String(data: data, encoding: .utf8) ?? "")
            }

            guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let items = json["items"] as? [[String: Any]] else {
                break
            }

            allEvents.append(contentsOf: items.map { item in
                let payload = (try? JSONSerialization.data(withJSONObject: item)) ?? Data()
                return RawEvent(
                    id: nil,
                    eventType: "youtube_metadata",
                    payload: String(data: payload, encoding: .utf8) ?? "{}",
                    createdAt: Date(),
                    privacyFiltered: false
                )
            })

            pageToken = json["nextPageToken"] as? String
            if pageToken == nil { break }
        }

        return allEvents
    }
}
