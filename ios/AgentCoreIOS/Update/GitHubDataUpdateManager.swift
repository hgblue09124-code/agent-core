// ios/AgentCoreIOS/Update/GitHubDataUpdateManager.swift
// Offline-First GitHub Data Update Manager v0.1

import Foundation

public final class GitHubDataUpdateManager: @unchecked Sendable {
    public let config: GitHubDataUpdateConfiguration
    public let validator: DataUpdateValidator

    private let storageDir: URL
    private let stagingDir: URL
    private let statePath: URL

    private var report: DataUpdateStateReport

    public init(
        config: GitHubDataUpdateConfiguration? = nil,
        validator: DataUpdateValidator? = nil,
        storageDir: URL? = nil
    ) {
        self.config = config ?? GitHubDataUpdateConfiguration()
        self.validator = validator ?? DataUpdateValidator()

        if let dir = storageDir {
            self.storageDir = dir
        } else {
            let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
            self.storageDir = appSupport.appendingPathComponent("AgentCore/data", isDirectory: true)
        }

        self.stagingDir = self.storageDir.appendingPathComponent("staging", isDirectory: true)
        self.statePath = self.storageDir.appendingPathComponent("update_state.json")

        try? FileManager.default.createDirectory(at: self.storageDir, withIntermediateDirectories: true)
        try? FileManager.default.createDirectory(at: self.stagingDir, withIntermediateDirectories: true)

        self.report = DataUpdateStateReport()
        loadReport()
    }

    private func loadReport() {
        guard FileManager.default.fileExists(atPath: statePath.path) else { return }
        do {
            let data = try Data(contentsOf: statePath)
            self.report = try JSONDecoder().decode(DataUpdateStateReport.self, from: data)
        } catch {
            print("Failed to load update state report: \(error)")
        }
    }

    private func saveReport() {
        let tmp = storageDir.appendingPathComponent("update_state.json.tmp")
        do {
            let data = try JSONEncoder().encode(report)
            try data.write(to: tmp, options: .atomic)
            if FileManager.default.fileExists(atPath: statePath.path) {
                try FileManager.default.removeItem(at: statePath)
            }
            try FileManager.default.moveItem(at: tmp, to: statePath)
        } catch {
            print("Failed to save update state report: \(error)")
        }
    }

    public func getStateReport() -> DataUpdateStateReport {
        return report
    }

    /// Check remote GitHub repository for update manifest safely.
    public func checkForUpdates(mockManifest: AppDataManifest? = nil) async -> DataUpdateStateReport {
        let nowStr = ISO8601DateFormatter().string(from: Date())

        if let mock = mockManifest {
            do {
                try validator.validateManifestSchema(mock, clientVersion: config.currentClientVersion)
                let isNewer = validator.isVersion(report.installedDataVersion, olderThan: mock.dataVersion)
                report = DataUpdateStateReport(
                    installedDataVersion: report.installedDataVersion,
                    latestKnownVersion: mock.dataVersion,
                    status: isNewer ? .updateAvailable : .upToDate,
                    lastSuccessfulSync: report.lastSuccessfulSync,
                    lastAttempt: nowStr,
                    lastError: nil,
                    isOffline: false
                )
                saveReport()
                return report
            } catch {
                report = DataUpdateStateReport(
                    installedDataVersion: report.installedDataVersion,
                    latestKnownVersion: report.latestKnownVersion,
                    status: .failed,
                    lastSuccessfulSync: report.lastSuccessfulSync,
                    lastAttempt: nowStr,
                    lastError: "Manifest Validation Error: \(error)",
                    isOffline: false
                )
                saveReport()
                return report
            }
        }

        // Fetch manifest URL
        guard let manifestURL = config.urlForFile(path: config.manifestPath) else {
            report = DataUpdateStateReport(
                installedDataVersion: report.installedDataVersion,
                status: .failed,
                lastAttempt: nowStr,
                lastError: "Invalid manifest URL configuration."
            )
            saveReport()
            return report
        }

        do {
            let (data, response) = try await URLSession.shared.data(from: manifestURL)
            guard let httpResp = response as? HTTPURLResponse, httpResp.statusCode == 200 else {
                let code = (response as? HTTPURLResponse)?.statusCode ?? 500
                report = DataUpdateStateReport(
                    installedDataVersion: report.installedDataVersion,
                    status: .offline,
                    lastAttempt: nowStr,
                    lastError: "Manifest fetch returned HTTP \(code)",
                    isOffline: true
                )
                saveReport()
                return report
            }

            let manifest = try JSONDecoder().decode(AppDataManifest.self, from: data)
            try validator.validateManifestSchema(manifest, clientVersion: config.currentClientVersion)

            let isNewer = validator.isVersion(report.installedDataVersion, olderThan: manifest.dataVersion)
            report = DataUpdateStateReport(
                installedDataVersion: report.installedDataVersion,
                latestKnownVersion: manifest.dataVersion,
                status: isNewer ? .updateAvailable : .upToDate,
                lastSuccessfulSync: report.lastSuccessfulSync,
                lastAttempt: nowStr,
                lastError: nil,
                isOffline: false
            )
            saveReport()
            return report
        } catch {
            report = DataUpdateStateReport(
                installedDataVersion: report.installedDataVersion,
                status: .offline,
                lastAttempt: nowStr,
                lastError: "Network fetch failed: \(error.localizedDescription)",
                isOffline: true
            )
            saveReport()
            return report
        }
    }

    /// Perform atomic data update: snapshot active -> download delta to staging -> validate -> commit swap -> update state.
    public func performUpdate(manifest: AppDataManifest, fileDataMap: [String: Data]? = nil) async -> DataUpdateStateReport {
        let nowStr = ISO8601DateFormatter().string(from: Date())

        // Version Rule Enforcement
        if manifest.dataVersion == report.installedDataVersion {
            report = DataUpdateStateReport(
                installedDataVersion: report.installedDataVersion,
                latestKnownVersion: manifest.dataVersion,
                status: .upToDate,
                lastSuccessfulSync: report.lastSuccessfulSync,
                lastAttempt: nowStr,
                lastError: "Already at installed data version \(manifest.dataVersion)",
                isOffline: false
            )
            saveReport()
            return report
        }

        if validator.isVersion(manifest.dataVersion, olderThan: report.installedDataVersion) {
            report = DataUpdateStateReport(
                installedDataVersion: report.installedDataVersion,
                latestKnownVersion: manifest.dataVersion,
                status: .failed,
                lastSuccessfulSync: report.lastSuccessfulSync,
                lastAttempt: nowStr,
                lastError: "Version Downgrade Rejected: Remote version \(manifest.dataVersion) is older than installed \(report.installedDataVersion)",
                isOffline: false
            )
            saveReport()
            return report
        }

        do {
            // Validate manifest schema first
            try validator.validateManifestSchema(manifest, clientVersion: config.currentClientVersion)

            // 1. Clean staging directory
            if FileManager.default.fileExists(atPath: stagingDir.path) {
                try FileManager.default.removeItem(at: stagingDir)
            }
            try FileManager.default.createDirectory(at: stagingDir, withIntermediateDirectories: true)

            // Delta Update Preservation: Copy existing active/ dataset snapshot into staging/ before applying updates
            let activeDataDir = storageDir.appendingPathComponent("active", isDirectory: true)
            if FileManager.default.fileExists(atPath: activeDataDir.path) {
                let items = try FileManager.default.contentsOfDirectory(atPath: activeDataDir.path)
                for item in items {
                    let src = activeDataDir.appendingPathComponent(item)
                    let dst = stagingDir.appendingPathComponent(item)
                    try FileManager.default.copyItem(at: src, to: dst)
                }
            }

            // 2. Download or copy delta files into staging and validate
            for entry in manifest.files {
                try validator.validatePathSafety(path: entry.path)

                let fileData: Data
                if let mockMap = fileDataMap, let data = mockMap[entry.path] {
                    fileData = data
                } else if let fileURL = config.urlForFile(path: entry.path) {
                    let (data, response) = try await URLSession.shared.data(from: fileURL)
                    guard let httpResp = response as? HTTPURLResponse, httpResp.statusCode == 200 else {
                        throw DataUpdateValidationError(message: "Download failed for '\(entry.path)': HTTP \((response as? HTTPURLResponse)?.statusCode ?? 500)")
                    }
                    fileData = data
                } else {
                    throw DataUpdateValidationError(message: "Invalid URL for file '\(entry.path)'")
                }

                // Integrity check: SHA256 & size
                try validator.validateFileIntegrity(data: fileData, expectedSize: entry.size, expectedSHA256: entry.sha256)

                // Write to staging path (overwriting or creating)
                let stagingFilePath = stagingDir.appendingPathComponent(entry.path)
                let stagingParentDir = stagingFilePath.deletingLastPathComponent()
                try FileManager.default.createDirectory(at: stagingParentDir, withIntermediateDirectories: true)
                if FileManager.default.fileExists(atPath: stagingFilePath.path) {
                    try FileManager.default.removeItem(at: stagingFilePath)
                }
                try fileData.write(to: stagingFilePath, options: .atomic)
            }

            // 3. Atomic commit / swap: commit staging files into active storage directory
            let backupDataDir = storageDir.appendingPathComponent("backup", isDirectory: true)

            // Rollback prep: Move active to backup
            if FileManager.default.fileExists(atPath: backupDataDir.path) {
                try FileManager.default.removeItem(at: backupDataDir)
            }
            if FileManager.default.fileExists(atPath: activeDataDir.path) {
                try FileManager.default.moveItem(at: activeDataDir, to: backupDataDir)
            }

            // Move staging to active
            try FileManager.default.moveItem(at: stagingDir, to: activeDataDir)

            // Clean backup on commit success
            try? FileManager.default.removeItem(at: backupDataDir)

            // 4. Update state report
            report = DataUpdateStateReport(
                installedDataVersion: manifest.dataVersion,
                latestKnownVersion: manifest.dataVersion,
                status: .committed,
                lastSuccessfulSync: nowStr,
                lastAttempt: nowStr,
                lastError: nil,
                isOffline: false
            )
            saveReport()
            return report
        } catch {
            // Automatic Rollback on failure: restore active from backup if active was moved
            let activeDataDir = storageDir.appendingPathComponent("active", isDirectory: true)
            let backupDataDir = storageDir.appendingPathComponent("backup", isDirectory: true)
            if !FileManager.default.fileExists(atPath: activeDataDir.path) && FileManager.default.fileExists(atPath: backupDataDir.path) {
                try? FileManager.default.moveItem(at: backupDataDir, to: activeDataDir)
            }

            report = DataUpdateStateReport(
                installedDataVersion: report.installedDataVersion,
                latestKnownVersion: report.latestKnownVersion,
                status: .failed,
                lastSuccessfulSync: report.lastSuccessfulSync,
                lastAttempt: nowStr,
                lastError: "Update failed: \((error as? DataUpdateValidationError)?.message ?? error.localizedDescription)",
                isOffline: false
            )
            saveReport()
            return report
        }
    }
}
