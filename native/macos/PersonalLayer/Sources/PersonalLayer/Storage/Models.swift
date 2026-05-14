import GRDB

struct RawEvent: Codable, FetchableRecord, MutablePersistableRecord {
    var id: Int64?
    var eventType: String
    var payload: String
    var createdAt: Date
    var privacyFiltered: Bool

    mutating func didInsert(with rowID: Int64, for column: String?) {
        id = rowID
    }
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

extension RawEvent {
    static let databaseTableName = "raw_events"
}

extension DomainApproval {
    static let databaseTableName = "domain_approvals"
}

extension SharedBundle {
    static let databaseTableName = "shared_bundles"
}
