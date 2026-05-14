import Foundation

enum ConnectorError: Error {
    case invalidResponse
    case unauthorized
    case rate_limited(retryAfter: Int)
    case api_error(status: Int, message: String)
    case network(Error)
}

extension ConnectorError: LocalizedError {
    var errorDescription: String? {
        switch self {
        case .invalidResponse: return "Invalid response from API"
        case .unauthorized: return "OAuth token expired or invalid. Please reconnect."
        case .rate_limited(let retryAfter): return "Rate limited. Retry after \(retryAfter)s"
        case .api_error(let status, let message): return "API error \(status): \(message)"
        case .network(let error): return "Network error: \(error.localizedDescription)"
        }
    }
}
