import Foundation

struct GoogleFitClient {
    static func aggregateSteps(token: String) async throws -> RawEvent? {
        let now = Int(Date().timeIntervalSince1970 * 1000)
        let dayAgo = now - 86400000
        let body: [String: Any] = [
            "aggregateBy": [["dataTypeName": "com.google.step_count.delta", "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"]],
            "bucketByTime": ["durationMillis": 86400000],
            "startTimeMillis": dayAgo,
            "endTimeMillis": now
        ]
        let url = URL(string: "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, _) = try await URLSession.shared.data(for: request)
        return RawEvent(id: nil, eventType: "google_fit_aggregate", payload: String(data: data, encoding: .utf8)!, createdAt: Date(), privacyFiltered: false)
    }
}
