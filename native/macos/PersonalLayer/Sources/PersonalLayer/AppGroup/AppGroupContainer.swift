import Foundation
import CryptoKit

/// App Group shared container for Personal Layer v4.
/// Enables macOS daemon, Safari extension, and helper processes to share state.
///
/// Architecture: group.dev.contextlayer.shared
/// File: bundle_{userId}.json (AES-256 encrypted with device key)
final class AppGroupContainer {
    static let shared = AppGroupContainer()
    static let groupIdentifier = "group.dev.contextlayer.shared"
    static let bundleFileName = "bundle_{userId}.json"

    private let containerURL: URL
    private let deviceKey: SymmetricKey

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

        // Derive device key from Keychain
        self.deviceKey = Self.deriveDeviceKey()
    }

    private static func deriveDeviceKey() -> SymmetricKey {
        let keyTag = "com.personalayer.device-key"
        let query: [String: Any] = [
            kSecClass as String: kSecClassKey,
            kSecAttrApplicationTag as String: keyTag.data(using: .utf8)!,
            kSecAttrKeySizeInBits as String: 256,
            kSecReturnData as String: true
        ]
        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        if status == errSecSuccess, let data = result as? Data {
            return SymmetricKey(data: data)
        }
        // Generate new key
        var newKeyData = Data(count: 32)
        let genStatus = newKeyData.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 32, $0.baseAddress!) }
        guard genStatus == errSecSuccess else {
            // Derive from machine identifier as absolute fallback
            let identifier = IOPlatformUUID() ?? "fallback-device-id"
            let derived = SHA256.hash(data: identifier.data(using: .utf8)!)
            return SymmetricKey(data: Data(derived))
        }
        let addQuery: [String: Any] = [
            kSecClass as String: kSecClassKey,
            kSecAttrApplicationTag as String: keyTag.data(using: .utf8)!,
            kSecValueData as String: newKeyData,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]
        SecItemAdd(addQuery as CFDictionary, nil)
        return SymmetricKey(data: newKeyData)
    }

    private func IOPlatformUUID() -> String? {
        // Get the machine UUID via IOKit
        let platformExpert = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("IOPlatformExpertDevice"))
        guard platformExpert != 0 else { return nil }
        defer { IOObjectRelease(platformExpert) }
        guard let uuid = IORegistryEntryCreateCFProperty(platformExpert, kIOPlatformUUIDKey as CFString, kCFAllocatorDefault, 0)?.takeRetainedValue() as? String else {
            return nil
        }
        return uuid
    }

    private func bundleURL(userId: String) -> URL {
        let fileName = Self.bundleFileName.replacingOccurrences(of: "{userId}", with: userId)
        return containerURL.appendingPathComponent(fileName)
    }

    /// Write encrypted bundle to App Group container.
    func writeBundle(_ bundle: [String: Any], userId: String = "default") throws {
        let jsonData = try JSONSerialization.data(withJSONObject: bundle, options: .prettyPrinted)
        let sealedBox = try AES.GCM.seal(jsonData, using: deviceKey)
        let encryptedData = sealedBox.combined!
        try encryptedData.write(to: bundleURL(userId: userId), options: .atomic)
    }

    /// Read and decrypt bundle from App Group container.
    func readBundle(userId: String = "default") throws -> [String: Any] {
        let encryptedData = try Data(contentsOf: bundleURL(userId: userId))
        let sealedBox = try AES.GCM.SealedBox(combined: encryptedData)
        let decryptedData = try AES.GCM.open(sealedBox, using: deviceKey)
        guard let dict = try JSONSerialization.jsonObject(with: decryptedData) as? [String: Any] else {
            throw AppGroupError.invalidBundle
        }
        return dict
    }

    func bundleFileURL(userId: String = "default") -> URL {
        bundleURL(userId: userId)
    }
}

enum AppGroupError: Error {
    case invalidBundle
    case encryptionFailed
    case keyDerivationFailed
}
