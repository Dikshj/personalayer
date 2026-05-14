import Foundation
import Compression

/// Compression utility for COOL and COLD tier storage.
/// Uses Apple Compression library (lz4/zlib) since zstd is not directly available on iOS.
/// On macOS we can use libzstd via system library. Here we use COMPRESSION_ZSTD if available (iOS 15+),
/// falling back to COMPRESSION_LZ4 for older OS versions.
enum CompressionHelper {
    static let algorithm: compression_algorithm = {
        if #available(iOS 15.0, macOS 12.0, *) {
            // ZSTD is available on iOS 15+ / macOS 12+
            return COMPRESSION_ZSTD
        }
        return COMPRESSION_LZ4_RAW
    }()

    /// Compress data using the selected algorithm.
    static func compress(_ data: Data) throws -> Data {
        guard !data.isEmpty else { return data }
        let algorithm = Self.algorithm

        // Estimate compressed size
        let maxSize = compression_encode_scratch_buffer_size(algorithm)
        var compressed = Data(count: data.count + maxSize)
        let count = data.withUnsafeBytes { source in
            compressed.withUnsafeMutableBytes { dest in
                compression_encode_buffer(
                    dest.baseAddress!.assumingMemoryBound(to: UInt8.self),
                    dest.count,
                    source.baseAddress!.assumingMemoryBound(to: UInt8.self),
                    source.count,
                    nil,
                    algorithm
                )
            }
        }
        guard count > 0 else { throw CompressionError.compressionFailed }
        return compressed.prefix(count)
    }

    /// Decompress data.
    static func decompress(_ data: Data, uncompressedSize: Int) throws -> Data {
        guard !data.isEmpty else { return data }
        let algorithm = Self.algorithm

        let maxSize = compression_decode_scratch_buffer_size(algorithm)
        var decompressed = Data(count: max(uncompressedSize, data.count * 4) + maxSize)
        let count = data.withUnsafeBytes { source in
            decompressed.withUnsafeMutableBytes { dest in
                compression_decode_buffer(
                    dest.baseAddress!.assumingMemoryBound(to: UInt8.self),
                    dest.count,
                    source.baseAddress!.assumingMemoryBound(to: UInt8.self),
                    source.count,
                    nil,
                    algorithm
                )
            }
        }
        guard count > 0 else { throw CompressionError.decompressionFailed }
        return decompressed.prefix(count)
    }

    /// Compress a JSON-serializable dictionary.
    static func compressDictionary(_ dict: [String: Any]) throws -> Data {
        let data = try JSONSerialization.data(withJSONObject: dict)
        return try compress(data)
    }

    /// Decompress to a dictionary.
    static func decompressDictionary(_ data: Data, uncompressedSize: Int) throws -> [String: Any] {
        let decompressed = try decompress(data, uncompressedSize: uncompressedSize)
        guard let dict = try JSONSerialization.jsonObject(with: decompressed) as? [String: Any] else {
            throw CompressionError.invalidData
        }
        return dict
    }
}

enum CompressionError: Error {
    case compressionFailed
    case decompressionFailed
    case invalidData
}

/// Tier-aware storage that compresses COOL and COLD nodes.
extension GRDBDatabase {
    /// Compress and store a COLD tier node.
    func compressColdNode(entityId: String, attributes: [String: Any]) throws {
        let compressed = try CompressionHelper.compressDictionary(attributes)
        try dbPool.write { db in
            try db.execute(
                sql: "UPDATE kg_node SET attributes = ?, isCompressed = true WHERE entityId = ?",
                arguments: [compressed.base64EncodedString(), entityId]
            )
        }
    }

    /// Decompress a COLD tier node.
    func decompressColdNode(entityId: String) throws -> [String: Any] {
        let row = try dbPool.read { db in
            try Row.fetchOne(db, sql: "SELECT attributes, isCompressed FROM kg_node WHERE entityId = ?", arguments: [entityId])
        }
        guard let attributesStr = row?["attributes"] as? String else { return [:] }
        guard let compressed = Data(base64Encoded: attributesStr) else { return [:] }
        let uncompressedSize = (row?["uncompressedSize"] as? Int) ?? compressed.count * 4
        return try CompressionHelper.decompressDictionary(compressed, uncompressedSize: uncompressedSize)
    }
}
