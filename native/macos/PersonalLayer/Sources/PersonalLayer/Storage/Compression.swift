import Foundation
import Compression

enum CompressionHelper {
    static let algorithm: compression_algorithm = {
        if #available(macOS 12.0, *) {
            return COMPRESSION_ZSTD
        }
        return COMPRESSION_LZ4_RAW
    }()

    static func compress(_ data: Data) throws -> Data {
        guard !data.isEmpty else { return data }
        let algorithm = Self.algorithm
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

    static func compressDictionary(_ dict: [String: Any]) throws -> Data {
        let data = try JSONSerialization.data(withJSONObject: dict)
        return try compress(data)
    }

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
