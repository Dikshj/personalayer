import Foundation

/// YouTube Data API client with pageToken pagination.
actor YouTubeClient {
    private let baseURL = "https://www.googleapis.com/youtube/v3"
    private var lastRequestTime: Date = .distantPast
    private let minInterval: TimeInterval = 0.1  // 10 req/sec (quota: 10,000/day)

    func syncActivity(accessToken: String, cursorStore: ConnectorCursorStore) async throws -> [YouTubeVideo] {
        var pageToken = cursorStore.loadCursor("youtube")
        var allVideos: [YouTubeVideo] = []

        for _ in 0..<10 {  // Max 10 pages to stay within quota
            var urlComponents = URLComponents(string: "\(baseURL)/activities")!
            urlComponents.queryItems = [
                URLQueryItem(name: "part", value: "snippet,contentDetails"),
                URLQueryItem(name: "mine", value: "true"),
                URLQueryItem(name: "maxResults", value: "50")
            ]
            if let pageToken = pageToken {
                urlComponents.queryItems?.append(URLQueryItem(name: "pageToken", value: pageToken))
            }

            let data = try await fetch(url: urlComponents.url!, accessToken: accessToken)
            guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let items = json["items"] as? [[String: Any]] else {
                throw ConnectorError.invalidResponse
            }

            for item in items {
                if let snippet = item["snippet"] as? [String: Any],
                   let title = snippet["title"] as? String,
                   let videoId = (item["contentDetails"] as? [String: Any])?["upload"] as? [String: Any]?,
                   let id = videoId?["videoId"] {
                    allVideos.append(YouTubeVideo(
                        id: id as? String ?? "",
                        title: title,
                        publishedAt: snippet["publishedAt"] as? String ?? ""
                    ))
                }
            }

            pageToken = json["nextPageToken"] as? String
            cursorStore.saveCursor("youtube", pageToken ?? "")

            if pageToken == nil { break }
        }

        return allVideos
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

        if httpResponse.statusCode == 429 ||
           (httpResponse.statusCode == 403 && String(data: data, encoding: .utf8)?.contains("quotaExceeded") == true) {
            throw ConnectorError.rate_limited(retryAfter: 3600)  // Wait for quota reset
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

struct YouTubeVideo: Codable {
    let id: String
    let title: String
    let publishedAt: String
}
