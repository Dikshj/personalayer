import Foundation

struct BundleEndpoint {
    let database: GRDBDatabase

    func handle(_ request: HTTPRequest) -> HTTPResponse {
        do {
            let bundle = try database.loadSharedBundle()
            let data = try JSONSerialization.data(withJSONObject: bundle, options: .prettyPrinted)
            return HTTPResponse(status: 200, contentType: "application/json", body: data)
        } catch {
            let body = try! JSONSerialization.data(withJSONObject: ["error": error.localizedDescription])
            return HTTPResponse(status: 500, contentType: "application/json", body: body)
        }
    }
}
