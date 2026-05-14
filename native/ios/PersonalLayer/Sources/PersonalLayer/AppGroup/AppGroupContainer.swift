import Foundation

final class AppGroupContainer {
    static let shared = AppGroupContainer()
    static let groupIdentifier = "group.com.personalayer"

    private let containerURL: URL

    private init() {
        if let url = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: Self.groupIdentifier) {
            self.containerURL = url
        } else {
            let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
            self.containerURL = appSupport.appendingPathComponent("PersonalLayer", isDirectory: true)
            try? FileManager.default.createDirectory(at: self.containerURL, withIntermediateDirectories: true)
        }
    }

    func writeBundle(_ bundle: [String: Any]) throws {
        let url = containerURL.appendingPathComponent("shared_bundle.json")
        let data = try JSONSerialization.data(withJSONObject: bundle, options: .prettyPrinted)
        try data.write(to: url, options: .atomic)
    }

    func readBundle() throws -> [String: Any] {
        let url = containerURL.appendingPathComponent("shared_bundle.json")
        let data = try Data(contentsOf: url)
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
