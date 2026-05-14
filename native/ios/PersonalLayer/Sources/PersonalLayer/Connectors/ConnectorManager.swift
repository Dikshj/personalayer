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
}

final class ConnectorManager: ObservableObject {
    @Published private var connected: Set<ConnectorType> = []

    func isConnected(_ type: ConnectorType) -> Bool { connected.contains(type) }

    func connect(_ type: ConnectorType) {
        guard let url = oauthURL(for: type) else { return }
        let session = ASWebAuthenticationSession(
            url: url,
            callbackURLScheme: "personalayer"
        ) { callbackURL, error in
            guard let url = callbackURL, error == nil else { return }
            // TODO: exchange code for token, save to OAuthTokenStore
            DispatchQueue.main.async { self.connected.insert(type) }
        }
        session.presentationContextProvider = AuthContextProvider.shared
        session.start()
    }

    private func oauthURL(for type: ConnectorType) -> URL? {
        // TODO: return proper OAuth URLs per provider
        switch type {
        case .gmail:
            return URL(string: "https://accounts.google.com/o/oauth2/v2/auth?client_id=CLIENT_ID&redirect_uri=personalayer://oauth&scope=https://www.googleapis.com/auth/gmail.metadata&response_type=code")
        case .calendar:
            return URL(string: "https://accounts.google.com/o/oauth2/v2/auth?client_id=CLIENT_ID&redirect_uri=personalayer://oauth&scope=https://www.googleapis.com/auth/calendar.readonly&response_type=code")
        case .spotify:
            return URL(string: "https://accounts.spotify.com/authorize?client_id=CLIENT_ID&redirect_uri=personalayer://oauth&scope=user-read-recently-played&response_type=code")
        case .googleFit:
            return URL(string: "https://accounts.google.com/o/oauth2/v2/auth?client_id=CLIENT_ID&redirect_uri=personalayer://oauth&scope=https://www.googleapis.com/auth/fitness.activity.read&response_type=code")
        case .notion:
            return URL(string: "https://api.notion.com/v1/oauth/authorize?client_id=CLIENT_ID&redirect_uri=personalayer://oauth&response_type=code")
        case .youtube:
            return URL(string: "https://accounts.google.com/o/oauth2/v2/auth?client_id=CLIENT_ID&redirect_uri=personalayer://oauth&scope=https://www.googleapis.com/auth/youtube.readonly&response_type=code")
        }
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
