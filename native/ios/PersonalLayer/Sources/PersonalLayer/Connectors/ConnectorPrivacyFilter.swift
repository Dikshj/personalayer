import Foundation

/// Privacy whitelist per connector type.
/// Only these event fields are retained; everything else is stripped before storage.
enum ConnectorPrivacyFilter {
    static let allowedFields: [String: [String]] = [
        "gmail": ["id", "threadId", "labelIds", "snippet", "internalDate", "historyId"],
        "calendar": ["id", "status", "start", "end", "created", "updated", "recurringEventId"],
        "spotify": ["track", "played_at", "context", "progress_ms"],
        "google_fit": ["bucket", "dataset", "point", "startTimeNanos", "endTimeNanos", "dataTypeName"],
        "notion": ["id", "object", "title", "last_edited_time", "created_time"],
        "youtube": ["videoId", "title", "description", "publishedAt", "channelId", "channelTitle"]
    ]

    static func filter(payload: [String: Any], for connector: String) -> [String: Any] {
        guard let allowed = allowedFields[connector] else {
            // Unknown connector: strip everything except safe metadata
            return [:]
        }
        var filtered: [String: Any] = [:]
        for key in allowed {
            if let value = payload[key] {
                filtered[key] = value
            }
        }
        return filtered
    }

    static func shouldFilterEvent(eventType: String, payload: [String: Any]) -> Bool {
        let blockedPatterns = [
            "password", "secret", "token", "api_key", "credit_card",
            "ssn", "social_security", "private_key"
        ]
        let payloadStr = String(data: (try? JSONSerialization.data(withJSONObject: payload)) ?? Data(), encoding: .utf8) ?? ""
        let lower = payloadStr.lowercased()
        return blockedPatterns.contains { lower.contains($0) }
    }
}
