import Foundation

struct CalendarClient {
    static func sync7DayWindow(token: String) async throws -> [RawEvent] {
        let now = Date()
        let weekAgo = Calendar.current.date(byAdding: .day, value: -7, to: now)!
        let fmt = ISO8601DateFormatter()
        let timeMin = fmt.string(from: weekAgo)
        let url = URL(string: "https://www.googleapis.com/calendar/v3/calendars/primary/events?timeMin=\(timeMin)&maxResults=100")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, _) = try await URLSession.shared.data(for: request)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let items = json?["items"] as? [[String: Any]] ?? []
        return items.map { item in
            RawEvent(id: nil, eventType: "calendar_event", payload: String(data: try! JSONSerialization.data(withJSONObject: item), encoding: .utf8)!, createdAt: Date(), privacyFiltered: false)
        }
    }
}
