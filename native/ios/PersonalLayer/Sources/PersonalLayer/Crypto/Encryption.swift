import CryptoKit
import Foundation

enum Encryption {
    static func deriveKey(from password: String, salt: Data) -> SymmetricKey {
        let passwordData = Data(password.utf8)
        return HKDF<SHA256>.deriveKey(
            inputKeyMaterial: .init(data: passwordData),
            salt: salt,
            outputByteCount: 32
        )
    }
    static func encrypt(data: Data, using key: SymmetricKey) throws -> Data {
        let nonce = AES.GCM.Nonce()
        return try AES.GCM.seal(data, using: key, nonce: nonce).combined!
    }
    static func decrypt(data: Data, using key: SymmetricKey) throws -> Data {
        try AES.GCM.open(AES.GCM.SealedBox(combined: data), using: key)
    }
}
