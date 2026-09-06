// ios/AgentCoreIOS/Providers/ModelDownloadManager.swift
// Resume-friendly GGUF downloader. Weights only. HTTPS (or file:// in tests).

import Combine
import CryptoKit
import Foundation

public final class ModelDownloadManager: ObservableObject, @unchecked Sendable {
    public static let shared = ModelDownloadManager()

    @Published public private(set) var progress: [String: Double] = [:]
    @Published public private(set) var statusText: [String: String] = [:]
    @Published public private(set) var installedIds: Set<String> = []

    private let fileManager: FileManager
    private let root: URL
    private var tasks: [String: Task<URL, Error>] = [:]
    public var session: URLSession
    public var maxBytes: Int64 = 8_000_000_000

    public init(root: URL? = nil, session: URLSession = .shared, fileManager: FileManager = .default) {
        self.fileManager = fileManager
        self.session = session
        if let root {
            self.root = root
        } else {
            self.root = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
                .appendingPathComponent("AgentCore", isDirectory: true)
        }
        refreshInstalled()
    }

    public func localURL(for spec: LLMModelSpec) -> URL {
        ModelCatalog.localURL(for: spec, base: root)
    }

    public func isInstalled(_ spec: LLMModelSpec) -> Bool {
        fileManager.fileExists(atPath: localURL(for: spec).path)
    }

    public func refreshInstalled() {
        var ids: Set<String> = []
        for spec in ModelCatalog.all where isInstalled(spec) {
            ids.insert(spec.id)
        }
        installedIds = ids
    }

    public func cancel(_ spec: LLMModelSpec) {
        tasks[spec.id]?.cancel()
        tasks[spec.id] = nil
        progress[spec.id] = 0
        statusText[spec.id] = "Cancelled"
    }

    public func delete(_ spec: LLMModelSpec) throws {
        let url = localURL(for: spec)
        if fileManager.fileExists(atPath: url.path) {
            try fileManager.removeItem(at: url)
        }
        installedIds.remove(spec.id)
        progress[spec.id] = 0
        statusText[spec.id] = "Deleted"
    }

    public func inspect(_ spec: LLMModelSpec) throws -> GGUFInfo {
        try GGUFHeader.inspect(fileAt: localURL(for: spec))
    }

    @discardableResult
    public func download(_ spec: LLMModelSpec) async throws -> URL {
        if let existing = tasks[spec.id] {
            return try await existing.value
        }
        let task = Task<URL, Error> { [weak self] in
            guard let self else { throw LanguageModelError.cancelled }
            return try await self.performDownload(spec)
        }
        tasks[spec.id] = task
        defer { tasks[spec.id] = nil }
        do {
            return try await task.value
        } catch is CancellationError {
            throw LanguageModelError.cancelled
        }
    }

    private func performDownload(_ spec: LLMModelSpec) async throws -> URL {
        try Task.checkCancellation()
        let dest = localURL(for: spec)
        if fileManager.fileExists(atPath: dest.path), GGUFHeader.isGGUF(fileAt: dest) {
            progress[spec.id] = 1
            statusText[spec.id] = "Ready"
            installedIds.insert(spec.id)
            return dest
        }

        try validateSource(spec.downloadURL)
        try fileManager.createDirectory(at: dest.deletingLastPathComponent(), withIntermediateDirectories: true)

        progress[spec.id] = 0.05
        statusText[spec.id] = "Downloading"

        let isLocalFile = spec.downloadURL.isFileURL
        let staged: URL
        if isLocalFile {
            staged = spec.downloadURL
            guard fileManager.fileExists(atPath: staged.path) else {
                throw LanguageModelError.downloadFailed("Local file not found")
            }
        } else {
            var request = URLRequest(url: spec.downloadURL)
            request.setValue("Agent-Core-iOS/0.2.0", forHTTPHeaderField: "User-Agent")
            request.timeoutInterval = 600

            let (fileURL, response) = try await session.download(for: request)
            if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
                throw LanguageModelError.downloadFailed("HTTP \(http.statusCode)")
            }
            staged = fileURL
        }

        let attrs = try fileManager.attributesOfItem(atPath: staged.path)
        let size = (attrs[.size] as? NSNumber)?.int64Value ?? 0
        if size > maxBytes {
            if !isLocalFile { try? fileManager.removeItem(at: staged) }
            throw LanguageModelError.downloadFailed("File exceeds disk budget")
        }
        if spec.approximateBytes > 0, size > 64, size < spec.approximateBytes / 4 {
            if !isLocalFile { try? fileManager.removeItem(at: staged) }
            throw LanguageModelError.downloadFailed("Downloaded file is unexpectedly small")
        }

        progress[spec.id] = 0.85
        statusText[spec.id] = "Verifying"

        if let expected = spec.sha256, !expected.isEmpty {
            let data = try Data(contentsOf: staged, options: [.mappedIfSafe])
            let digest = SHA256.hash(data: data)
            let hex = digest.map { String(format: "%02x", $0) }.joined()
            if hex != expected.lowercased() {
                if !isLocalFile { try? fileManager.removeItem(at: staged) }
                throw LanguageModelError.downloadFailed("SHA-256 mismatch")
            }
        }

        guard GGUFHeader.isGGUF(fileAt: staged) else {
            if !isLocalFile { try? fileManager.removeItem(at: staged) }
            throw LanguageModelError.invalidModelFile("Not a GGUF weight file")
        }

        if fileManager.fileExists(atPath: dest.path) {
            try fileManager.removeItem(at: dest)
        }
        if isLocalFile {
            try fileManager.copyItem(at: staged, to: dest)
        } else {
            try fileManager.moveItem(at: staged, to: dest)
        }

        progress[spec.id] = 1
        statusText[spec.id] = "Ready"
        installedIds.insert(spec.id)
        return dest
    }

    private func validateSource(_ url: URL) throws {
        let scheme = url.scheme?.lowercased() ?? ""
        if scheme == "file" { return }
        if scheme == "http" {
            let host = url.host?.lowercased() ?? ""
            if host == "127.0.0.1" || host == "localhost" { return }
            throw LanguageModelError.downloadFailed("HTTP only allowed for local hosts")
        }
        guard scheme == "https" else {
            throw LanguageModelError.downloadFailed("Downloads must use HTTPS")
        }
        let host = url.host?.lowercased() ?? ""
        let allowed = [
            "huggingface.co",
            "cdn-lfs.huggingface.co",
            "hf.co",
            "github.com",
            "objects.githubusercontent.com",
        ]
        if !allowed.contains(where: { host == $0 || host.hasSuffix("." + $0) }) {
            throw LanguageModelError.downloadFailed("Host not in allow-list: \(host)")
        }
    }
}
