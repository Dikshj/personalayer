import GRDB
import Foundation

final class GRDBDatabase {
    static let shared = GRDBDatabase()
    let dbPool: DatabasePool

    private init() {
        let fileManager = FileManager.default
        let appSupport = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let dir = appSupport.appendingPathComponent("PersonalLayer", isDirectory: true)
        try? fileManager.createDirectory(at: dir, withIntermediateDirectories: true)

        // Prefer App Group shared path if available (iOS extensions need this)
        let appGroupURL = AppGroupContainer.shared.sharedDatabaseURL()
        let dbURL = fileManager.fileExists(atPath: appGroupURL.deletingLastPathComponent().path)
            ? appGroupURL
            : dir.appendingPathComponent("personalayer.sqlite")

        var config = Configuration()
        config.prepareDatabase { db in
            db.add(function: .unicodeLower)
        }
        dbPool = try! DatabasePool(path: dbURL.path, configuration: config)
        try! migrate()
    }

    private func migrate() throws {
        var migrator = DatabaseMigrator()

        migrator.registerMigration("v1_raw_events") { db in
            try db.create(table: "raw_event") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("eventType", .text).notNull()
                t.column("payload", .text).notNull()
                t.column("createdAt", .datetime).notNull().defaults(to: Date())
                t.column("privacyFiltered", .boolean).notNull().defaults(to: false)
                t.column("connectorType", .text)
            }
        }

        migrator.registerMigration("v2_kg_nodes") { db in
            try db.create(table: "kg_node") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("entityId", .text).notNull().unique()
                t.column("entityType", .text).notNull()
                t.column("label", .text).notNull()
                t.column("attributes", .text).notNull().defaults(to: "{}")
                t.column("embedding", .blob)
                t.column("tier", .text).notNull().defaults(to: "HOT")
                t.column("signalStrength", .double).notNull().defaults(to: 1.0)
                t.column("lastAccessedAt", .datetime).notNull().defaults(to: Date())
                t.column("createdAt", .datetime).notNull().defaults(to: Date())
                t.column("updatedAt", .datetime).notNull().defaults(to: Date())
            }
        }

        migrator.registerMigration("v3_kg_edges") { db in
            try db.create(table: "kg_edge") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("sourceEntityId", .text).notNull()
                t.column("targetEntityId", .text).notNull()
                t.column("relationType", .text).notNull()
                t.column("weight", .double).notNull().defaults(to: 1.0)
                t.column("evidence", .text).notNull().defaults(to: "[]")
                t.column("createdAt", .datetime).notNull().defaults(to: Date())
            }
        }

        migrator.registerMigration("v4_temporal_chains") { db in
            try db.create(table: "temporal_chain") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("chainType", .text).notNull()
                t.column("sequence", .text).notNull()
                t.column("startDate", .datetime).notNull()
                t.column("endDate", .datetime).notNull()
                t.column("createdAt", .datetime).notNull().defaults(to: Date())
            }
        }

        migrator.registerMigration("v5_domain_approvals") { db in
            try db.create(table: "domain_approval") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("domain", .text).notNull().unique()
                t.column("isApproved", .boolean).notNull().defaults(to: false)
                t.column("approvedAt", .datetime).notNull().defaults(to: Date())
            }
        }

        migrator.registerMigration("v6_shared_bundles") { db in
            try db.create(table: "shared_bundle") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("userId", .text).notNull().unique()
                t.column("bundleJson", .text).notNull().defaults(to: "{}")
                t.column("updatedAt", .datetime).notNull().defaults(to: Date())
            }
        }

        migrator.registerMigration("v7_compression") { db in
            try db.alter(table: "kg_node") { t in
                t.add(column: "isCompressed", .boolean).notNull().defaults(to: false)
                t.add(column: "uncompressedSize", .integer)
            }
        }

        migrator.registerMigration("v8_encrypted_raw_events") { db in
            try db.alter(table: "raw_event") { t in
                t.add(column: "encryptedPayload", .blob)
                t.add(column: "nonce", .blob)
            }
        }

        migrator.registerMigration("v9_pcl_apps") { db in
            try db.create(table: "pcl_app") { t in
                t.column("app_id", .text).primaryKey()
                t.column("name", .text).notNull()
                t.column("allowed_layers", .text).notNull().defaults(to: "[]")
                t.column("created_at", .datetime).notNull().defaults(to: Date())
                t.column("updated_at", .datetime).notNull().defaults(to: Date())
            }
        }

        migrator.registerMigration("v10_pcl_permissions") { db in
            try db.create(table: "pcl_permission") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("user_id", .text).notNull()
                t.column("app_id", .text).notNull()
                t.column("scopes", .text).notNull().defaults(to: "[]")
                t.column("is_active", .boolean).notNull().defaults(to: true)
                t.column("created_at", .datetime).notNull().defaults(to: Date())
                t.column("updated_at", .datetime).notNull().defaults(to: Date())
                t.uniqueKey(["user_id", "app_id"])
            }
        }

        migrator.registerMigration("v11_pcl_integrations") { db in
            try db.create(table: "pcl_integration") { t in
                t.column("source", .text).primaryKey()
                t.column("name", .text).notNull()
                t.column("scopes", .text).notNull().defaults(to: "[]")
                t.column("status", .text).notNull().defaults(to: "pending")
                t.column("metadata", .text).notNull().defaults(to: "{}")
                t.column("sync_cursor", .text).notNull().defaults(to: "{}")
                t.column("last_sync_at", .datetime)
                t.column("next_sync_after", .integer)
                t.column("items_synced", .integer).notNull().defaults(to: 0)
                t.column("auth_status", .text).notNull().defaults(to: "pending")
                t.column("auth_expires_at", .datetime)
                t.column("account_hint", .text)
                t.column("created_at", .datetime).notNull().defaults(to: Date())
                t.column("updated_at", .datetime).notNull().defaults(to: Date())
            }
        }

        migrator.registerMigration("v12_push_tokens") { db in
            try db.create(table: "push_token") { t in
                t.column("id", .text).primaryKey()
                t.column("user_id", .text).notNull()
                t.column("device_id", .text).notNull()
                t.column("apns_token", .text).notNull()
                t.column("platform", .text).notNull()
                t.column("environment", .text).notNull().defaults(to: "sandbox")
                t.column("is_active", .boolean).notNull().defaults(to: true)
                t.column("revoked_at", .datetime)
                t.column("created_at", .datetime).notNull().defaults(to: Date())
                t.uniqueKey(["user_id", "device_id"])
            }
        }

        migrator.registerMigration("v13_notification_routes") { db in
            try db.create(table: "notification_route") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("user_id", .text).notNull()
                t.column("device_id", .text).notNull()
                t.column("push_token_id", .text).notNull()
                t.column("notification_type", .text).notNull()
                t.column("scheduled_at", .datetime).notNull().defaults(to: Date())
                t.column("sent_at", .datetime)
                t.column("created_at", .datetime).notNull().defaults(to: Date())
            }
        }

        migrator.registerMigration("v14_query_log") { db in
            try db.create(table: "query_log") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("app_id", .text).notNull()
                t.column("user_id", .text).notNull()
                t.column("purpose", .text).notNull()
                t.column("requested_layers", .text).notNull().defaults(to: "[]")
                t.column("returned_layers", .text).notNull().defaults(to: "[]")
                t.column("feature_ids", .text).notNull().defaults(to: "[]")
                t.column("status", .text).notNull()
                t.column("reason", .text)
                t.column("created_at", .datetime).notNull().defaults(to: Date())
            }
        }

        migrator.registerMigration("v15_feature_signals") { db in
            try db.create(table: "feature_signal") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("user_id", .text).notNull()
                t.column("app_id", .text).notNull()
                t.column("feature_id", .text).notNull()
                t.column("feature_name", .text).notNull()
                t.column("use_count", .integer).notNull().defaults(to: 0)
                t.column("last_used_at", .datetime)
                t.column("recency_score", .double).notNull().defaults(to: 0.0)
                t.column("tier", .text).notNull().defaults(to: "HOT")
                t.column("is_synthetic", .boolean).notNull().defaults(to: false)
                t.column("created_at", .datetime).notNull().defaults(to: Date())
                t.column("updated_at", .datetime).notNull().defaults(to: Date())
            }
        }

        migrator.registerMigration("v16_privacy_boundaries") { db in
            try db.create(table: "privacy_boundary") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("user_id", .text).notNull()
                t.column("boundary_type", .text).notNull()
                t.column("target", .text).notNull()
                t.column("reason", .text)
                t.column("is_active", .boolean).notNull().defaults(to: true)
                t.column("revoked_at", .datetime)
                t.column("created_at", .datetime).notNull().defaults(to: Date())
            }
        }

        try migrator.migrate(dbPool)
    }

    // MARK: - Raw Events

    func insertRawEvent(type: String, payload: [String: Any], connector: String? = nil) throws {
        let payloadStr = String(data: try JSONSerialization.data(withJSONObject: payload), encoding: .utf8)!
        var event = RawEvent(
            id: nil,
            eventType: type,
            payload: payloadStr,
            createdAt: Date(),
            privacyFiltered: false,
            connectorType: connector
        )
        try dbPool.write { db in
            try event.insert(db)
        }
    }

    func recentRawEvents(limit: Int = 100) throws -> [RawEvent] {
        try dbPool.read { db in
            try RawEvent.limit(limit).order(Column("createdAt").desc).fetchAll(db)
        }
    }

    func markPrivacyFiltered() throws {
        try dbPool.write { db in
            try db.execute(
                sql: """
                UPDATE raw_event SET privacyFiltered = true
                WHERE privacyFiltered = false
                AND (
                    payload LIKE '%password%' OR
                    payload LIKE '%ssn%' OR
                    payload LIKE '%credit_card%' OR
                    payload LIKE '%secret%' OR
                    payload LIKE '%token%'
                )
                """
            )
        }
    }

    func deleteRawEventsOlderThan(days: Int) throws {
        let cutoff = Calendar.current.date(byAdding: .day, value: -days, to: Date())!
        try dbPool.write { db in
            try RawEvent.filter(Column("createdAt") < cutoff).deleteAll(db)
        }
    }

    // MARK: - Knowledge Graph

    func upsertNode(entityId: String, type: String, label: String, attributes: [String: Any], embedding: [Float]? = nil) throws {
        let attrStr = String(data: try JSONSerialization.data(withJSONObject: attributes), encoding: .utf8)!
        let embeddingData = embedding.flatMap {
            var data = Data()
            for f in $0 {
                withUnsafeBytes(of: f) { data.append(contentsOf: $0) }
            }
            return data
        }

        try dbPool.write { db in
            if var existing = try KGNode.filter(Column("entityId") == entityId).fetchOne(db) {
                existing.label = label
                existing.attributes = attrStr
                existing.embedding = embeddingData
                existing.signalStrength = min(existing.signalStrength + 0.1, 1.0)
                existing.lastAccessedAt = Date()
                existing.updatedAt = Date()
                try existing.update(db)
            } else {
                var node = KGNode(
                    id: nil,
                    entityId: entityId,
                    entityType: type,
                    label: label,
                    attributes: attrStr,
                    embedding: embeddingData,
                    tier: "HOT",
                    signalStrength: 1.0,
                    lastAccessedAt: Date(),
                    createdAt: Date(),
                    updatedAt: Date()
                )
                try node.insert(db)
            }
        }
    }

    func nodesByTier(_ tier: MemoryTier, limit: Int = 100) throws -> [KGNode] {
        try dbPool.read { db in
            try KGNode.filter(Column("tier") == tier.rawValue).limit(limit).fetchAll(db)
        }
    }

    func updateNodeTier(entityId: String, tier: MemoryTier) throws {
        try dbPool.write { db in
            try db.execute(
                sql: "UPDATE kg_node SET tier = ?, updatedAt = ? WHERE entityId = ?",
                arguments: [tier.rawValue, Date(), entityId]
            )
        }
    }

    func insertEdge(source: String, target: String, relation: String, weight: Double = 1.0, evidence: [String] = []) throws {
        var edge = KGEdge(
            id: nil,
            sourceEntityId: source,
            targetEntityId: target,
            relationType: relation,
            weight: weight,
            evidence: String(data: try JSONSerialization.data(withJSONObject: evidence), encoding: .utf8)!,
            createdAt: Date()
        )
        try dbPool.write { db in
            try edge.insert(db)
        }
    }

    // MARK: - Temporal Chains

    func insertTemporalChain(type: String, sequence: [(entityId: String, timestamp: Date)]) throws {
        let seqArray = sequence.map { ["entityId": $0.entityId, "timestamp": ISO8601DateFormatter().string(from: $0.timestamp)] }
        let seqStr = String(data: try JSONSerialization.data(withJSONObject: seqArray), encoding: .utf8)!
        var chain = TemporalChain(
            id: nil,
            chainType: type,
            sequence: seqStr,
            startDate: sequence.first?.timestamp ?? Date(),
            endDate: sequence.last?.timestamp ?? Date(),
            createdAt: Date()
        )
        try dbPool.write { db in
            try chain.insert(db)
        }
    }

    func cleanupTemporalChains(olderThanDays: Int) throws {
        let cutoff = Calendar.current.date(byAdding: .day, value: -olderThanDays, to: Date())!
        try dbPool.write { db in
            try TemporalChain.filter(Column("createdAt") < cutoff).deleteAll(db)
        }
    }

    // MARK: - Shared Bundle

    func loadSharedBundle() throws -> [String: Any] {
        try dbPool.read { db in
            if let bundle = try SharedBundle.fetchOne(db) {
                return (try? JSONSerialization.jsonObject(with: bundle.bundleJson.data(using: .utf8)!) as? [String: Any]) ?? [:]
            }
            return [:]
        }
    }

    func saveSharedBundle(_ bundle: [String: Any], userId: String = "default") throws {
        let json = String(data: try JSONSerialization.data(withJSONObject: bundle), encoding: .utf8)!
        try dbPool.write { db in
            if var existing = try SharedBundle.filter(Column("userId") == userId).fetchOne(db) {
                existing.bundleJson = json
                existing.updatedAt = Date()
                try existing.update(db)
            } else {
                var b = SharedBundle(id: nil, userId: userId, bundleJson: json, updatedAt: Date())
                try b.insert(db)
            }
        }
    }
}
