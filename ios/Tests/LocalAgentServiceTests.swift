// ios/Tests/LocalAgentServiceTests.swift
// Native XCTest Suite for LocalAgentService & Native Runtime Contracts

import XCTest
@testable import AgentCoreIOS

final class LocalAgentServiceTests: XCTestCase {
    private var tempDir: URL!
    private var service: LocalAgentService!

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

    func test03_remember() async {
        let res = await service.remember(key: "preferred_branch", value: "master")
        XCTAssertEqual(res.status, .success)
        XCTAssertEqual(res.item?.key, "preferred_branch")
        XCTAssertEqual(res.item?.value, "master")
    }

    func test04_retrieve() async {
        _ = await service.remember(key: "user_editor", value: "vscode")
        let items = await service.retrieve(query: "vscode")
        XCTAssertEqual(items.count, 1)
        XCTAssertEqual(items.first?.value, "vscode")
    }

    func test05_persistenceAfterRuntimeRecreation() async {
        _ = await service.remember(key: "persist_key", value: "persist_val")

        // Recreate runtime pointing to same storage URL
        let memStore2 = LocalMemoryStore(storageDir: tempDir.appendingPathComponent("memories"))
        let expStore2 = LocalExperienceStore(storageDir: tempDir.appendingPathComponent("experiences"))
        let chkStore2 = LocalCheckpointStore(storageDir: tempDir.appendingPathComponent("runs"))
        let vltStore2 = LocalVaultStore(storageDir: tempDir.appendingPathComponent("vault"))

        let runtime2 = AgentRuntime(
            memoryStore: memStore2,
            experienceStore: expStore2,
            checkpointStore: chkStore2,
            vaultStore: vltStore2
        )
        let service2 = LocalAgentService(runtime: runtime2)

        let items = await service2.retrieve(query: "persist_key")
        XCTAssertEqual(items.count, 1)
        XCTAssertEqual(items.first?.value, "persist_val")
    }

    func test06_run() async {
        let res = await service.run(goal: "Inspect workspace architecture")
        XCTAssertEqual(res.status, .success)
        XCTAssertTrue(res.runId.hasPrefix("RUN-"))
        XCTAssertFalse(res.planSteps.isEmpty)
    }

    func test07_stableRunId() async {
        let res = await service.run(goal: "Stable ID test")
        XCTAssertFalse(res.runId.isEmpty)
        let runInfo = await service.getRun(runId: res.runId)
        XCTAssertEqual(runInfo?.runId, res.runId)
    }

    func test08_policyDenial() async {
        // Unapproved write capability call -> DENIED
        let res = await service.executeCapability(
            capabilityId: "github_integration",
            input: ["action": "create_issue_comment", "owner": "owner", "repo": "repo", "issue_number": "1", "body": "comment"],
            userApproved: false
        )
        XCTAssertEqual(res.status, .denied)
        XCTAssertTrue(res.errorMessage?.contains("requires explicit user approval") ?? false)
    }

    func test09_approvedMutation() async {
        // Approved write capability call -> SUCCESS (offline mock)
        let res = await service.executeCapability(
            capabilityId: "github_integration",
            input: ["action": "create_issue_comment", "owner": "owner", "repo": "repo", "issue_number": "1", "body": "comment", "mock_offline": "true"],
            userApproved: true
        )
        XCTAssertEqual(res.status, .success)
    }

    func test10_experiencePersistence() async {
        let runRes = await service.run(goal: "Experience test goal")
        let exps = await service.getExperience()
        XCTAssertTrue(exps.contains(where: { $0.runId == runRes.runId }))
    }

    func test11_checkpointPersistence() async {
        let runRes = await service.run(goal: "Checkpoint test goal")

        // Recreate runtime and verify run checkpoint reloads from disk
        let chkStore2 = LocalCheckpointStore(storageDir: tempDir.appendingPathComponent("runs"))
        let loaded = chkStore2.get(runId: runRes.runId)
        XCTAssertNotNil(loaded)
        XCTAssertEqual(loaded?.runId, runRes.runId)
    }

    func test12_resume() async {
        let runRes = await service.run(goal: "Initial run for resume")
        let resumed = await service.resume(runId: runRes.runId)
        XCTAssertEqual(resumed.runId, runRes.runId)
        XCTAssertEqual(resumed.status, .success)
        XCTAssertTrue(resumed.output?.contains("Resumed") ?? false)
    }

    func test13_failedCapability() async {
        // Attempting GitHub action without mock flag in offline mode returns FAILED
        let res = await service.executeCapability(
            capabilityId: "github_integration",
            input: ["action": "get_repo", "owner": "owner", "repo": "repo"],
            userApproved: false
        )
        XCTAssertEqual(res.status, .failed)
    }

    func test14_health() async {
        let h = await service.health()
        XCTAssertEqual(h.status, "HEALTHY")
        XCTAssertTrue(h.isLocalOnly)
        XCTAssertTrue(h.activeCapabilitiesCount >= 2)
    }

    func test15_noNetworkRequired() async {
        // Verify local memory, vault, reasoning, capability listing, and runs execute completely offline
        _ = await service.remember(key: "offline_key", value: "offline_val")
        let retrieved = await service.retrieve(query: "offline_key")
        XCTAssertEqual(retrieved.count, 1)

        let caps = await service.listCapabilities()
        XCTAssertFalse(caps.isEmpty)

        let runRes = await service.run(goal: "Fully offline local operation")
        XCTAssertEqual(runRes.status, .success)
    }
}
