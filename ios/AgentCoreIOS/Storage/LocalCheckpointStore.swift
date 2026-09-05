// ios/AgentCoreIOS/Storage/LocalCheckpointStore.swift
// Native iOS Local File-Backed Checkpoint Store (Application Support/AgentCore/runs/)

import Foundation

public final class LocalCheckpointStore: @unchecked Sendable {
    private let storageDir: URL
    private var checkpoints: [String: AgentRunResult] = [:]

    public init(storageDir: URL? = nil) {
        if let dir = storageDir {
            self.storageDir = dir
        } else {
            let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
            self.storageDir = appSupport.appendingPathComponent("AgentCore/runs", isDirectory: true)
        }
        try? FileManager.default.createDirectory(at: self.storageDir, withIntermediateDirectories: true)
        loadFromDisk()
    }

    private var fileURL: URL {
        storageDir.appendingPathComponent("runs.json")
    }

    private func loadFromDisk() {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return }
        do {
            let data = try Data(contentsOf: fileURL)
            let items = try JSONDecoder().decode([String: AgentRunResult].self, from: data)
            self.checkpoints = items
        } catch {
            print("Failed to load local checkpoints: \(error)")
        }
    }

    private func saveToDisk() {
        let tmp = storageDir.appendingPathComponent("runs.json.tmp")
        do {
            let data = try JSONEncoder().encode(checkpoints)
            try data.write(to: tmp, options: .atomic)
            if FileManager.default.fileExists(atPath: fileURL.path) {
                try FileManager.default.removeItem(at: fileURL)
            }
            try FileManager.default.moveItem(at: tmp, to: fileURL)
        } catch {
            print("Failed to save local checkpoints: \(error)")
        }
    }

    public func save(result: AgentRunResult) {
        checkpoints[result.runId] = result
        saveToDisk()
    }

    public func get(runId: String) -> AgentRunResult? {
        return checkpoints[runId]
    }

    public func listAll() -> [AgentRunResult] {
        return Array(checkpoints.values)
    }
}
