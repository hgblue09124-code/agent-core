// ios/AgentCoreIOS/Update/GitHubDataUpdateConfiguration.swift
// Configuration abstraction for GitHub Data Update v0.1

import Foundation

/// Safe configuration struct for GitHub Data Update v0.1.
/// Does not store or require personal tokens or credentials. Uses unauthenticated public read access by default.
public struct GitHubDataUpdateConfiguration: Codable, Sendable {
    public let owner: String
    public let repo: String
    public let branch: String
    public let manifestPath: String
    public let autoCheckOnLaunch: Bool
    public let currentClientVersion: String

    public init(
        owner: String = "hgblue09124-code",
        repo: String = "agent-core",
        branch: String = "master",
        manifestPath: String = "data-update/manifest.json",
        autoCheckOnLaunch: Bool = true,
        currentClientVersion: String = "0.1.0"
    ) {
        self.owner = owner
        self.repo = repo
        self.branch = branch
        self.manifestPath = manifestPath
        self.autoCheckOnLaunch = autoCheckOnLaunch
        self.currentClientVersion = currentClientVersion
    }

    /// URL for raw file content on GitHub.
    public func urlForFile(path: String) -> URL? {
        let cleanPath = path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        return URL(string: "https://raw.githubusercontent.com/\(owner)/\(repo)/\(branch)/\(cleanPath)")
    }
}
