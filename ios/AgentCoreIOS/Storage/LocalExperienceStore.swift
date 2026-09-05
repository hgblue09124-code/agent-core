// ios/AgentCoreIOS/Storage/LocalExperienceStore.swift
// Native iOS Local File-Backed Experience Store (Application Support/AgentCore/experiences/)

import Foundation

public final class LocalExperienceStore: @unchecked Sendable {
    private let storageDir: URL
    private var experiences: [String: Experience] = [:]

    public init(storageDir: URL? = nil) {
        if let dir = storageDir {
            self.storageDir = dir
        } else {
            let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
            self.storageDir = appSupport.appendingPathComponent("AgentCore/experiences", isDirectory: true)
        }
        try? FileManager.default.createDirectory(at: self.storageDir, withIntermediateDirectories: true)
        loadFromDisk()
    }

    private var fileURL: URL {
        storageDir.appendingPathComponent("experiences.json")
    }

    private func loadFromDisk() {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return }
        do {
            let data = try Data(contentsOf: fileURL)
            let items = try JSONDecoder().decode([String: Experience].self, from: data)
            self.experiences = items
        } catch {
            print("Failed to load local experiences: \(error)")
        }
    }

    private func saveToDisk() {
        let tmp = storageDir.appendingPathComponent("experiences.json.tmp")
        do {
            let data = try JSONEncoder().encode(experiences)
            try data.write(to: tmp, options: .atomic)
            if FileManager.default.fileExists(atPath: fileURL.path) {
                try FileManager.default.removeItem(at: fileURL)
            }
            try FileManager.default.moveItem(at: tmp, to: fileURL)
        } catch {
            print("Failed to save local experiences: \(error)")
        }
    }

    public func record(runId: String, goal: String, outcome: String) -> Experience {
        let exp = Experience(runId: runId, goal: goal, outcome: outcome)
        experiences[runId] = exp
        saveToDisk()
        return exp
    }

    public func get(runId: String) -> Experience? {
        return experiences[runId]
    }

    public func listAll() -> [Experience] {
        return Array(experiences.values)
    }
}
