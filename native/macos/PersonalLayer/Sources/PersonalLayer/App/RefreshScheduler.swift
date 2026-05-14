import BackgroundTasks
import Foundation
import Combine

final class RefreshScheduler: ObservableObject {
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
        task.expirationHandler = {
            NSLog("PersonalLayer: refresh task expired")
        }

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

    private func runRefreshPipeline() throws {
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
        let connectors: [(String, String, (String) async throws -> [RawEvent])] = [
            ("google", "gmail", { t in try await GmailClient.syncMetadata(token: t) }),
            ("google", "calendar", { t in try await CalendarClient.sync7DayWindow(token: t) }),
            ("google", "youtube", { t in try await YouTubeClient.metadata(token: t) }),
            ("spotify", "spotify", { t in try await SpotifyClient.recentlyPlayed(token: t) }),
            ("notion", "notion", { t in try await NotionClient.search(token: t) })
        ]

        for (providerName, _, syncFn) in connectors {
            guard let stored = OAuthTokenStore.load(provider: providerName) else { continue }
            do {
                let events = try runAsyncAndBlock { try await syncFn(stored.token) }
                try database.dbPool.write { db in
                    for var event in events {
                        try event.insert(db)
                    }
                }
            } catch {
                NSLog("PersonalLayer: connector sync failed for \(providerName): \(error)")
            }
        }

        // Google Fit (single aggregate, uses Google token)
        if let stored = OAuthTokenStore.load(provider: "google") {
            do {
                if let event = try runAsyncAndBlock({ try await GoogleFitClient.aggregateSteps(token: stored.token) }) {
                    if let payload = try? JSONSerialization.jsonObject(with: event.payload.data(using: .utf8) ?? Data()) as? [String: Any] {
                        try database.insertRawEvent(type: event.eventType, payload: payload)
                    }
                }
            } catch {
                NSLog("PersonalLayer: Google Fit sync failed: \(error)")
            }
        }
    }

    private func classifySignals() throws {
        let events = try database.recentRawEvents(limit: 1000)
        for event in events {
            let embedding = try model.encode(text: event.payload)
            _ = embedding
            // TODO: classify and store signal strength
        }
    }

    private func synthesizeProfile() throws { /* TODO */ }
    private func runDecayEngine() throws { /* TODO */ }
    private func buildInductiveMemory() throws { /* TODO */ }
    private func buildReflectiveMemory() throws { /* TODO */ }
    private func maintainTiers() throws { /* TODO */ }

    private func writeSharedBundle() throws {
        let bundle = try database.loadSharedBundle()
        let appGroup = AppGroupContainer.shared
        try appGroup.writeBundle(bundle)
    }

    private func generateDailyInsight() throws { /* TODO */ }
    private func cleanupTemporalChains() throws { /* TODO */ }

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
