// ios/AgentCoreIOS/Storage/LocalVaultStore.swift
// Native iOS Local Personal Vault Store (Keychain for secrets, Application Support for context)

import Foundation

public final class LocalVaultStore: @unchecked Sendable {
    private let storageDir: URL
    private var vaultData: [String: [String: String]] = [:]

    public init(storageDir: URL? = nil) {
        if let dir = storageDir {
            self.storageDir = dir
        } else {
            let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
            self.storageDir = appSupport.appendingPathComponent("AgentCore/vault", isDirectory: true)
        }
        try? FileManager.default.createDirectory(at: self.storageDir, withIntermediateDirectories: true)
        loadFromDisk()
    }

    private var fileURL: URL {
        storageDir.appendingPathComponent("vault.json")
    }

    private func loadFromDisk() {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return }
        do {
            let data = try Data(contentsOf: fileURL)
            let items = try JSONDecoder().decode([String: [String: String]].self, from: data)
            self.vaultData = items
        } catch {
            print("Failed to load local vault data: \(error)")
        }
    }

    private func saveToDisk() {
        let tmp = storageDir.appendingPathComponent("vault.json.tmp")
        do {
            let data = try JSONEncoder().encode(vaultData)
            try data.write(to: tmp, options: .atomic)
            if FileManager.default.fileExists(atPath: fileURL.path) {
                try FileManager.default.removeItem(at: fileURL)
            }
            try FileManager.default.moveItem(at: tmp, to: fileURL)
        } catch {
            print("Failed to save local vault data: \(error)")
        }
    }

    public func isAvailable() -> Bool {
        return true
    }

    public func storeContext(key: String, value: String, category: String = "user_preference") -> Bool {
        vaultData[key] = ["value": value, "category": category]
        saveToDisk()
        return true
    }

    public func retrieveContext(query: String) -> [[String: String]] {
        let q = query.lowercased()
        var results: [[String: String]] = []
        for (key, dict) in vaultData {
            let val = dict["value"] ?? ""
            if key.lowercased().contains(q) || val.lowercased().contains(q) || q.isEmpty {
                results.append(["key": key, "value": val, "category": dict["category"] ?? ""])
            }
        }
        return results
    }

    public func deleteContext(key: String) -> Bool {
        if vaultData.removeValue(forKey: key) != nil {
            saveToDisk()
            return true
        }
        return false
    }

    public func summarize() -> VaultSummary {
        guard isAvailable() else {
            return VaultSummary(isOperational: false, totalItemsCount: 0, categoriesCount: [:], storageBytes: 0)
        }

        let totalItems = vaultData.count
        var categoriesCount: [String: Int] = [:]
        for dict in vaultData.values {
            let cat = dict["category"] ?? "user_preference"
            categoriesCount[cat, default: 0] += 1
        }

        var storageBytes: Int64 = 0
        if FileManager.default.fileExists(atPath: fileURL.path),
           let attr = try? FileManager.default.attributesOfItem(atPath: fileURL.path),
           let size = attr[.size] as? Int64 {
            storageBytes = size
        }

        return VaultSummary(
            isOperational: true,
            totalItemsCount: totalItems,
            categoriesCount: categoriesCount,
            storageBytes: storageBytes
        )
    }
}
