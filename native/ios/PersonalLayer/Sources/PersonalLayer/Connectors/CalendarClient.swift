import Foundation

struct CalendarClient {
    private static let baseURL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

    static func sync7DayWindow(token: String) async throws -> [RawEvent] {
        let now = Date()
        let weekAgo = Calendar.current.date(byAdding: .day, value: -7, to: now)!
        let fmt = ISO8601DateFormatter()
        let timeMin = fmt.string(from: weekAgo)
        let timeMax = fmt.string(from: now)

        var components = URLComponents(string: baseURL)!
        components.queryItems = [
            URLQueryItem(name: "timeMin", value: timeMin),
            URLQueryItem(name: "timeMax", value: timeMax),
            URLQueryItem(name: "maxResults", value: "250"),
            URLQueryItem(name: "singleEvents", value: "true"),
            URLQueryItem(name: "orderBy", value: "startTime")
        ]

        var request = URLRequest(url: components.url!)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            throw ConnectorError.apiError(status: status, message: String(data: data, encoding: .utf8) ?? "")
        }

        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let items = json["items"] as? [[String: Any]] else {
            return []
        }

        return items.map { item in
            let payload = (try? JSONSerialization.data(withJSONObject: item)) ?? Data()
            return RawEvent(
                id: nil,
                eventType: "calendar_event",
                payload: String(data: payload, encoding: .utf8) ?? "{}",
                createdAt: Date(),
                privacyFiltered: false
            )
        }
    }
}
