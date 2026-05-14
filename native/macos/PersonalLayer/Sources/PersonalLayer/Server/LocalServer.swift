import Network
import Foundation
import Combine

final class LocalServer: ObservableObject {
    @Published var isRunning = false

    private var listener: NWListener?
    private let queue = DispatchQueue(label: "com.personalayer.server")
    private let domainStore: DomainApprovalStore
    private let database: GRDBDatabase

    init(domainStore: DomainApprovalStore = DomainApprovalStore(),
         database: GRDBDatabase = GRDBDatabase.shared) {
        self.domainStore = domainStore
        self.database = database
    }

    func start() throws {
        let parameters = NWParameters.tcp
        listener = try NWListener(using: parameters, on: 7432)
        listener?.stateUpdateHandler = { [weak self] state in
            DispatchQueue.main.async {
                self?.isRunning = (state == .ready)
            }
        }
        listener?.newConnectionHandler = { [weak self] connection in
            self?.handleConnection(connection)
        }
        listener?.start(queue: queue)
    }

    func stop() {
        listener?.cancel()
        listener = nil
        DispatchQueue.main.async { self.isRunning = false }
    }

    private func handleConnection(_ connection: NWConnection) {
        connection.start(queue: queue)
        receiveHTTPRequest(connection)
    }

    private func receiveHTTPRequest(_ connection: NWConnection) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] data, _, isComplete, error in
            guard let self = self, let data = data, error == nil else {
                connection.cancel(); return
            }
            let origin = HTTPRequest(data: data)?.headers["Origin"] ?? HTTPRequest(data: data)?.headers["origin"]
            if let request = HTTPRequest(data: data),
               let requestOrigin = origin {
                let allowed = self.domainStore.isApproved(domain: requestOrigin) || requestOrigin.contains("localhost") || requestOrigin.contains("127.0.0.1")
                if !allowed {
                    self.sendJSON(connection, status: 403, body: ["error": "Domain not approved"], origin: requestOrigin)
                    return
                }
            }
            self.route(request: HTTPRequest(data: data), origin: origin, connection: connection)
            if !isComplete {
                self.receiveHTTPRequest(connection)
            }
        }
    }

    private func route(request: HTTPRequest?, origin: String?, connection: NWConnection) {
        guard let request = request else {
            sendJSON(connection, status: 400, body: ["error": "Bad request"], origin: origin); return
        }
        let router = Router(database: database, domainStore: domainStore)
        let response = router.handle(request)
        send(connection, response: response, origin: origin)
    }

    private func sendJSON(_ connection: NWConnection, status: Int, body: [String: Any], origin: String? = nil) {
        let data = try! JSONSerialization.data(withJSONObject: body)
        var headers = "HTTP/1.1 \(status)\r\nContent-Type: application/json\r\nContent-Length: \(data.count)\r\n"
        if let origin = origin {
            headers += "Access-Control-Allow-Origin: \(origin)\r\n"
        }
        headers += "\r\n"
        let payload = Data(headers.utf8) + data
        connection.send(content: payload, completion: .contentProcessed { _ in connection.cancel() })
    }

    private func send(_ connection: NWConnection, response: HTTPResponse, origin: String? = nil) {
        var headers = "HTTP/1.1 \(response.status)\r\nContent-Type: \(response.contentType)\r\nContent-Length: \(response.body.count)\r\n"
        if let origin = origin {
            headers += "Access-Control-Allow-Origin: \(origin)\r\n"
        }
        headers += "\r\n"
        let payload = Data(headers.utf8) + response.body
        connection.send(content: payload, completion: .contentProcessed { _ in })
    }
}

struct HTTPRequest {
    let method: String
    let path: String
    let headers: [String: String]
    let body: Data

    init?(data: Data) {
        guard let raw = String(data: data, encoding: .utf8) else { return nil }
        let lines = raw.components(separatedBy: "\r\n")
        guard let first = lines.first else { return nil }
        let parts = first.split(separator: " ")
        guard parts.count >= 2 else { return nil }
        self.method = String(parts[0])
        self.path = String(parts[1])
        var headers: [String: String] = [:]
        for line in lines.dropFirst() {
            if line.isEmpty { break }
            let headerParts = line.split(separator: ":", maxSplits: 1)
            if headerParts.count == 2 {
                headers[String(headerParts[0]).trimmingCharacters(in: .whitespaces)] = String(headerParts[1]).trimmingCharacters(in: .whitespaces)
            }
        }
        self.headers = headers
        if let split = raw.range(of: "\r\n\r\n") {
            self.body = data.subdata(in: split.upperBound..<data.endIndex)
        } else {
            self.body = Data()
        }
    }
}

struct HTTPResponse {
    let status: Int
    let contentType: String
    let body: Data
}
