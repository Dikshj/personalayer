import Foundation
import CryptoKit

struct BundleEncryption {
    private static let saltFileName = "device_salt.bin"

    static func encryptBundle(_ bundle: [String: Any], userId: String, passphrase: String, to directory: URL) throws {
        let salt = try loadOrCreateSalt(in: directory)
        let key = Encryption.deriveKey(from: passphrase, salt: salt)
        let jsonData = try JSONSerialization.data(withJSONObject: bundle)
        let encrypted = try Encryption.encrypt(data: jsonData, using: key)
        try encrypted.write(to: directory.appendingPathComponent("bundle_\(userId).json.enc"))
    }

    static func decryptBundle(userId: String, passphrase: String, from directory: URL) throws -> [String: Any] {
        let salt = try loadOrCreateSalt(in: directory)
        let key = Encryption.deriveKey(from: passphrase, salt: salt)
        let encrypted = try Data(contentsOf: directory.appendingPathComponent("bundle_\(userId).json.enc"))
        let decrypted = try Encryption.decrypt(data: encrypted, using: key)
        guard let dict = try JSONSerialization.jsonObject(with: decrypted) as? [String: Any] else {
            throw BundleEncryptionError.invalidFormat
        }
        return dict
    }

    private static func loadOrCreateSalt(in directory: URL) throws -> Data {
        let saltURL = directory.appendingPathComponent(saltFileName)
        if let data = try? Data(contentsOf: saltURL), data.count == 16 { return data }
        var salt = Data(count: 16)
        let result = salt.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 16, $0.baseAddress!) }
        guard result == errSecSuccess else { throw BundleEncryptionError.randomGenerationFailed }
        try salt.write(to: saltURL)
        return salt
    }
}

enum BundleEncryptionError: Error {
    case invalidFormat
    case randomGenerationFailed
}
