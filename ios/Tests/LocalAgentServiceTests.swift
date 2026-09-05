// ios/Tests/LocalAgentServiceTests.swift
// Native XCTest Suite for LocalAgentService, Policy Boundaries & GitHub Data Update v0.1

import XCTest
@testable import AgentCoreIOS

final class LocalAgentServiceTests: XCTestCase {
    private var tempDir: URL!
    private var service: LocalAgentService!
    private var updateManager: GitHubDataUpdateManager!

    override func setUp() async throws {
        try await super.setUp()
        tempDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)

        let memStore = LocalMemoryStore(storageDir: tempDir.appendingPathComponent("memories"))
        let expStore = LocalExperienceStore(storageDir: tempDir.appendingPathComponent("experiences"))
        let chkStore = LocalCheckpointStore(storageDir: tempDir.appendingPathComponent("runs"))
        let vltStore = LocalVaultStore(storageDir: tempDir.appendingPathComponent("vault"))

        let runtime = AgentRuntime(
            memoryStore: memStore,
            experienceStore: expStore,
            checkpointStore: chkStore,
            vaultStore: vltStore
        )
        service = LocalAgentService(runtime: runtime)
        updateManager = GitHubDataUpdateManager(storageDir: tempDir.appendingPathComponent("data"))
    }

    override func tearDown() async throws {
        try? FileManager.default.removeItem(at: tempDir)
        try await super.tearDown()
    }

    func test01_serviceInitialization() async {
        XCTAssertNotNil(service)
    }

    func test02_offlineStartup() async {
        let health = await service.health()
        XCTAssertEqual(health.status, "HEALTHY")
        XCTAssertTrue(health.isLocalOnly)
    }

    func test03_rememberAndRetrieve() async {
        let res = await service.remember(key: "branch", value: "master")
        XCTAssertEqual(res.status, .success)

        let items = await service.retrieve(query: "master")
        XCTAssertEqual(items.count, 1)
        XCTAssertEqual(items.first?.value, "master")
    }

    func test04_actionAwarePolicy_readActionAllowedWithoutApproval() async {
        // Read action 'get_repo' on github_integration passes without user approval
        let res = await service.executeCapability(
            capabilityId: "github_integration",
            input: ["action": "get_repo", "owner": "owner", "repo": "repo", "mock_offline": "true"],
            userApproved: false
        )
        XCTAssertEqual(res.status, .success)
    }

    func test05_actionAwarePolicy_writeActionDeniedWithoutApproval() async {
        // Write action 'create_issue_comment' without approval -> DENIED
        let res = await service.executeCapability(
            capabilityId: "github_integration",
            input: ["action": "create_issue_comment", "owner": "owner", "repo": "repo", "issue_number": "1", "body": "comment"],
            userApproved: false
        )
        XCTAssertEqual(res.status, .denied)
        XCTAssertTrue(res.errorMessage?.contains("requires explicit user approval") ?? false)
    }

    func test06_actionAwarePolicy_writeActionAllowedWithApproval() async {
        // Write action 'create_issue_comment' with explicit approval -> SUCCESS
        let res = await service.executeCapability(
            capabilityId: "github_integration",
            input: ["action": "create_issue_comment", "owner": "owner", "repo": "repo", "issue_number": "1", "body": "comment", "mock_offline": "true"],
            userApproved: true
        )
        XCTAssertEqual(res.status, .success)
    }

    func test07_pathSafetyValidator_rejectsAbsoluteAndTraversalPaths() {
        let validator = DataUpdateValidator()

        XCTAssertThrowsError(try validator.validatePathSafety(path: "/etc/passwd"))
        XCTAssertThrowsError(try validator.validatePathSafety(path: "../secret.json"))
        XCTAssertThrowsError(try validator.validatePathSafety(path: "config/../../secret.json"))
        XCTAssertThrowsError(try validator.validatePathSafety(path: "bin/update.swift"))

        XCTAssertNoThrow(try validator.validatePathSafety(path: "agent-config/default.json"))
    }

    func test08_dataUpdateIntegrity_sha256AndSizeValidation() {
        let validator = DataUpdateValidator()
        let sampleData = "Hello Agent Core Data Update".data(using: .utf8)!
        let expectedHash = validator.sha256Hex(data: sampleData)

        // Valid integrity -> No error
        XCTAssertNoThrow(try validator.validateFileIntegrity(data: sampleData, expectedSize: sampleData.count, expectedSHA256: expectedHash))

        // Mismatched size -> Throws error
        XCTAssertThrowsError(try validator.validateFileIntegrity(data: sampleData, expectedSize: sampleData.count + 10, expectedSHA256: expectedHash))

        // Mismatched SHA-256 -> Throws error
        XCTAssertThrowsError(try validator.validateFileIntegrity(data: sampleData, expectedSize: sampleData.count, expectedSHA256: "invalid_hash"))
    }

    func test09_atomicDataUpdateAndRollback() async {
        let sampleData = "test config content".data(using: .utf8)!
        let validator = DataUpdateValidator()
        let hash = validator.sha256Hex(data: sampleData)

        let manifest = AppDataManifest(
            schemaVersion: 1,
            dataVersion: "2026.09.05.001",
            minimumClientVersion: "0.1.0",
            files: [ManifestFileEntry(path: "agent-config/default.json", sha256: hash, size: sampleData.count)]
        )

        // Perform successful update
        let report = await updateManager.performUpdate(manifest: manifest, fileDataMap: ["agent-config/default.json": sampleData])
        XCTAssertEqual(report.status, .committed)
        XCTAssertEqual(report.installedDataVersion, "2026.09.05.001")

        // Attempt invalid update with hash mismatch -> Triggers rollback & returns failed status
        let badManifest = AppDataManifest(
            schemaVersion: 1,
            dataVersion: "2026.09.05.002",
            minimumClientVersion: "0.1.0",
            files: [ManifestFileEntry(path: "agent-config/default.json", sha256: "bad_hash", size: sampleData.count)]
        )

        let badReport = await updateManager.performUpdate(manifest: badManifest, fileDataMap: ["agent-config/default.json": sampleData])
        XCTAssertEqual(badReport.status, .failed)
        XCTAssertEqual(badReport.installedDataVersion, "2026.09.05.001") // Preserves last known-good version
    }

    func test10_offlineUpdateCheck_preservesAgentCoreOperation() async {
        // Checking updates offline without network or mock returns offline status without breaking AgentCore
        let report = await updateManager.checkForUpdates()
        XCTAssertEqual(report.status, .offline)
        XCTAssertTrue(report.isOffline)

        // Local Agent Core run continues normally
        let runRes = await service.run(goal: "Offline operation after failed update check")
        XCTAssertEqual(runRes.status, .success)
    }
}
