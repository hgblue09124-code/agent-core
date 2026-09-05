// ios/AgentCoreIOS/Storage/LocalMemoryStore.swift
// Native iOS Local File-Backed Memory Store (Application Support/AgentCore/memories/)

import Foundation

public final class LocalMemoryStore: @unchecked Sendable {
    private let storageDir: URL
    private var memories: [String: MemoryItem] = [:]

    public init(storageDir: URL? = nil) {
        if let dir = storageDir {
            self.storageDir = dir
        } else {
            let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
            self.storageDir = appSupport.appendingPathComponent("AgentCore/memories", isDirectory: true)
        }
        try? FileManager.default.createDirectory(at: self.storageDir, withIntermediateDirectories: true)
        loadFromDisk()
    }

    private var fileURL: URL {
        storageDir.appendingPathComponent("memories.json")
    }

    private func loadFromDisk() {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return }
        do {
            let data = try Data(contentsOf: fileURL)
            let items = try JSONDecoder().decode([String: MemoryItem].self, from: data)
            self.memories = items
        } catch {
            print("Failed to load local memories: \(error)")
        }
    }

    private func saveToDisk() {
        let tmp = storageDir.appendingPathComponent("memories.json.tmp")
        do {
            let data = try JSONEncoder().encode(memories)
            try data.write(to: tmp, options: .atomic)
            if FileManager.default.fileExists(atPath: fileURL.path) {
                try FileManager.default.removeItem(at: fileURL)
            }
            try FileManager.default.moveItem(at: tmp, to: fileURL)
        } catch {
            print("Failed to save local memories atomically: \(error)")
        }
    }

    public func remember(key: String, value: String) -> MemoryItem {
        let id = "MEM-" + UUID().uuidString.prefix(8).lowercased()
        let item = MemoryItem(memoryId: id, key: key, value: value)
        memories[key] = item
        saveToDisk()
        return item
    }

    public func retrieve(query: String) -> [MemoryItem] {
        let q = query.lowercased()
        if q.isEmpty {
            return Array(memories.values)
        }
        return memories.values.filter {
            $0.key.lowercased().contains(q) || $0.value.lowercased().contains(q)
        }
    }

    public func update(key: String, value: String) -> MemoryItem? {
        guard var item = memories[key] else { return nil }
        item = MemoryItem(
            memoryId: item.memoryId,
            key: key,
            value: value,
            memoryType: item.memoryType,
            importance: item.importance,
            createdAt: item.createdAt,
            updatedAt: ISO8601DateFormatter().string(from: Date())
        )
        memories[key] = item
        saveToDisk()
        return item
    }

    public func forget(key: String) -> Bool {
        if memories.removeValue(forKey: key) != nil {
            saveToDisk()
            return true
        }
        return false
    }
}
