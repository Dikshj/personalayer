import Foundation

public protocol PersonalLayerClient {
    func getBundle() async throws -> PersonalLayerBundle
    func track(event: TrackEvent) async throws -> Bool
    func isAvailable() async -> Bool
}

public struct PersonalLayerBundle: Codable {
    public let hotContext: [ContextNode]
    public let warmContext: [ContextNode]
    public let coolContext: [ContextNode]
    public let generatedAt: String
    public let version: String

    public struct ContextNode: Codable {
        public let id: String
        public let label: String
        public let strength: Double
    }
}

public struct TrackEvent: Codable {
    public let eventType: String
    public let payload: [String: AnyCodable]

    public init(eventType: String, payload: [String: Any] = [:]) {
        self.eventType = eventType
        self.payload = payload.mapValues { AnyCodable($0) }
    }
}

public actor PersonalLayerSDK: PersonalLayerClient {
    public static let shared = PersonalLayerSDK()

    private let daemonURL: URL
    private let session: URLSession

    public init(daemonURL: URL = URL(string: "http://127.0.0.1:7432")!, session: URLSession = .shared) {
        self.daemonURL = daemonURL
        self.session = session
    }

    public func isAvailable() async -> Bool {
        do {
            let (_, response) = try await session.data(from: daemonURL.appendingPathComponent("v1/context/bundle"))
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    public func getBundle() async throws -> PersonalLayerBundle {
        let (data, response) = try await session.data(from: daemonURL.appendingPathComponent("v1/context/bundle"))
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw SDKError.bundleUnavailable
        }
        return try JSONDecoder().decode(PersonalLayerBundle.self, from: data)
    }

    public func track(event: TrackEvent) async throws -> Bool {
        var request = URLRequest(url: daemonURL.appendingPathComponent("v1/ingest/extension"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(event)
        let (_, response) = try await session.data(for: request)
        return (response as? HTTPURLResponse)?.statusCode == 200
    }
}

public enum SDKError: Error {
    case bundleUnavailable
    case trackFailed
}

// Helper for encoding [String: Any]
public struct AnyCodable: Codable {
    public let value: Any

    public init(_ value: Any) {
        self.value = value
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let string = try? container.decode(String.self) { value = string }
        else if let int = try? container.decode(Int.self) { value = int }
        else if let double = try? container.decode(Double.self) { value = double }
        else if let bool = try? container.decode(Bool.self) { value = bool }
        else if let array = try? container.decode([AnyCodable].self) { value = array.map { $0.value } }
        else if let dict = try? container.decode([String: AnyCodable].self) { value = dict.mapValues { $0.value } }
        else { value = "" }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        if let string = value as? String { try container.encode(string) }
        else if let int = value as? Int { try container.encode(int) }
        else if let double = value as? Double { try container.encode(double) }
        else if let bool = value as? Bool { try container.encode(bool) }
        else if let array = value as? [Any] { try container.encode(array.map { AnyCodable($0) }) }
        else if let dict = value as? [String: Any] { try container.encode(dict.mapValues { AnyCodable($0) }) }
        else { try container.encode("\(value)") }
    }
}
