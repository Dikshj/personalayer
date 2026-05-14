import Foundation

/// OAuth provider configuration.
/// Loads from Info.plist first, then falls back to environment variables.
enum OAuthConfig {
    private static func string(for key: String) -> String {
        // 1. Try Info.plist
        if let dict = Bundle.main.infoDictionary?["OAuthProviders"] as? [String: String],
           let value = dict[key], !value.hasPrefix("YOUR_") {
            return value
        }
        // 2. Try environment (for CI/testing)
        if let value = ProcessInfo.processInfo.environment["OAUTH_\(key.uppercased())_CLIENT_ID"], !value.isEmpty {
            return value
        }
        return ""
    }

    static func clientID(for provider: OAuthProvider) -> String {
        let id = string(for: provider.rawValue)
        if id.isEmpty {
            print("[WARNING] Missing OAuth client ID for \(provider.rawValue). " +
                  "Set in Info.plist OAuthProviders dict or environment OAUTH_\(provider.rawValue.uppercased())_CLIENT_ID")
        }
        return id
    }

    static func clientSecret(for provider: OAuthProvider) -> String {
        guard let dict = Bundle.main.infoDictionary?["OAuthSecrets"] as? [String: String] else { return "" }
        return dict[provider.rawValue] ?? ""
    }

    static func redirectURI(for provider: OAuthProvider) -> String {
        switch provider {
        case .google: return "com.personalayer.ios:/oauth2redirect"
        case .spotify: return "personalayer://spotify-callback"
        case .notion: return "https://localhost/oauth/callback"
        }
    }

    /// Check if all required OAuth credentials are configured.
    static func isConfigured(for provider: OAuthProvider) -> Bool {
        return !clientID(for: provider).isEmpty
    }
}
