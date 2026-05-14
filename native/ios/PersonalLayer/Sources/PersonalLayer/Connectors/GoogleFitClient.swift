import Foundation

struct GoogleFitClient {
    private static let baseURL = "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate"

    static func aggregateSteps(token: String) async throws -> RawEvent? {
        let now = Int(Date().timeIntervalSince1970 * 1000)
        let dayAgo = now - 86400000

        let body: [String: Any] = [
            "aggregateBy": [[
                "dataTypeName": "com.google.step_count.delta",
                "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"
            ]],
            "bucketByTime": ["durationMillis": 86400000],
            "startTimeMillis": dayAgo,
            "endTimeMillis": now
        ]

        var request = URLRequest(url: URL(string: baseURL)!)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw ConnectorError.invalidResponse
        }

        if httpResponse.statusCode == 429 {
            let retryAfter = httpResponse.value(forHTTPHeaderField: "Retry-After").flatMap(Int.init) ?? 5
            try await Task.sleep(nanoseconds: UInt64(retryAfter) * 1_000_000_000)
            return try await aggregateSteps(token: token) // one retry
        }

        guard httpResponse.statusCode == 200 else {
            throw ConnectorError.apiError(status: httpResponse.statusCode, message: String(data: data, encoding: .utf8) ?? "")
        }

        return RawEvent(
            id: nil,
            eventType: "google_fit_aggregate",
            payload: String(data: data, encoding: .utf8) ?? "{}",
            createdAt: Date(),
            privacyFiltered: false
        )
    }
}
