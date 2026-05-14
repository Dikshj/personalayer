import GRDB
import Foundation

final class GRDBDatabase {
    static let shared = GRDBDatabase()
    private let dbPool: DatabasePool

    private init() {
        let fileManager = FileManager.default
        let appSupport = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let dir = appSupport.appendingPathComponent("PersonalLayer", isDirectory: true)
        try? fileManager.createDirectory(at: dir, withIntermediateDirectories: true)
        let dbURL = dir.appendingPathComponent("personal_layer.sqlite")
        dbPool = try! DatabasePool(path: dbURL.path)
        try? migrate()
    }

    private func migrate() throws {
        var migrator = DatabaseMigrator()
        migrator.registerMigration("v1") { db in
            try db.create(table: "raw_events") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("event_type", .text).notNull()
                t.column("payload", .text).notNull()
                t.column("created_at", .datetime).notNull()
                t.column("privacy_filtered", .boolean).notNull().defaults(to: false)
            }
            try db.create(table: "domain_approvals") { t in
                t.column("domain", .text).primaryKey()
                t.column("approved_at", .datetime).notNull()
            }
            try db.create(table: "shared_bundles") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("user_id", .text).notNull().unique()
                t.column("bundle_json", .text).notNull()
                t.column("updated_at", .datetime).notNull()
            }
            try db.create(table: "temporal_chains") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("chain_type", .text).notNull()
                t.column("nodes_json", .text).notNull()
                t.column("created_at", .datetime).notNull()
            }
        }
        try migrator.migrate(dbPool)
    }

    func insertRawEvent(type: String, payload: [String: Any]) throws {
        let jsonData = try JSONSerialization.data(withJSONObject: payload)
        let jsonString = String(data: jsonData, encoding: .utf8)!
        var event = RawEvent(
            id: nil,
            eventType: type,
            payload: jsonString,
            createdAt: Date(),
            privacyFiltered: false
        )
        try dbPool.write { db in
            try event.insert(db)
        }
    }

    func loadSharedBundle() throws -> [String: Any] {
        let bundle = try dbPool.read { db in
            try SharedBundle.fetchOne(db)
        }
        guard let json = bundle?.bundleJson.data(using: .utf8),
              let dict = try JSONSerialization.jsonObject(with: json) as? [String: Any] else {
            return ["profile": [:], "tiers": [:], "daily_insight": nil]
        }
        return dict
    }

    func saveSharedBundle(userId: String, bundle: [String: Any]) throws {
        let jsonData = try JSONSerialization.data(withJSONObject: bundle)
        let jsonString = String(data: jsonData, encoding: .utf8)!
        try dbPool.write { db in
            var record = SharedBundle(
                id: nil,
                userId: userId,
                bundleJson: jsonString,
                updatedAt: Date()
            )
            try record.upsert(db)
        }
    }

    // MARK: - Refresh pipeline helpers

    func markPrivacyFiltered() throws {
        let sevenDaysAgo = Calendar.current.date(byAdding: .day, value: -7, to: Date())!
        try dbPool.write { db in
            try db.execute(
                sql: """
                UPDATE raw_events
                SET privacy_filtered = 1
                WHERE privacy_filtered = 0
                  AND created_at < ?
                  AND (
                    payload LIKE '%ssn%' OR
                    payload LIKE '%password%' OR
                    payload LIKE '%credit_card%' OR
                    payload LIKE '%secret%'
                  )
                """,
                arguments: [sevenDaysAgo]
            )
        }
    }

    func recentRawEvents(limit: Int) throws -> [RawEvent] {
        try dbPool.read { db in
            try RawEvent
                .filter(Column("privacy_filtered") == false)
                .order(Column("created_at").desc)
                .limit(limit)
                .fetchAll(db)
        }
    }

    func deleteRawEventsOlderThan(days: Int) throws {
        let cutoff = Calendar.current.date(byAdding: .day, value: -days, to: Date())!
        try dbPool.write { db in
            try db.execute(
                sql: "DELETE FROM raw_events WHERE created_at < ?",
                arguments: [cutoff]
            )
        }
    }
}
