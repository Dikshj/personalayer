import Foundation

/// Reads / writes the shared context bundle into the App Group container.
/// Enables the macOS daemon, Safari extension, and any helper processes to share state.
final class AppGroupContainer {
    static let shared = AppGroupContainer()
    static let groupIdentifier = "group.com.personalayer"

    private let containerURL: URL

    private init() {
        if let url = FileManager.default
            .containerURL(forSecurityApplicationGroupIdentifier: Self.groupIdentifier) {
            self.containerURL = url
        } else {
            // Fallback to local Application Support when App Group entitlement is missing
            let appSupport = FileManager.default
                .urls(for: .applicationSupportDirectory, in: .userDomainMask)
                .first!
            self.containerURL = appSupport.appendingPathComponent("PersonalLayer", isDirectory: true)
            try? FileManager.default.createDirectory(at: self.containerURL, withIntermediateDirectories: true)
        }
    }

    var bundleDirectory: URL {
        containerURL
    }

    func writeBundle(_ bundle: [String: Any]) throws {
        let fileURL = containerURL.appendingPathComponent("shared_bundle.json")
        let data = try JSONSerialization.data(withJSONObject: bundle, options: .prettyPrinted)
        try data.write(to: fileURL, options: .atomic)
    }

    func readBundle() throws -> [String: Any] {
        let fileURL = containerURL.appendingPathComponent("shared_bundle.json")
        let data = try Data(contentsOf: fileURL)
        guard let dict = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw AppGroupError.invalidBundle
        }
        return dict
    }

    func bundleFileURL() -> URL {
        containerURL.appendingPathComponent("shared_bundle.json")
    }
}

enum AppGroupError: Error {
    case invalidBundle
}
