import GRDB

struct RawEvent: Codable, FetchableRecord, MutablePersistableRecord {
    var id: Int64?
    var eventType: String
    var payload: String
    var createdAt: Date
    var privacyFiltered: Bool
    mutating func didInsert(with rowID: Int64, for column: String?) { id = rowID }
}

struct KGNode: Codable, FetchableRecord, PersistableRecord {
    var id: String
    var label: String
    var nodeType: String
    var embeddingJson: String?
    var metadataJson: String?
    var createdAt: Date
}

struct KGEdge: Codable, FetchableRecord, PersistableRecord {
    var sourceId: String
    var targetId: String
    var relation: String
    var weight: Double
    var createdAt: Date
}

struct TemporalChain: Codable, FetchableRecord, PersistableRecord {
    var id: Int64?
    var chainType: String
    var nodesJson: String
    var createdAt: Date
}

struct DomainApproval: Codable, FetchableRecord, PersistableRecord {
    var domain: String
    var approvedAt: Date
}

struct SharedBundle: Codable, FetchableRecord, MutablePersistableRecord {
    var id: Int64?
    var userId: String
    var bundleJson: String
    var updatedAt: Date

    mutating func didInsert(with rowID: Int64, for column: String?) {
        id = rowID
    }
}
