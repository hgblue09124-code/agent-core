// ios/AgentCoreIOS/Update/AppDataUpdateModels.swift
// Codable Manifest & Data Update Result Models for GitHub Data Update v0.1

import Foundation

/// Update status enum representing the operational state of the data updater.
public enum DataUpdateStatus: String, Codable, Sendable {
    case upToDate = "UP_TO_DATE"
    case updateAvailable = "UPDATE_AVAILABLE"
    case downloading = "DOWNLOADING"
    case validating = "VALIDATING"
    case committed = "COMMITTED"
    case failed = "FAILED"
    case offline = "OFFLINE"
}

/// File entry specification inside the remote data update manifest.
public struct ManifestFileEntry: Codable, Sendable, Identifiable {
    public var id: String { path }
    public let path: String
    public let sha256: String
    public let size: Int

    public init(path: String, sha256: String, size: Int) {
        self.path = path
        self.sha256 = sha256
        self.size = size
    }
}

/// Remote data update manifest schema.
public struct AppDataManifest: Codable, Sendable {
    public let schemaVersion: Int
    public let dataVersion: String
    public let minimumClientVersion: String
    public let files: [ManifestFileEntry]

    public init(schemaVersion: Int = 1, dataVersion: String, minimumClientVersion: String = "0.1.0", files: [ManifestFileEntry]) {
        self.schemaVersion = schemaVersion
        self.dataVersion = dataVersion
        self.minimumClientVersion = minimumClientVersion
        self.files = files
    }
}

/// Diagnostic state report for data update manager.
public struct DataUpdateStateReport: Codable, Sendable {
    public let installedDataVersion: String
    public let latestKnownVersion: String?
    public let status: DataUpdateStatus
    public let lastSuccessfulSync: String?
    public let lastAttempt: String?
    public let lastError: String?
    public let isOffline: Bool

    public init(
        installedDataVersion: String = "2026.09.04.001",
        latestKnownVersion: String? = nil,
        status: DataUpdateStatus = .upToDate,
        lastSuccessfulSync: String? = nil,
        lastAttempt: String? = nil,
        lastError: String? = nil,
        isOffline: Bool = false
    ) {
        self.installedDataVersion = installedDataVersion
        self.latestKnownVersion = latestKnownVersion
        self.status = status
        self.lastSuccessfulSync = lastSuccessfulSync
        self.lastAttempt = lastAttempt
        self.lastError = lastError
        self.isOffline = isOffline
    }
}
