import Foundation

/// Native Messaging host for Chrome / Edge / Safari.
/// Reads 4-byte little-endian length-prefixed JSON from stdin,
/// routes internally to LocalServer, and writes responses to stdout.
final class NativeMessagingHost {
    static let shared = NativeMessagingHost()

    private let fileHandle = FileHandle.standardInput
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()
    private var isRunning = false

    func start() {
        isRunning = true
        DispatchQueue.global(qos: .utility).async {
            while self.isRunning {
                do {
                    let message = try self.readMessage()
                    let response = try self.handle(message: message)
                    try self.writeMessage(response)
                } catch {
                    NSLog("PersonalLayer NM error: \(error)")
                    break
                }
            }
        }
    }

    func stop() {
        isRunning = false
    }

    // MARK: - Protocol

    private func readMessage() throws -> [String: Any] {
        let lengthData = try readExactly(4)
        let length = lengthData.withUnsafeBytes { $0.load(as: UInt32.self).littleEndian }
        guard length > 0, length < 1024 * 1024 else {
            throw NativeMessagingError.invalidLength
        }
        let payload = try readExactly(Int(length))
        guard let json = try JSONSerialization.jsonObject(with: payload) as? [String: Any] else {
            throw NativeMessagingError.invalidJSON
        }
        return json
    }

    private func writeMessage(_ message: [String: Any]) throws {
        let data = try JSONSerialization.data(withJSONObject: message)
        var length = UInt32(data.count).littleEndian
        let lengthData = Data(bytes: &length, count: 4)
        FileHandle.standardOutput.write(lengthData)
        FileHandle.standardOutput.write(data)
    }

    private func readExactly(_ count: Int) throws -> Data {
        var buffer = Data()
        while buffer.count < count {
            let chunk = fileHandle.availableData
            if chunk.isEmpty {
                throw NativeMessagingError.eof
            }
            buffer.append(chunk)
        }
        return buffer.prefix(count)
    }

    // MARK: - Routing

    private func handle(message: [String: Any]) -> [String: Any] {
        guard let action = message["action"] as? String else {
            return ["error": "missing action"]
        }
        switch action {
        case "CL_GET_BUNDLE":
            do {
                let bundle = try GRDBDatabase.shared.loadSharedBundle()
                return ["success": true, "bundle": bundle]
            } catch {
                return ["success": false, "error": error.localizedDescription]
            }
        case "CL_TRACK":
            guard let eventType = message["event_type"] as? String,
                  let payload = message["payload"] as? [String: Any] else {
                return ["success": false, "error": "missing event_type or payload"]
            }
            do {
                try GRDBDatabase.shared.insertRawEvent(type: eventType, payload: payload)
                return ["success": true]
            } catch {
                return ["success": false, "error": error.localizedDescription]
            }
        case "CL_IS_AVAILABLE":
            return ["available": true, "version": "0.1.0"]
        default:
            return ["error": "unknown action: \(action)"]
        }
    }
}

enum NativeMessagingError: Error {
    case invalidLength
    case invalidJSON
    case eof
}
