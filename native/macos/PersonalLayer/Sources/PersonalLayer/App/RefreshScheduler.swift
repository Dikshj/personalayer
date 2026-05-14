import BackgroundTasks
import Foundation

/// Schedules and handles the daily 3 AM local refresh.
/// Maps to the Python scheduler’s `contextlayer_daily_refresh` job.
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
        schedule() // Reschedule next 3 AM before doing work

        let queue = DispatchQueue(label: "com.personalayer.refresh", qos: .background)
        task.expirationHandler = {
            // Cleanup if killed mid-refresh
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

    /// 11-step daily refresh pipeline (mirrors Python backend).
    private func runRefreshPipeline() throws {
        // 1. Connector sync (placeholder — would call Gmail/Calendar/etc. APIs)
        try syncConnectors()

        // 2. Privacy filter check
        try database.markPrivacyFiltered()

        // 3. Signal classifier (embedding-based)
        try classifySignals()

        // 4. Profile synthesizer
        try synthesizeProfile()

        // 5. Decay engine
        try runDecayEngine()

        // 6. Inductive memory
        try buildInductiveMemory()

        // 7. Reflective memory
        try buildReflectiveMemory()

        // 8. Tier maintenance
        try maintainTiers()

        // 9. Write shared context file
        try writeSharedBundle()

        // 10. Daily insight
        try generateDailyInsight()

        // 11. Raw event / temporal-chain cleanup (> 7 days)
        try cleanupOldEvents()
    }

    private func syncConnectors() throws {
        // TODO: Gmail metadata, Calendar 7-day window, Spotify recently played, etc.
        NSLog("PersonalLayer: connector sync placeholder")
    }

    private func classifySignals() throws {
        let events = try database.recentRawEvents(limit: 1000)
        for event in events {
            let embedding = try model.encode(text: event.payload)
            // TODO: classify and store signal strength
            _ = embedding
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
        let appGroup = AppGroupContainer.shared
        try appGroup.writeBundle(bundle)
    }

    private func generateDailyInsight() throws {
        // TODO: generate insight text, store locally
    }

    private func cleanupOldEvents() throws {
        try database.deleteRawEventsOlderThan(days: 7)
    }

    private static func next3AM() -> Date {
        var components = Calendar.current.dateComponents(
            [.year, .month, .day],
            from: Date()
        )
        components.hour = refreshHour
        components.minute = refreshMinute
        components.second = 0
        var date = Calendar.current.date(from: components)!
        if date <= Date() {
            date = Calendar.current.date(byAdding: .day, value: 1, to: date)!
        }
        return date
    }
}
