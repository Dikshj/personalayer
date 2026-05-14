import BackgroundTasks
import Foundation
import Combine

final class RefreshScheduler: ObservableObject {
    static let shared = RefreshScheduler()
    static let taskIdentifier = "com.personalayer.dailyrefresh"

    @Published var isRunning = false
    @Published var nextRefreshFormatted = "Not scheduled"

    private let database = GRDBDatabase.shared
    private let model = EmbeddingModel.shared

    func register() {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: Self.taskIdentifier, using: nil) { task in
            self.handle(task: task as! BGAppRefreshTask)
        }
    }

    func schedule() {
        let request = BGAppRefreshTaskRequest(identifier: Self.taskIdentifier)
        request.earliestBeginDate = next3AM()
        do {
            try BGTaskScheduler.shared.submit(request)
            DispatchQueue.main.async {
                let fmt = DateFormatter()
                fmt.dateStyle = .short
                fmt.timeStyle = .short
                self.nextRefreshFormatted = fmt.string(from: request.earliestBeginDate!)
            }
        } catch {
            DispatchQueue.main.async { self.nextRefreshFormatted = "Failed" }
        }
    }

    private func handle(task: BGAppRefreshTask) {
        schedule()
        DispatchQueue.main.async { self.isRunning = true }
        task.expirationHandler = { DispatchQueue.main.async { self.isRunning = false } }
        DispatchQueue(label: "refresh", qos: .background).async {
            do {
                try self.runPipeline()
                task.setTaskCompleted(success: true)
            } catch {
                task.setTaskCompleted(success: false)
            }
            DispatchQueue.main.async { self.isRunning = false }
        }
    }

    private func runPipeline() throws {
        try syncConnectors()
        try database.markPrivacyFiltered()
        try classifySignals()
        try synthesizeProfile()
        try runDecayEngine()
        try buildInductiveMemory()
        try buildReflectiveMemory()
        try maintainTiers()
        try writeSharedBundle()
        try generateDailyInsight()
        try database.deleteRawEventsOlderThan(days: 7)
        try cleanupTemporalChains()
    }

    private func syncConnectors() throws {
        // Sync all connected connectors
        let connectorTypes: [(ConnectorType, (String) async throws -> [RawEvent])] = [
            (.gmail, { token in try await GmailClient.syncMetadata(token: token) }),
            (.calendar, { token in try await CalendarClient.sync7DayWindow(token: token) }),
            (.spotify, { token in try await SpotifyClient.recentlyPlayed(token: token) }),
            (.youtube, { token in try await YouTubeClient.metadata(token: token) }),
            (.notion, { token in try await NotionClient.search(token: token) })
        ]

        for (type, syncFn) in connectorTypes {
            let providerName = type.oauthProvider.map { String(describing: $0).lowercased() } ?? ""
            guard let stored = OAuthTokenStore.load(provider: providerName) else { continue }

            // Check if token needs refresh
            var token = stored.token
            if let obtainedAt = stored.metadata["obtained_at"] as? String,
               let expiresIn = stored.metadata["expires_in"] as? Int,
               let date = ISO8601DateFormatter().date(from: obtainedAt) {
                if Date().timeIntervalSince(date) > Double(expiresIn) - 300 {
                    // Refresh if expiring within 5 minutes
                    Task {
                        if let provider = type.oauthProvider {
                            token = try await OAuthTokenExchange.shared.refreshToken(provider: provider)
                        }
                    }
                }
            }

            do {
                let events = try runAsyncAndBlock { try await syncFn(token) }
                try database.dbPool.write { db in
                    for event in events {
                        var ev = event
                        try ev.insert(db)
                    }
                }
            } catch {
                print("Connector sync failed for \(type.displayName): \(error)")
            }
        }

        // Google Fit (single aggregate)
        if let stored = OAuthTokenStore.load(provider: "google") {
            do {
                if let event = try runAsyncAndBlock({ try await GoogleFitClient.aggregateSteps(token: stored.token) }) {
                    try database.insertRawEvent(type: event.eventType, payload: (try? JSONSerialization.jsonObject(with: event.payload.data(using: .utf8) ?? Data()) as? [String: Any]) ?? [:])
                }
            } catch {
                print("Google Fit sync failed: \(error)")
            }
        }
    }

    private func classifySignals() throws {
        let events = try database.recentRawEvents(limit: 1000)
        for event in events {
            _ = try model.encode(text: event.payload)
            // TODO: store embedding and classify
        }
    }

    private func synthesizeProfile() throws {
        // TODO: aggregate signals into profile segments
    }

    private func runDecayEngine() throws {
        // TODO: apply decay to tiered memories
    }

    private func buildInductiveMemory() throws {
        // TODO: pattern extraction across temporal chains
    }

    private func buildReflectiveMemory() throws {
        // TODO: high-level reflection summaries
    }

    private func maintainTiers() throws {
        // TODO: HOT → WARM → COOL → COLD transitions
    }

    private func writeSharedBundle() throws {
        let bundle = try database.loadSharedBundle()
        try AppGroupContainer.shared.writeBundle(bundle)
    }

    private func generateDailyInsight() throws {
        // TODO: generate insight text, store locally
    }

    private func cleanupTemporalChains() throws {
        // TODO: delete old temporal chains
    }

    private func next3AM() -> Date {
        var comps = Calendar.current.dateComponents([.year,.month,.day], from: Date())
        comps.hour = 3; comps.minute = 0; comps.second = 0
        var date = Calendar.current.date(from: comps)!
        if date <= Date() { date = Calendar.current.date(byAdding: .day, value: 1, to: date)! }
        return date
    }

    /// Helper to bridge async in sync context (for background task)
    private func runAsyncAndBlock<T>(_ operation: @escaping () async throws -> T) throws -> T {
        let semaphore = DispatchSemaphore(value: 0)
        var result: T?
        var thrownError: Error?
        Task {
            do {
                result = try await operation()
            } catch {
                thrownError = error
            }
            semaphore.signal()
        }
        semaphore.wait()
        if let error = thrownError { throw error }
        return result!
    }
}
