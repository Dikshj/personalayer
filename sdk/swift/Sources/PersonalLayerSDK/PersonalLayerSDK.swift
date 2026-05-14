import Foundation

public final class PersonalLayerSDK {
    public static let shared = PersonalLayerSDK()
    private init() {}

    public func getBundle() async throws -> [String: Any] {
        let url = URL(string: "http://127.0.0.1:7432/v1/context/bundle")!
        let (data, _) = try await URLSession.shared.data(from: url)
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw SDKError.invalidResponse
        }
        return json
    }

    public func track(eventType: String, payload: [String: Any]) async throws {
        let url = URL(string: "http://127.0.0.1:7432/v1/ingest/extension")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["event_type": eventType, "payload": payload])
        _ = try await URLSession.shared.data(for: request)
    }
}

public enum SDKError: Error {
    case invalidResponse
}
