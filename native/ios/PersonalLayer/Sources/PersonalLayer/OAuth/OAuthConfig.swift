import Foundation

/// OAuth provider configuration loaded from Info.plist or environment.
/// Add real client IDs to the Info.plist under the OAuthProviders dictionary.
enum OAuthConfig {
    static func clientID(for provider: OAuthProvider) -> String {
        guard let dict = Bundle.main.infoDictionary?["OAuthProviders"] as? [String: String],
              let id = dict[provider.rawValue] else {
            print("WARNING: Missing OAuth client ID for \(provider.rawValue) in Info.plist")
            return ""
        }
        return id
    }

    static func clientSecret(for provider: OAuthProvider) -> String {
        guard let dict = Bundle.main.infoDictionary?["OAuthSecrets"] as? [String: String],
              let secret = dict[provider.rawValue] else {
            return ""  // PKCE flows (Google, Notion) don't require client secret
        }
        return secret
    }

    static func redirectURI(for provider: OAuthProvider) -> String {
        switch provider {
        case .google: return "com.personalayer.ios:/oauth2redirect"
        case .spotify: return "personalayer://spotify-callback"
        case .notion: return "https://localhost/oauth/callback"
        }
    }
}
