import Foundation

/// Google Calendar API client with 7-day window sync.
actor CalendarClient {
    private let baseURL = "https://www.googleapis.com/calendar/v3"
    private var lastRequestTime: Date = .distantPast
    private let minInterval: TimeInterval = 0.1

    /// Sync events from the past 7 days.
    func sync7DayWindow(accessToken: String, cursorStore: ConnectorCursorStore) async throws -> [RawEvent] {
        let calendar = Calendar.current
        let sevenDaysAgo = calendar.date(byAdding: .day, value: -7, to: Date())!
        let timeMin = ISO8601DateFormatter().string(from: sevenDaysAgo)

        var urlComponents = URLComponents(string: "\(baseURL)/calendars/primary/events")!
        urlComponents.queryItems = [
            URLQueryItem(name: "timeMin", value: timeMin),
            URLQueryItem(name: "maxResults", value: "250"),
            URLQueryItem(name: "singleEvents", value: "true"),
            URLQueryItem(name: "orderBy", value: "startTime")
        ]

        let data = try await fetch(url: urlComponents.url!, accessToken: accessToken)
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let items = json["items"] as? [[String: Any]] else {
            throw ConnectorError.invalidResponse
        }

        var events: [RawEvent] = []
        for item in items {
            let start = (item["start"] as? [String: Any])?["dateTime"] as? String
            let summary = item["summary"] as? String ?? "Untitled"
            let id = item["id"] as? String ?? UUID().uuidString
            let payload: [String: Any] = [
                "id": id,
                "summary": summary,
                "start": start ?? "",
                "status": item["status"] as? String ?? "confirmed"
            ]
            events.append(RawEvent(
                id: nil,
                eventType: "calendar_event",
                payload: String(data: try JSONSerialization.data(withJSONObject: payload), encoding: .utf8)!,
                createdAt: Date(),
                privacyFiltered: false,
                connectorType: "calendar"
            ))
        }

        // Cursor = last event start time
        if let lastStart = events.last.map({ (try? JSONSerialization.jsonObject(with: $0.payload.data(using: .utf8)!) as? [String: Any])?["start"] as? String }) {
            cursorStore.saveCursor("calendar", lastStart ?? timeMin)
        }

        return events
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
