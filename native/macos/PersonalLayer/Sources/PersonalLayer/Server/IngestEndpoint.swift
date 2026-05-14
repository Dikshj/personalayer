import Foundation

struct IngestEndpoint {
    let database: GRDBDatabase

    func handle(_ request: HTTPRequest) -> HTTPResponse {
        do {
            guard let json = try JSONSerialization.jsonObject(with: request.body) as? [String: Any] else {
                return HTTPResponse(status: 400, contentType: "application/json", body: Data("{\"error\": \"Invalid JSON\"}".utf8))
            }

            guard let eventType = json["event_type"] as? String else {
                return HTTPResponse(status: 400, contentType: "application/json", body: Data("{\"error\": \"Missing event_type\"}".utf8))
            }

            // Privacy gate: reject if payload contains blocked keywords
            let payloadStr = String(data: request.body, encoding: .utf8) ?? ""
            let blocked = ["password", "ssn", "credit_card", "secret_key", "api_key"]
            let lowerPayload = payloadStr.lowercased()
            for keyword in blocked {
                if lowerPayload.contains(keyword) {
                    return HTTPResponse(status: 403, contentType: "application/json", body: Data("{\"error\": \"Payload blocked by privacy filter\"}".utf8))
                }
            }

            // Size limit: 1MB
            guard request.body.count < 1_000_000 else {
                return HTTPResponse(status: 413, contentType: "application/json", body: Data("{\"error\": \"Payload too large\"}".utf8))
            }

            try database.insertRawEvent(type: eventType, payload: json)

            let response: [String: Any] = ["status": "ingested", "event_type": eventType]
            let data = try JSONSerialization.data(withJSONObject: response)
            return HTTPResponse(status: 200, contentType: "application/json", body: data)
        } catch {
            return HTTPResponse(status: 500, contentType: "application/json", body: Data("{\"error\": \"Internal error\"}".utf8))
        }
    }
}
