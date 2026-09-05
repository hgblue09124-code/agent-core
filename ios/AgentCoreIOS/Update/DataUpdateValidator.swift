// ios/AgentCoreIOS/Update/DataUpdateValidator.swift
// Security and Integrity Validator for GitHub Data Update v0.1

import Foundation
import CommonCrypto

public struct DataUpdateValidationError: Error, CustomStringError {
    public let message: String
    public var description: String { message }
}

public protocol CustomStringError {
    var message: String { get }
}

public final class DataUpdateValidator: @unchecked Sendable {
    public init() {}

    /// Validate path safety: must be relative, no leading slash, no '..' path traversal.
    public func validatePathSafety(path: String) throws {
        let clean = path.trimmingCharacters(in: .whitespaces)
        if clean.hasPrefix("/") || clean.contains("..") {
            throw DataUpdateValidationError(message: "Path Traversal Violation: Path '\(path)' contains absolute prefix or '..' traversal.")
        }

        // Executable code boundary check: Reject Swift code, dynamic libraries, and native executables.
        let forbiddenExtensions = [".swift", ".dylib", ".so", ".a", ".sh", ".bin", ".exec"]
        let lower = clean.lowercased()
        if forbiddenExtensions.contains(where: { lower.hasSuffix($0) }) {
            throw DataUpdateValidationError(message: "Executable Code Boundary Violation: Remote file '\(path)' has forbidden extension. Only data/config allowed.")
        }
    }

    /// Validate manifest schema version and client compatibility.
    public func validateManifestSchema(_ manifest: AppDataManifest, clientVersion: String) throws {
        guard manifest.schemaVersion == 1 else {
            throw DataUpdateValidationError(message: "Unsupported Schema Version: Manifest schema version \(manifest.schemaVersion) is not supported.")
        }

        if isVersion(clientVersion, olderThan: manifest.minimumClientVersion) {
            throw DataUpdateValidationError(message: "Incompatible Client Version: Client \(clientVersion) is below required minimum \(manifest.minimumClientVersion).")
        }

        for file in manifest.files {
            try validatePathSafety(path: file.path)
        }
    }

    /// Validate file size and SHA-256 checksum.
    public func validateFileIntegrity(data: Data, expectedSize: Int, expectedSHA256: String) throws {
        guard data.count == expectedSize else {
            throw DataUpdateValidationError(message: "Size Mismatch: File size \(data.count) bytes does not match expected size \(expectedSize) bytes.")
        }

        let computedHash = sha256Hex(data: data)
        guard computedHash.lowercased() == expectedSHA256.lowercased() else {
            throw DataUpdateValidationError(message: "SHA-256 Checksum Mismatch: Computed hash '\(computedHash)' does not match expected '\(expectedSHA256)'.")
        }
    }

    /// Compute SHA-256 hex string.
    public func sha256Hex(data: Data) -> String {
        var hash = [UInt8](repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH))
        data.withUnsafeBytes {
            _ = CC_SHA256($0.baseAddress, CC_LONG(data.count), &hash)
        }
        return hash.map { String(format: "%02x", $0) }.joined()
    }

    /// Compare semantic versions (e.g., "0.1.0" vs "0.2.0").
    public func isVersion(_ v1: String, olderThan v2: String) -> Bool {
        let p1 = v1.split(separator: ".").compactMap { Int($0) }
        let p2 = v2.split(separator: ".").compactMap { Int($0) }

        for i in 0..<max(p1.count, p2.count) {
            let n1 = i < p1.count ? p1[i] : 0
            let n2 = i < p2.count ? p2[i] : 0
            if n1 < n2 { return true }
            if n1 > n2 { return false }
        }
        return false
    }
}
