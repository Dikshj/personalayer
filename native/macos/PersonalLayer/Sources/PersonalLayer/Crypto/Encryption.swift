import CryptoKit
import Foundation

enum Encryption {
    static func deriveKey(from password: String, salt: Data) -> SymmetricKey {
        let passwordData = Data(password.utf8)
        let key = HKDF<SHA256>.deriveKey(inputKeyMaterial: .init(data: passwordData),
                                          salt: salt,
                                          outputByteCount: 32)
        return key
    }

    static func encrypt(data: Data, using key: SymmetricKey) throws -> Data {
        let nonce = AES.GCM.Nonce()
        let sealed = try AES.GCM.seal(data, using: key, nonce: nonce)
        return sealed.combined!
    }

    static func decrypt(data: Data, using key: SymmetricKey) throws -> Data {
        let sealed = try AES.GCM.SealedBox(combined: data)
        return try AES.GCM.open(sealed, using: key)
    }
}
