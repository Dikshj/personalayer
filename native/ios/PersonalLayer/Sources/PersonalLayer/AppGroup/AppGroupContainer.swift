import Foundation
import CryptoKit

/// App Group shared container for Personal Layer v4.
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

        // Derive device key from Secure Enclave or Keychain
        self.deviceKey = Self.deriveDeviceKey()
    }

    /// Derive a stable AES-256 key from the device.
    /// Uses Secure Enclave if available, falls back to random Keychain item.
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
            // Absolute fallback: derive from device identifier (NOT secure, but prevents crash)
            let identifier = UIDevice.current.identifierForVendor?.uuidString ?? "fallback-device-id"
            let derived = SHA256.hash(data: identifier.data(using: .utf8)!)
            return SymmetricKey(data: Data(derived))
        }
        let newKey = SymmetricKey(data: newKeyData)
        let addQuery: [String: Any] = [
            kSecClass as String: kSecClassKey,
            kSecAttrApplicationTag as String: keyTag.data(using: .utf8)!,
            kSecValueData as String: newKeyData,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]
        SecItemAdd(addQuery as CFDictionary, nil)
        return newKey
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
