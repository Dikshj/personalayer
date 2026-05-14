import Foundation

struct IngestEndpoint {
    let database: GRDBDatabase

    func handle(_ request: HTTPRequest) -> HTTPResponse {
        do {
            guard let json = try JSONSerialization.jsonObject(with: request.body) as? [String: Any] else {
                return HTTPResponse(status: 400, contentType: "application/json", body: Data(#"{"error":"Invalid JSON"}"#.utf8))
            }
            let eventType = json["event_type"] as? String ?? "unknown"
            let payload = json["payload"] as? [String: Any] ?? [:]
            try database.insertRawEvent(type: eventType, payload: payload)
            let body = try JSONSerialization.data(withJSONObject: ["ok": true])
            return HTTPResponse(status: 200, contentType: "application/json", body: body)
        } catch {
            let body = try! JSONSerialization.data(withJSONObject: ["error": error.localizedDescription])
            return HTTPResponse(status: 500, contentType: "application/json", body: body)
        }
    }
}
