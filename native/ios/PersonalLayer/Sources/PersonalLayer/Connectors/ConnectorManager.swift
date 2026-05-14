import Foundation
import SwiftUI

enum ConnectorType: String, CaseIterable {
    case gmail = "Gmail"
    case calendar = "Calendar"
    case spotify = "Spotify"
    case googleFit = "Google Fit"
    case notion = "Notion"
    case youtube = "YouTube"

    var displayName: String { rawValue }
    var provider: String {
        switch self {
        case .gmail, .calendar, .googleFit, .youtube: return "google"
        case .spotify: return "spotify"
        case .notion: return "notion"
        }
    }
}

@MainActor
class ConnectorManager: ObservableObject {
    @Published private(set) var connected: Set<ConnectorType> = []

    init() {
        refreshStatus()
    }

    func refreshStatus() {
        for type in ConnectorType.allCases {
            if OAuthTokenStore.load(provider: type.provider) != nil {
                connected.insert(type)
            } else {
                connected.remove(type)
            }
        }
    }

    func isConnected(_ type: ConnectorType) -> Bool {
        connected.contains(type)
    }

    func connect(_ type: ConnectorType) {
        let provider = oauthProviderForType(type)
        guard let window = UIApplication.shared.windows.first else { return }
        OAuthTokenExchange.shared.startAuth(provider: provider, presentingViewController: window.rootViewController!) { result in
            Task { @MainActor in
                switch result {
                case .success:
                    self.connected.insert(type)
                case .failure(let error):
                    print("OAuth failed for \(type): \(error)")
                }
            }
        }
    }

    func disconnect(_ type: ConnectorType) {
        OAuthTokenStore.delete(provider: type.provider)
        connected.remove(type)
    }
}

private func oauthProviderForType(_ type: ConnectorType) -> OAuthProvider {
    switch type {
    case .gmail, .calendar, .googleFit, .youtube: return .google
    case .spotify: return .spotify
    case .notion: return .notion
    }
}
