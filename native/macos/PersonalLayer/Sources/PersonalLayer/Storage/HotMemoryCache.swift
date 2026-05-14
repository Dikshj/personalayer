import Foundation

/// HOT in-memory cache with LRU eviction and 50MB size limit.
/// Stores the most recently accessed nodes in memory for sub-millisecond access.
final class HotMemoryCache {
    private let maxByteSize = 50 * 1024 * 1024  // 50 MB
    private var cache: [String: CacheEntry] = [:]
    private var accessOrder: [String] = []
    private let lock = NSLock()
    private var currentByteSize = 0

    struct CacheEntry {
        let value: [String: Any]
        let byteSize: Int
        let insertedAt: Date
    }

    func set(_ key: String, value: [String: Any]) {
        lock.lock()
        defer { lock.unlock() }

        let data = (try? JSONSerialization.data(withJSONObject: value)) ?? Data()
        let byteSize = data.count

        if let existing = cache[key] {
            currentByteSize -= existing.byteSize
            accessOrder.removeAll { $0 == key }
        }

        while currentByteSize + byteSize > maxByteSize && !accessOrder.isEmpty {
            evictLRU()
        }

        cache[key] = CacheEntry(value: value, byteSize: byteSize, insertedAt: Date())
        accessOrder.append(key)
        currentByteSize += byteSize
    }

    func get(_ key: String) -> [String: Any]? {
        lock.lock()
        defer { lock.unlock() }
        guard let entry = cache[key] else { return nil }
        accessOrder.removeAll { $0 == key }
        accessOrder.append(key)
        return entry.value
    }

    func remove(_ key: String) {
        lock.lock()
        defer { lock.unlock() }
        if let existing = cache[key] {
            currentByteSize -= existing.byteSize
            cache.removeValue(forKey: key)
            accessOrder.removeAll { $0 == key }
        }
    }

    func all() -> [(key: String, value: [String: Any])] {
        lock.lock()
        defer { lock.unlock() }
        return accessOrder.compactMap { key in
            guard let entry = cache[key] else { return nil }
            return (key, entry.value)
        }
    }

    func clear() {
        lock.lock()
        defer { lock.unlock() }
        cache.removeAll()
        accessOrder.removeAll()
        currentByteSize = 0
    }

    var byteSize: Int {
        lock.lock(); defer { lock.unlock() }
        return currentByteSize
    }

    var count: Int {
        lock.lock(); defer { lock.unlock() }
        return cache.count
    }

    private func evictLRU() {
        guard let oldest = accessOrder.first else { return }
        if let existing = cache[oldest] {
            currentByteSize -= existing.byteSize
        }
        cache.removeValue(forKey: oldest)
        accessOrder.removeFirst()
    }
}
