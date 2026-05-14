import Foundation

/// Typed OAuth token storage using the Keychain.
/// Supports masked inspection and revocation.
struct OAuthTokenStore {
    private static let service = "com.personalayer.oauth"

    static func save(provider: String, token: String, metadata: [String: Any]) throws {
        let account = "oauth:\(provider)"
        let payload: [String: Any] = [
            "token": token,
            "metadata": metadata,
            "stored_at": ISO8601DateFormatter().string(from: Date())
        ]
        let data = try JSONSerialization.data(withJSONObject: payload)
        try KeychainManager.save(service: service, account: account, data: data)
    }

    static func load(provider: String) -> (token: String, metadata: [String: Any])? {
        let account = "oauth:\(provider)"
        guard let data = try? KeychainManager.load(service: service, account: account),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let token = json["token"] as? String,
              let metadata = json["metadata"] as? [String: Any] else {
            return nil
        }
        return (token, metadata)
    }

    static func revoke(provider: String) {
        let account = "oauth:\(provider)"
        KeychainManager.delete(service: service, account: account)
    }

    static func listProviders() -> [(provider: String, maskedToken: String, storedAt: String)] {
        // Keychain does not support listing by service prefix natively;
        // in production maintain a small registry index in GRDB.
        return []
    }

    static func maskedToken(_ token: String) -> String {
        guard token.count > 8 else { return "****" }
        return String(token.prefix(4)) + "****" + String(token.suffix(4))
    }
}
