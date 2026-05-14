import Foundation
import AuthenticationServices

enum ConnectorType: String, CaseIterable {
    case gmail = "gmail"
    case calendar = "calendar"
    case spotify = "spotify"
    case googleFit = "google_fit"
    case notion = "notion"
    case youtube = "youtube"

    var displayName: String {
        switch self {
        case .gmail: return "Gmail"
        case .calendar: return "Google Calendar"
        case .spotify: return "Spotify"
        case .googleFit: return "Google Fit"
        case .notion: return "Notion"
        case .youtube: return "YouTube"
        }
    }

    var oauthProvider: OAuthProvider? {
        switch self {
        case .gmail, .calendar, .googleFit, .youtube: return .google
        case .spotify: return .spotify
        case .notion: return .notion
        }
    }

    var scope: String {
        switch self {
        case .gmail:
            return "https://www.googleapis.com/auth/gmail.metadata"
        case .calendar:
            return "https://www.googleapis.com/auth/calendar.readonly"
        case .spotify:
            return "user-read-recently-played"
        case .googleFit:
            return "https://www.googleapis.com/auth/fitness.activity.read"
        case .notion:
            return ""
        case .youtube:
            return "https://www.googleapis.com/auth/youtube.readonly"
        }
    }
}

final class ConnectorManager: ObservableObject {
    @Published private var connected: Set<ConnectorType> = []

    func isConnected(_ type: ConnectorType) -> Bool { connected.contains(type) }

    func connect(_ type: ConnectorType) {
        guard let url = buildAuthURL(for: type) else { return }
        let session = ASWebAuthenticationSession(
            url: url,
            callbackURLScheme: "personalayer"
        ) { [weak self] callbackURL, error in
            guard let url = callbackURL, error == nil else { return }
            Task {
                do {
                    if let code = self?.extractCode(from: url),
                       let provider = type.oauthProvider {
                        _ = try await OAuthTokenExchange.shared.exchangeCode(provider: provider, code: code)
                        await MainActor.run { self?.connected.insert(type) }
                    }
                } catch {
                    print("OAuth exchange failed: \(error)")
                }
            }
        }
        session.presentationContextProvider = AuthContextProvider.shared
        session.start()
    }

    private func buildAuthURL(for type: ConnectorType) -> URL? {
        guard let provider = type.oauthProvider else { return nil }
        let clientId = provider.clientId
        var components: URLComponents?

        switch provider {
        case .google:
            components = URLComponents(string: "https://accounts.google.com/o/oauth2/v2/auth")
            components?.queryItems = [
                URLQueryItem(name: "client_id", value: clientId),
                URLQueryItem(name: "redirect_uri", value: provider.redirectURI),
                URLQueryItem(name: "response_type", value: "code"),
                URLQueryItem(name: "scope", value: type.scope),
                URLQueryItem(name: "access_type", value: "offline"),
                URLQueryItem(name: "prompt", value: "consent")
            ]
        case .spotify:
            components = URLComponents(string: "https://accounts.spotify.com/authorize")
            components?.queryItems = [
                URLQueryItem(name: "client_id", value: clientId),
                URLQueryItem(name: "redirect_uri", value: provider.redirectURI),
                URLQueryItem(name: "response_type", value: "code"),
                URLQueryItem(name: "scope", value: type.scope)
            ]
        case .notion:
            components = URLComponents(string: "https://api.notion.com/v1/oauth/authorize")
            components?.queryItems = [
                URLQueryItem(name: "client_id", value: clientId),
                URLQueryItem(name: "redirect_uri", value: provider.redirectURI),
                URLQueryItem(name: "response_type", value: "code")
            ]
        }
        return components?.url
    }

    private func extractCode(from url: URL) -> String? {
        URLComponents(url: url, resolvingAgainstBaseURL: false)?
            .queryItems?
            .first(where: { $0.name == "code" })?
            .value
    }
}

final class AuthContextProvider: NSObject, ASWebAuthenticationPresentationContextProviding {
    static let shared = AuthContextProvider()
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .first?.windows.first ?? UIWindow()
    }
}
