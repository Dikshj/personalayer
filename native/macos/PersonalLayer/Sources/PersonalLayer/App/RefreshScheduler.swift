import BackgroundTasks
import Foundation

final class RefreshScheduler {
    static let shared = RefreshScheduler()
    static let taskIdentifier = "com.personalayer.dailyrefresh"
    static let refreshHour = 3
    static let refreshMinute = 0

    private let database: GRDBDatabase
    private let model: EmbeddingModel

    init(database: GRDBDatabase = .shared,
         model: EmbeddingModel = .shared) {
        self.database = database
        self.model = model
    }

    func register() {
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: Self.taskIdentifier,
            using: nil
        ) { task in
            self.handle(task: task as! BGAppRefreshTask)
        }
    }

    func schedule() {
        let request = BGAppRefreshTaskRequest(identifier: Self.taskIdentifier)
        request.earliestBeginDate = Self.next3AM()
        do {
            try BGTaskScheduler.shared.submit(request)
            NSLog("PersonalLayer: scheduled next refresh at \(request.earliestBeginDate!)")
        } catch {
            NSLog("PersonalLayer: failed to schedule refresh: \(error)")
        }
    }

    func handle(task: BGAppRefreshTask) {
        schedule()
        let queue = DispatchQueue(label: "com.personalayer.refresh", qos: .background)
        task.expirationHandler = { NSLog("PersonalLayer: refresh task expired") }
        queue.async {
            do {
                try self.runRefreshPipeline()
                task.setTaskCompleted(success: true)
            } catch {
                NSLog("PersonalLayer: refresh failed: \(error)")
                task.setTaskCompleted(success: false)
            }
        }
    }

    // MARK: - 11-Step Pipeline

    func runRefreshPipeline() throws {
        try syncConnectors()
        try runPrivacyFilter()
        try classifySignals()
        try synthesizeProfile()
        try runDecayEngine()
        try buildInductiveMemory()
        try buildReflectiveMemory()
        try maintainTiers()
        try writeSharedBundle()
        try generateDailyInsight()
        try cleanupOldData()
    }

    private func syncConnectors() throws {
        let connectorMap: [(provider: String, syncFn: (String) async throws -> [RawEvent])] = [
            ("google", { t in try await GmailClient.syncMetadata(token: t) }),
            ("google", { t in try await CalendarClient.sync7DayWindow(token: t) }),
            ("google", { t in try await YouTubeClient.metadata(token: t) }),
            ("spotify", { t in try await SpotifyClient.recentlyPlayed(token: t) }),
            ("notion", { t in try await NotionClient.search(token: t) })
        ]

        for (providerName, syncFn) in connectorMap {
            guard let stored = OAuthTokenStore.load(provider: providerName) else { continue }
            let token = try refreshIfNeeded(provider: providerName, token: stored)
            do {
                let events = try runAsyncAndBlock { try await syncFn(token) }
                try database.dbPool.write { db in
                    for var event in events {
                        try event.insert(db)
                    }
                }
            } catch {
                NSLog("PersonalLayer: connector sync failed for \(providerName): \(error)")
            }
        }

        if let stored = OAuthTokenStore.load(provider: "google") {
            let token = try refreshIfNeeded(provider: "google", token: stored)
            do {
                if let event = try runAsyncAndBlock({ try await GoogleFitClient.aggregateSteps(token: token) }) {
                    if let payload = try? JSONSerialization.jsonObject(with: event.payload.data(using: .utf8) ?? Data()) as? [String: Any] {
                        try database.insertRawEvent(type: event.eventType, payload: payload)
                    }
                }
            } catch {
                NSLog("PersonalLayer: Google Fit sync failed: \(error)")
            }
        }
    }

    private func refreshIfNeeded(provider: String, token: OAuthTokenStore.TokenInfo) throws -> String {
        guard let obtainedAt = token.metadata["obtained_at"] as? String,
              let expiresIn = token.metadata["expires_in"] as? Int,
              let date = ISO8601DateFormatter().date(from: obtainedAt),
              expiresIn > 0 else {
            return token.token
        }
        if Date().timeIntervalSince(date) > Double(expiresIn) - 300 {
            // Token expiring within 5 minutes — refresh
            if let oauthProvider = oauthProviderForName(provider) {
                return try runAsyncAndBlock { try await OAuthTokenExchange.shared.refreshToken(provider: oauthProvider) }
            }
        }
        return token.token
    }

    private func oauthProviderForName(_ name: String) -> OAuthProvider? {
        switch name {
        case "google": return .google
        case "spotify": return .spotify
        case "notion": return .notion
        default: return nil
        }
    }

    private func runPrivacyFilter() throws {
        try database.markPrivacyFiltered()
    }

    private func classifySignals() throws {
        let events = try database.recentRawEvents(limit: 1000).filter { !$0.privacyFiltered }
        for event in events {
            let embedding = try model.encode(text: event.payload)
            let entityId = "event_\(event.id ?? 0)"
            let attributes: [String: Any] = [
                "eventType": event.eventType,
                "connectorType": event.connectorType ?? "unknown",
                "embedding_dim": embedding.count
            ]
            try database.upsertNode(entityId: entityId, type: "raw_event", label: event.eventType, attributes: attributes, embedding: embedding)
        }
    }

    private func synthesizeProfile() throws {
        // Aggregate events by connector type and time window
        let events = try database.recentRawEvents(limit: 5000)
        let byConnector = Dictionary(grouping: events) { $0.connectorType ?? "unknown" }
        for (connector, connectorEvents) in byConnector {
            let dailyCounts = Dictionary(grouping: connectorEvents) {
                Calendar.current.startOfDay(for: $0.createdAt)
            }.mapValues { $0.count }
            let attributes: [String: Any] = [
                "connector": connector,
                "totalEvents": connectorEvents.count,
                "dailyCounts": dailyCounts.mapKeys { ISO8601DateFormatter().string(from: $0) }
            ]
            try database.upsertNode(entityId: "profile_\(connector)", type: "profile_segment", label: "\(connector) Profile", attributes: attributes)
        }
    }

    private func runDecayEngine() throws {
        // Reduce signal strength for nodes not accessed recently
        let now = Date()
        try database.dbPool.write { db in
            try db.execute(
                sql: """
                UPDATE kg_node SET
                    signalStrength = max(0.0, signalStrength * pow(0.95, julianday(?) - julianday(lastAccessedAt))),
                    updatedAt = ?
                WHERE tier != 'COLD'
                """,
                arguments: [now, now]
            )
        }
    }

    private func buildInductiveMemory() throws {
        // Find temporal patterns: sequences of related events within 1-hour windows
        let events = try database.recentRawEvents(limit: 2000)
        let calendar = Calendar.current
        let hourlyWindows = Dictionary(grouping: events) {
            calendar.dateInterval(of: .hour, for: $0.createdAt)?.start ?? $0.createdAt
        }
        for (_, windowEvents) in hourlyWindows where windowEvents.count >= 3 {
            let sequence = windowEvents.map { (entityId: "event_\($0.id ?? 0)", timestamp: $0.createdAt) }
            try database.insertTemporalChain(type: "hourly_window", sequence: sequence)
        }
    }

    private func buildReflectiveMemory() throws {
        // High-level summary: top connectors, peak activity day
        let events = try database.recentRawEvents(limit: 5000)
        let byConnector = Dictionary(grouping: events) { $0.connectorType ?? "unknown" }
        let topConnectors = byConnector.sorted { $0.value.count > $1.value.count }.prefix(3).map { $0.key }
        let dailyCounts = Dictionary(grouping: events) { calendar.startOfDay(for: $0.createdAt) }.mapValues { $0.count }
        let peakDay = dailyCounts.max { $0.value < $1.value }?.key

        let summary: [String: Any] = [
            "topConnectors": topConnectors,
            "peakActivityDay": peakDay.map { ISO8601DateFormatter().string(from: $0) } ?? "unknown",
            "totalEvents": events.count
        ]
        try database.upsertNode(entityId: "reflective_summary", type: "reflective_memory", label: "Daily Reflection", attributes: summary)
    }

    private func maintainTiers() throws {
        // HOT: accessed within 1 day, strength > 0.7
        // WARM: accessed within 7 days, strength > 0.3
        // COOL: accessed within 30 days
        // COLD: everything else
        let now = Date()
        try database.dbPool.write { db in
            try db.execute(
                sql: "UPDATE kg_node SET tier = 'HOT' WHERE julianday(?) - julianday(lastAccessedAt) < 1 AND signalStrength > 0.7",
                arguments: [now]
            )
            try db.execute(
                sql: "UPDATE kg_node SET tier = 'WARM' WHERE tier != 'HOT' AND julianday(?) - julianday(lastAccessedAt) < 7 AND signalStrength > 0.3",
                arguments: [now]
            )
            try db.execute(
                sql: "UPDATE kg_node SET tier = 'COOL' WHERE tier NOT IN ('HOT','WARM') AND julianday(?) - julianday(lastAccessedAt) < 30",
                arguments: [now]
            )
            try db.execute(
                sql: "UPDATE kg_node SET tier = 'COLD' WHERE tier NOT IN ('HOT','WARM','COOL')",
                arguments: []
            )
        }
    }

    private func writeSharedBundle() throws {
        let hotNodes = try database.nodesByTier(.hot, limit: 50)
        let warmNodes = try database.nodesByTier(.warm, limit: 50)
        let coolNodes = try database.nodesByTier(.cool, limit: 30)

        let bundle: [String: Any] = [
            "hot_context": hotNodes.map { ["id": $0.entityId, "label": $0.label, "strength": $0.signalStrength] },
            "warm_context": warmNodes.map { ["id": $0.entityId, "label": $0.label, "strength": $0.signalStrength] },
            "cool_context": coolNodes.map { ["id": $0.entityId, "label": $0.label, "strength": $0.signalStrength] },
            "generated_at": ISO8601DateFormatter().string(from: Date()),
            "version": "v4"
        ]
        try database.saveSharedBundle(bundle)
        try AppGroupContainer.shared.writeBundle(bundle)
    }

    private func generateDailyInsight() throws {
        let nodes = try database.nodesByTier(.hot, limit: 10)
        let connectorCounts = Dictionary(grouping: nodes) {
            (try? JSONSerialization.jsonObject(with: $0.attributes.data(using: .utf8)!) as? [String: Any])?["connectorType"] as? String ?? "unknown"
        }.mapValues { $0.count }
        let insight = "Today you were most active with: \(connectorCounts.sorted { $0.value > $1.value }.prefix(3).map { "\($0.key) (\($0.value))" }.joined(separator: ", "))"
        let attributes: [String: Any] = ["text": insight, "generated_at": ISO8601DateFormatter().string(from: Date())]
        try database.upsertNode(entityId: "daily_insight", type: "insight", label: "Daily Insight", attributes: attributes)
    }

    private func cleanupOldData() throws {
        try database.deleteRawEventsOlderThan(days: 7)
        try database.cleanupTemporalChains(olderThanDays: 30)
    }

    private static func next3AM() -> Date {
        var components = Calendar.current.dateComponents([.year, .month, .day], from: Date())
        components.hour = refreshHour
        components.minute = refreshMinute
        components.second = 0
        var date = Calendar.current.date(from: components)!
        if date <= Date() {
            date = Calendar.current.date(byAdding: .day, value: 1, to: date)!
        }
        return date
    }

    private func runAsyncAndBlock<T>(_ operation: @escaping () async throws -> T) throws -> T {
        let semaphore = DispatchSemaphore(value: 0)
        var result: T?
        var thrownError: Error?
        Task {
            do { result = try await operation() }
            catch { thrownError = error }
            semaphore.signal()
        }
        semaphore.wait()
        if let error = thrownError { throw error }
        return result!
    }
}
