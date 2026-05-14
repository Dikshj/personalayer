import Foundation
import AuthenticationServices

enum OAuthProvider: String {
    case google = "google"
    case spotify = "spotify"
    case notion = "notion"

    var authorizationEndpoint: URL {
        switch self {
        case .google: return URL(string: "https://accounts.google.com/o/oauth2/v2/auth")!
        case .spotify: return URL(string: "https://accounts.spotify.com/authorize")!
        case .notion: return URL(string: "https://api.notion.com/v1/oauth/authorize")!
        }
    }

    var tokenEndpoint: URL {
        switch self {
        case .google: return URL(string: "https://oauth2.googleapis.com/token")!
        case .spotify: return URL(string: "https://accounts.spotify.com/api/token")!
        case .notion: return URL(string: "https://api.notion.com/v1/oauth/token")!
        }
    }

    var scopes: String {
        switch self {
        case .google: return "https://www.googleapis.com/auth/gmail.metadata https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/youtube.readonly"
        case .spotify: return "user-read-recently-played"
        case .notion: return "read_user read_database"
        }
    }
}

final class OAuthTokenExchange {
    static let shared = OAuthTokenExchange()

    func startAuth(provider: OAuthProvider, presentingViewController: UIViewController, completion: @escaping (Result<String, Error>) -> Void) {
        let clientID = OAuthConfig.clientID(for: provider)
        guard !clientID.isEmpty else {
            completion(.failure(OAuthError.missingClientID))
            return
        }

        var components = URLComponents(url: provider.authorizationEndpoint, resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "client_id", value: clientID),
            URLQueryItem(name: "redirect_uri", value: OAuthConfig.redirectURI(for: provider)),
            URLQueryItem(name: "response_type", value: "code"),
            URLQueryItem(name: "scope", value: provider.scopes),
            URLQueryItem(name: "access_type", value: "offline")
        ]

        guard let url = components.url else {
            completion(.failure(OAuthError.invalidURL))
            return
        }

        let session = ASWebAuthenticationSession(url: url, callbackURLScheme: "com.personalayer.ios") { callbackURL, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            guard let callbackURL = callbackURL,
                  let code = URLComponents(url: callbackURL, resolvingAgainstBaseURL: false)?.queryItems?.first(where: { $0.name == "code" })?.value else {
                completion(.failure(OAuthError.missingAuthCode))
                return
            }
            Task {
                do {
                    let token = try await self.exchangeCode(code: code, provider: provider)
                    completion(.success(token))
                } catch {
                    completion(.failure(error))
                }
            }
        }
        session.presentationContextProvider = presentingViewController as? ASWebAuthenticationPresentationContextProviding
        session.start()
    }

    func exchangeCode(code: String, provider: OAuthProvider) async throws -> String {
        let clientID = OAuthConfig.clientID(for: provider)
        let clientSecret = OAuthConfig.clientSecret(for: provider)

        var request = URLRequest(url: provider.tokenEndpoint)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")

        var bodyComponents = URLComponents()
        bodyComponents.queryItems = [
            URLQueryItem(name: "grant_type", value: "authorization_code"),
            URLQueryItem(name: "code", value: code),
            URLQueryItem(name: "redirect_uri", value: OAuthConfig.redirectURI(for: provider)),
            URLQueryItem(name: "client_id", value: clientID)
        ]
        if !clientSecret.isEmpty {
            bodyComponents.queryItems?.append(URLQueryItem(name: "client_secret", value: clientSecret))
        }

        request.httpBody = bodyComponents.query?.data(using: .utf8)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw OAuthError.tokenExchangeFailed(body)
        }
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let accessToken = json["access_token"] as? String else {
            throw OAuthError.invalidTokenResponse
        }

        let refreshToken = json["refresh_token"] as? String
        let expiresIn = json["expires_in"] as? Int ?? 3600

        let metadata: [String: Any] = [
            "obtained_at": ISO8601DateFormatter().string(from: Date()),
            "expires_in": expiresIn,
            "refresh_token": refreshToken ?? ""
        ]

        let tokenInfo = OAuthTokenStore.TokenInfo(token: accessToken, metadata: metadata)
        OAuthTokenStore.save(tokenInfo: tokenInfo, provider: provider.rawValue)

        return accessToken
    }

    func refreshToken(provider: OAuthProvider) async throws -> String {
        guard let stored = OAuthTokenStore.load(provider: provider.rawValue),
              let refreshToken = stored.metadata["refresh_token"] as? String,
              !refreshToken.isEmpty else {
            throw OAuthError.noRefreshToken
        }

        let clientID = OAuthConfig.clientID(for: provider)
        let clientSecret = OAuthConfig.clientSecret(for: provider)

        var request = URLRequest(url: provider.tokenEndpoint)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")

        var bodyComponents = URLComponents()
        bodyComponents.queryItems = [
            URLQueryItem(name: "grant_type", value: "refresh_token"),
            URLQueryItem(name: "refresh_token", value: refreshToken),
            URLQueryItem(name: "client_id", value: clientID)
        ]
        if !clientSecret.isEmpty {
            bodyComponents.queryItems?.append(URLQueryItem(name: "client_secret", value: clientSecret))
        }

        request.httpBody = bodyComponents.query?.data(using: .utf8)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw OAuthError.tokenRefreshFailed
        }
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let accessToken = json["access_token"] as? String else {
            throw OAuthError.invalidTokenResponse
        }

        let newRefreshToken = json["refresh_token"] as? String ?? refreshToken
        let expiresIn = json["expires_in"] as? Int ?? 3600

        let metadata: [String: Any] = [
            "obtained_at": ISO8601DateFormatter().string(from: Date()),
            "expires_in": expiresIn,
            "refresh_token": newRefreshToken
        ]

        let tokenInfo = OAuthTokenStore.TokenInfo(token: accessToken, metadata: metadata)
        OAuthTokenStore.save(tokenInfo: tokenInfo, provider: provider.rawValue)

        return accessToken
    }
}

enum OAuthError: Error {
    case missingClientID
    case invalidURL
    case missingAuthCode
    case tokenExchangeFailed(String)
    case tokenRefreshFailed
    case invalidTokenResponse
    case noRefreshToken
}
