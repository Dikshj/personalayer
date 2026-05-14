import Foundation

/// Stores incremental sync cursors in UserDefaults per connector.
/// Enables delta sync instead of full sync on each refresh.
struct ConnectorCursorStore {
    private static let prefix = "com.personalayer.cursor."

    static func save(cursor: String, for connector: String) {
        UserDefaults.standard.set(cursor, forKey: "\(prefix)\(connector)")
    }

    static func load(for connector: String) -> String? {
        UserDefaults.standard.string(forKey: "\(prefix)\(connector)")
    }

    static func clear(for connector: String) {
        UserDefaults.standard.removeObject(forKey: "\(prefix)\(connector)")
    }

    static func saveTimestamp(for connector: String) {
        UserDefaults.standard.set(Date().timeIntervalSince1970, forKey: "\(prefix)\(connector).lastSync")
    }

    static func lastSyncTimestamp(for connector: String) -> TimeInterval {
        UserDefaults.standard.double(forKey: "\(prefix)\(connector).lastSync")
    }
}
