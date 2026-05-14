import Foundation

enum OAuthProvider {
    case google
    case spotify
    case notion

    var tokenURL: URL {
        switch self {
        case .google:
            return URL(string: "https://oauth2.googleapis.com/token")!
        case .spotify:
            return URL(string: "https://accounts.spotify.com/api/token")!
        case .notion:
            return URL(string: "https://api.notion.com/v1/oauth/token")!
        }
    }

    var clientId: String {
        switch self {
        case .google: return Bundle.main.object(forInfoDictionaryKey: "GOOGLE_CLIENT_ID") as? String ?? ""
        case .spotify: return Bundle.main.object(forInfoDictionaryKey: "SPOTIFY_CLIENT_ID") as? String ?? ""
        case .notion: return Bundle.main.object(forInfoDictionaryKey: "NOTION_CLIENT_ID") as? String ?? ""
        }
    }

    var clientSecret: String {
        switch self {
        case .google: return Bundle.main.object(forInfoDictionaryKey: "GOOGLE_CLIENT_SECRET") as? String ?? ""
        case .spotify: return Bundle.main.object(forInfoDictionaryKey: "SPOTIFY_CLIENT_SECRET") as? String ?? ""
        case .notion: return Bundle.main.object(forInfoDictionaryKey: "NOTION_CLIENT_SECRET") as? String ?? ""
        }
    }

    var redirectURI: String {
        "personalayer://oauth"
    }
}

actor OAuthTokenExchange {
    static let shared = OAuthTokenExchange()

    func exchangeCode(provider: OAuthProvider, code: String) async throws -> (accessToken: String, refreshToken: String?, expiresIn: Int?) {
        var request = URLRequest(url: provider.tokenURL)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")

        var params: [String: String] = [
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": provider.redirectURI,
            "client_id": provider.clientId
        ]

        if !provider.clientSecret.isEmpty {
            params["client_secret"] = provider.clientSecret
        }

        let body = params.map { "\($0)=\($1.addingPercentEncoding(withAllowedCharacters: .urlQueryValueAllowed)!)" }.joined(separator: "&")
        request.httpBody = body.data(using: .utf8)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            let errorBody = String(data: data, encoding: .utf8) ?? "unknown"
            throw OAuthError.tokenExchangeFailed(message: errorBody)
        }

        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let accessToken = json["access_token"] as? String else {
            throw OAuthError.invalidTokenResponse
        }

        let refreshToken = json["refresh_token"] as? String
        let expiresIn = json["expires_in"] as? Int

        let providerName = String(describing: provider).lowercased()
        try OAuthTokenStore.save(
            provider: providerName,
            token: accessToken,
            metadata: [
                "refresh_token": refreshToken ?? "",
                "expires_in": expiresIn ?? 0,
                "obtained_at": ISO8601DateFormatter().string(from: Date())
            ]
        )

        return (accessToken, refreshToken, expiresIn)
    }

    func refreshToken(provider: OAuthProvider) async throws -> String {
        let providerName = String(describing: provider).lowercased()
        guard let stored = OAuthTokenStore.load(provider: providerName),
              let refreshToken = stored.metadata["refresh_token"] as? String,
              !refreshToken.isEmpty else {
            throw OAuthError.noRefreshToken
        }

        var request = URLRequest(url: provider.tokenURL)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")

        let params = [
            "grant_type": "refresh_token",
            "refresh_token": refreshToken,
            "client_id": provider.clientId,
            "client_secret": provider.clientSecret
        ]
        let body = params.map { "\($0)=\($1.addingPercentEncoding(withAllowedCharacters: .urlQueryValueAllowed)!)" }.joined(separator: "&")
        request.httpBody = body.data(using: .utf8)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw OAuthError.tokenRefreshFailed
        }

        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let accessToken = json["access_token"] as? String else {
            throw OAuthError.invalidTokenResponse
        }

        try OAuthTokenStore.save(
            provider: providerName,
            token: accessToken,
            metadata: [
                "refresh_token": json["refresh_token"] as? String ?? refreshToken,
                "expires_in": json["expires_in"] as? Int ?? 0,
                "refreshed_at": ISO8601DateFormatter().string(from: Date())
            ]
        )

        return accessToken
    }
}

enum OAuthError: Error {
    case tokenExchangeFailed(message: String)
    case invalidTokenResponse
    case noRefreshToken
    case tokenRefreshFailed
}

extension CharacterSet {
    static let urlQueryValueAllowed: CharacterSet = {
        var allowed = CharacterSet.urlQueryAllowed
        allowed.remove(charactersIn: "&+=")
        return allowed
    }()
}
