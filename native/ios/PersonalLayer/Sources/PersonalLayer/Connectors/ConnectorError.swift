import Foundation

enum ConnectorError: Error {
    case invalidResponse
    case apiError(status: Int, message: String)
    case rateLimited(retryAfter: Int)
    case noData
}
