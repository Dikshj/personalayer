import Foundation

/// Google Fit API client for aggregate data.
actor GoogleFitClient {
    private let baseURL = "https://www.googleapis.com/fitness/v1"
    private var lastRequestTime: Date = .distantPast
    private let minInterval: TimeInterval = 0.1

    func syncAggregate(accessToken: String, cursorStore: ConnectorCursorStore) async throws -> [FitDataPoint] {
        let now = Int(Date().timeIntervalSince1970 * 1_000_000_000)
        let dayAgo = now - 86_400_000_000_000  // 24 hours in nanoseconds

        let body: [String: Any] = [
            "aggregateBy": [
                ["dataTypeName": "com.google.step_count.delta"],
                ["dataTypeName": "com.google.heart_rate.bpm"]
            ],
            "bucketByTime": ["durationMillis": 86400000],
            "startTimeMillis": "\(dayAgo / 1_000_000)",
            "endTimeMillis": "\(now / 1_000_000)"
        ]

        let url = URL(string: "\(baseURL)/users/me/dataset:aggregate")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw ConnectorError.invalidResponse
        }

        if httpResponse.statusCode == 429 {
            let retryAfter = Int(httpResponse.value(forHTTPHeaderField: "Retry-After") ?? "60") ?? 60
            try await Task.sleep(nanoseconds: UInt64(retryAfter * 1_000_000_000))
            return try await syncAggregate(accessToken: accessToken, cursorStore: cursorStore)
        }

        if httpResponse.statusCode == 401 {
            throw ConnectorError.unauthorized
        }
        guard httpResponse.statusCode == 200 else {
            throw ConnectorError.api_error(status: httpResponse.statusCode,
                message: String(data: data, encoding: .utf8) ?? "")
        }

        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let buckets = json["bucket"] as? [[String: Any]] else {
            throw ConnectorError.invalidResponse
        }

        var points: [FitDataPoint] = []
        for bucket in buckets {
            if let dataset = bucket["dataset"] as? [[String: Any]],
               let first = dataset.first,
               let point = first["point"] as? [[String: Any]],
               let firstPoint = point.first,
               let value = (firstPoint["value"] as? [[String: Any]])?.first,
               let intVal = value["intVal"] as? Int {
                points.append(FitDataPoint(
                    dataTypeName: first["dataSourceId"] as? String ?? "unknown",
                    value: intVal,
                    startTime: bucket["startTimeMillis"] as? String ?? ""
                ))
            }
        }

        cursorStore.saveCursor("google_fit", "\(now)")
        return points
    }
}

struct FitDataPoint: Codable {
    let dataTypeName: String
    let value: Int
    let startTime: String
}
