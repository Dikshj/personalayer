import GRDB
import Foundation

struct RawEvent: Codable, FetchableRecord, MutablePersistableRecord {
    var id: Int64?
    var eventType: String
    var payload: String
    var createdAt: Date
    var privacyFiltered: Bool
    var connectorType: String?

    mutating func didInsert(with rowID: Int64, for column: String?) { id = rowID }
}

struct KGNode: Codable, FetchableRecord, MutablePersistableRecord {
    var id: Int64?
    var entityId: String
    var entityType: String
    var label: String
    var attributes: String
    var embedding: Data?
    var tier: String
    var signalStrength: Double
    var lastAccessedAt: Date
    var createdAt: Date
    var updatedAt: Date

    mutating func didInsert(with rowID: Int64, for column: String?) { id = rowID }
}

struct KGEdge: Codable, FetchableRecord, MutablePersistableRecord {
    var id: Int64?
    var sourceEntityId: String
    var targetEntityId: String
    var relationType: String
    var weight: Double
    var evidence: String
    var createdAt: Date

    mutating func didInsert(with rowID: Int64, for column: String?) { id = rowID }
}

struct TemporalChain: Codable, FetchableRecord, MutablePersistableRecord {
    var id: Int64?
    var chainType: String
    var sequence: String
    var startDate: Date
    var endDate: Date
    var createdAt: Date

    mutating func didInsert(with rowID: Int64, for column: String?) { id = rowID }
}

struct DomainApproval: Codable, FetchableRecord, MutablePersistableRecord {
    var id: Int64?
    var domain: String
    var isApproved: Bool
    var approvedAt: Date

    mutating func didInsert(with rowID: Int64, for column: String?) { id = rowID }
}

struct SharedBundle: Codable, FetchableRecord, MutablePersistableRecord {
    var id: Int64?
    var userId: String
    var bundleJson: String
    var updatedAt: Date

    mutating func didInsert(with rowID: Int64, for column: String?) { id = rowID }
}

enum MemoryTier: String, Codable {
    case hot = "HOT"
    case warm = "WARM"
    case cool = "COOL"
    case cold = "COLD"
}
