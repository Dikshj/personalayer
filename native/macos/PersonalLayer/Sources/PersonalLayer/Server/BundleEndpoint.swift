import Foundation

struct BundleEndpoint {
    let database: GRDBDatabase

    func handle(_ request: HTTPRequest) -> HTTPResponse {
        do {
            let bundle = try database.loadSharedBundle()
            let hot = try database.nodesByTier(.hot, limit: 50)
            let warm = try database.nodesByTier(.warm, limit: 50)

            var response: [String: Any] = bundle
            response["nodes"] = [
                "hot": hot.map { ["id": $0.entityId, "label": $0.label, "type": $0.entityType, "strength": $0.signalStrength] },
                "warm": warm.map { ["id": $0.entityId, "label": $0.label, "type": $0.entityType, "strength": $0.signalStrength] }
            ]
            response["version"] = "v4"
            response["generated_at"] = ISO8601DateFormatter().string(from: Date())

            let data = try JSONSerialization.data(withJSONObject: response)
            return HTTPResponse(status: 200, contentType: "application/json", body: data)
        } catch {
            let body = Data("{\"error\": \"Failed to load bundle\"}".utf8)
            return HTTPResponse(status: 500, contentType: "application/json", body: body)
        }
    }
}
