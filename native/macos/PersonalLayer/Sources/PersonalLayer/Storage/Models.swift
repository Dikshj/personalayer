import GRDB
import Foundation

// MARK: - Raw Event

struct RawEvent: Codable, FetchableRecord, MutablePersistableRecord {
    var id: Int64?
    var eventType: String
    var payload: String
    var createdAt: Date
    var privacyFiltered: Bool
    var connectorType: String?

    mutating func didInsert(with rowID: Int64, for column: String?) {
        id = rowID
    }
}

// MARK: - Knowledge Graph Node

struct KGNode: Codable, FetchableRecord, MutablePersistableRecord {
    var id: Int64?
    var entityId: String
    var entityType: String
    var label: String
    var attributes: String // JSON
    var embedding: Data? // 384 floats as Data
    var tier: String // HOT, WARM, COOL, COLD
    var signalStrength: Double
    var lastAccessedAt: Date
    var createdAt: Date
    var updatedAt: Date

    mutating func didInsert(with rowID: Int64, for column: String?) {
        id = rowID
    }
}

// MARK: - Knowledge Graph Edge

struct KGEdge: Codable, FetchableRecord, MutablePersistableRecord {
    var id: Int64?
    var sourceEntityId: String
    var targetEntityId: String
    var relationType: String
    var weight: Double
    var evidence: String // JSON array of event IDs
    var createdAt: Date

    mutating func didInsert(with rowID: Int64, for column: String?) {
        id = rowID
    }
}

// MARK: - Temporal Chain

struct TemporalChain: Codable, FetchableRecord, MutablePersistableRecord {
    var id: Int64?
    var chainType: String
    var sequence: String // JSON array of {entityId, timestamp}
    var startDate: Date
    var endDate: Date
    var createdAt: Date

    mutating func didInsert(with rowID: Int64, for column: String?) {
        id = rowID
    }
}

// MARK: - Domain Approval

struct DomainApproval: Codable, FetchableRecord, MutablePersistableRecord {
    var id: Int64?
    var domain: String
    var isApproved: Bool
    var approvedAt: Date

    mutating func didInsert(with rowID: Int64, for column: String?) {
        id = rowID
    }
}

// MARK: - Shared Bundle

struct SharedBundle: Codable, FetchableRecord, MutablePersistableRecord {
    var id: Int64?
    var userId: String
    var bundleJson: String
    var updatedAt: Date

    mutating func didInsert(with rowID: Int64, for column: String?) {
        id = rowID
    }
}

// MARK: - Memory Tier

enum MemoryTier: String, Codable {
    case hot = "HOT"
    case warm = "WARM"
    case cool = "COOL"
    case cold = "COLD"
}
