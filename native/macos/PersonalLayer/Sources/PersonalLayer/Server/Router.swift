import Foundation

struct Router {
    let database: GRDBDatabase
    let domainStore: DomainApprovalStore

    func handle(_ request: HTTPRequest) -> HTTPResponse {
        switch (request.method, request.path) {
        case ("GET", "/v1/context/bundle"):
            return BundleEndpoint(database: database).handle(request)
        case ("POST", "/v1/ingest/extension"):
            return IngestEndpoint(database: database).handle(request)
        case ("OPTIONS", _):
            return HTTPResponse(status: 204, contentType: "text/plain", body: Data())
        default:
            return HTTPResponse(status: 404, contentType: "application/json", body: Data(#"{"error":"Not found"}"#.utf8))
        }
    }
}
