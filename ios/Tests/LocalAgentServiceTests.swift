// ios/Tests/LocalAgentServiceTests.swift
// Native XCTest Suite for LocalAgentService, Policy Boundaries & GitHub Data Update v0.1

import XCTest
@testable import AgentCoreIOS

private final class EventCollector: @unchecked Sendable {
    private let lock = NSLock()
    private var _phases: [AgentEventPhase] = []

    func add(_ phase: AgentEventPhase) {
        lock.lock()
        _phases.append(phase)
        lock.unlock()
    }

    var phases: [AgentEventPhase] {
        lock.lock()
        defer { lock.unlock() }
        return _phases
    }
}

final class LocalAgentServiceTests: XCTestCase {
    private var tempDir: URL!
    private var service: LocalAgentService!
    private var updateManager: GitHubDataUpdateManager!
    private var chkStore: LocalCheckpointStore!

    override func setUp() async throws {
        try await super.setUp()
        tempDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)

        let memStore = LocalMemoryStore(storageDir: tempDir.appendingPathComponent("memories"))
        let expStore = LocalExperienceStore(storageDir: tempDir.appendingPathComponent("experiences"))
        chkStore = LocalCheckpointStore(storageDir: tempDir.appendingPathComponent("runs"))
        let vltStore = LocalVaultStore(storageDir: tempDir.appendingPathComponent("vault"))

        let mockProvider = MockLanguageModelProvider(fixedResponseText: "Real LLM generated response for task.")
        let runtime = AgentRuntime(
            memoryStore: memStore,
            experienceStore: expStore,
            checkpointStore: chkStore,
            vaultStore: vltStore,
            languageModelProvider: mockProvider
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

    func test09_atomicDeltaUpdatePreservesUnchangedFilesAndRollback() async {
        let validator = DataUpdateValidator()

        // 1. Initial v1 setup: Create active dataset with unchanged.json ("old") and changed.json ("v1")
        let unchangedData = "old".data(using: .utf8)!
        let changedDataV1 = "v1".data(using: .utf8)!

        let manifest1 = AppDataManifest(
            schemaVersion: 1,
            dataVersion: "2026.09.05.001",
            minimumClientVersion: "0.1.0",
            files: [
                ManifestFileEntry(path: "unchanged.json", sha256: validator.sha256Hex(data: unchangedData), size: unchangedData.count),
                ManifestFileEntry(path: "changed.json", sha256: validator.sha256Hex(data: changedDataV1), size: changedDataV1.count)
            ]
        )
        let report1 = await updateManager.performUpdate(manifest: manifest1, fileDataMap: ["unchanged.json": unchangedData, "changed.json": changedDataV1])
        XCTAssertEqual(report1.status, .committed)
        XCTAssertEqual(report1.installedDataVersion, "2026.09.05.001")

        // 2. Delta update v2: Manifest contains ONLY changed.json ("v2")
        let changedDataV2 = "v2".data(using: .utf8)!
        let manifest2 = AppDataManifest(
            schemaVersion: 1,
            dataVersion: "2026.09.05.002",
            minimumClientVersion: "0.1.0",
            files: [
                ManifestFileEntry(path: "changed.json", sha256: validator.sha256Hex(data: changedDataV2), size: changedDataV2.count)
            ]
        )
        let report2 = await updateManager.performUpdate(manifest: manifest2, fileDataMap: ["changed.json": changedDataV2])
        XCTAssertEqual(report2.status, .committed)
        XCTAssertEqual(report2.installedDataVersion, "2026.09.05.002")

        // Verify active directory preserves unchanged.json ("old") and updates changed.json ("v2")
        let activeDir = tempDir.appendingPathComponent("data/active")
        let unchangedFile = activeDir.appendingPathComponent("unchanged.json")
        let changedFile = activeDir.appendingPathComponent("changed.json")

        XCTAssertTrue(FileManager.default.fileExists(atPath: unchangedFile.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: changedFile.path))
        XCTAssertEqual(try? String(contentsOf: unchangedFile, encoding: .utf8), "old")
        XCTAssertEqual(try? String(contentsOf: changedFile, encoding: .utf8), "v2")

        // 3. Failed update with bad hash -> Rollback preserves active dataset
        let badManifest = AppDataManifest(
            schemaVersion: 1,
            dataVersion: "2026.09.05.003",
            minimumClientVersion: "0.1.0",
            files: [
                ManifestFileEntry(path: "changed.json", sha256: "bad_hash", size: changedDataV2.count)
            ]
        )
        let badReport = await updateManager.performUpdate(manifest: badManifest, fileDataMap: ["changed.json": changedDataV2])
        XCTAssertEqual(badReport.status, .failed)
        XCTAssertEqual(badReport.installedDataVersion, "2026.09.05.002")

        XCTAssertEqual(try? String(contentsOf: unchangedFile, encoding: .utf8), "old")
        XCTAssertEqual(try? String(contentsOf: changedFile, encoding: .utf8), "v2")
    }

    func test10_versionDowngradeProtection() async {
        let validator = DataUpdateValidator()
        let sampleData = "v100_data".data(using: .utf8)!
        let hash = validator.sha256Hex(data: sampleData)

        let manifest1 = AppDataManifest(
            schemaVersion: 1,
            dataVersion: "2026.09.05.100",
            minimumClientVersion: "0.1.0",
            files: [ManifestFileEntry(path: "config.json", sha256: hash, size: sampleData.count)]
        )
        let report1 = await updateManager.performUpdate(manifest: manifest1, fileDataMap: ["config.json": sampleData])
        XCTAssertEqual(report1.status, .committed)
        XCTAssertEqual(report1.installedDataVersion, "2026.09.05.100")

        // Same version -> NO-OP / UP_TO_DATE
        let reportSame = await updateManager.performUpdate(manifest: manifest1, fileDataMap: ["config.json": sampleData])
        XCTAssertEqual(reportSame.status, .upToDate)
        XCTAssertEqual(reportSame.installedDataVersion, "2026.09.05.100")

        // Older version -> REJECTED / FAILED
        let olderData = "v050_data".data(using: .utf8)!
        let olderHash = validator.sha256Hex(data: olderData)
        let manifestOlder = AppDataManifest(
            schemaVersion: 1,
            dataVersion: "2026.09.05.050",
            minimumClientVersion: "0.1.0",
            files: [ManifestFileEntry(path: "config.json", sha256: olderHash, size: olderData.count)]
        )
        let reportOlder = await updateManager.performUpdate(manifest: manifestOlder, fileDataMap: ["config.json": olderData])
        XCTAssertEqual(reportOlder.status, .failed)
        XCTAssertTrue(reportOlder.lastError?.contains("Version Downgrade Rejected") ?? false)
        XCTAssertEqual(reportOlder.installedDataVersion, "2026.09.05.100")

        // Active dataset remains original v100 data
        let activeFile = tempDir.appendingPathComponent("data/active/config.json")
        XCTAssertEqual(try? String(contentsOf: activeFile, encoding: .utf8), "v100_data")
    }

    func test11_offlineUpdateCheck_preservesAgentCoreOperation() async {
        // Checking updates offline without network or mock returns offline status without breaking AgentCore
        let report = await updateManager.checkForUpdates()
        XCTAssertEqual(report.status, .offline)
        XCTAssertTrue(report.isOffline)

        // Local Agent Core run continues normally
        let runRes = await service.run(goal: "Offline operation read status", userApproved: true)
        XCTAssertEqual(runRes.status, .success)
    }

    func test12_forgetMemory_removesKeyFromStore() async {
        let saveRes = await service.remember(key: "test_key", value: "test_val")
        XCTAssertEqual(saveRes.status, .success)

        let retrieved = await service.retrieve(query: "test_key")
        XCTAssertEqual(retrieved.count, 1)

        let forgetRes = await service.forget(key: "test_key")
        XCTAssertEqual(forgetRes.status, .success)

        let afterForget = await service.retrieve(query: "test_key")
        XCTAssertEqual(afterForget.count, 0)

        let nonExistentRes = await service.forget(key: "non_existent_key")
        XCTAssertEqual(nonExistentRes.status, .failed)
    }

    func test12b_runRememberGoal_writesMemoryWithoutFakeSteps() async {
        let res = await service.run(goal: "Remember that my favorite color is blue", userApproved: true)
        XCTAssertEqual(res.status, .success)
        XCTAssertEqual(res.verificationVerdict, "PASS")
        XCTAssertEqual(res.planSteps.count, 1)
        let items = await service.retrieve(query: "favorite color")
        XCTAssertTrue(items.contains(where: { $0.value.lowercased().contains("blue") }), "remember goal must persist the fact")
    }

    @MainActor
    func test13_agentAppViewModel_interactiveReviewChecksPass() async {
        let viewModel = AgentAppViewModel(service: service, updateManager: updateManager)
        await viewModel.runAllReviewChecks()

        XCTAssertEqual(viewModel.passCount, 10)
        XCTAssertEqual(viewModel.failCount, 0)
        XCTAssertEqual(viewModel.blockerDetails.count, 0)
        XCTAssertEqual(viewModel.agentCoreStatus, ReviewCheckStatus.pass)
        XCTAssertEqual(viewModel.agentRuntimeStatus, ReviewCheckStatus.pass)
        XCTAssertEqual(viewModel.localStorageStatus, ReviewCheckStatus.pass)
        XCTAssertEqual(viewModel.memoryVaultStatus, ReviewCheckStatus.pass)
        XCTAssertEqual(viewModel.connectionStatus, ReviewCheckStatus.pass)
    }

    func test14_runPolicyEnforcement_unapprovedMutatingGoalDenied() async {
        let res = await service.run(goal: "Delete all context data", userApproved: false)
        XCTAssertEqual(res.status, .denied)
        XCTAssertEqual(res.errorCode, "POLICY_DENIAL")
        XCTAssertFalse(res.authorized)
        XCTAssertEqual(res.verificationVerdict, "DENIED")
    }

    func test15_runPolicyEnforcement_approvedMutatingGoalAllowed() async {
        let res = await service.run(goal: "Delete all context data", userApproved: true)
        XCTAssertEqual(res.status, .success)
        XCTAssertTrue(res.authorized)
        XCTAssertEqual(res.verificationVerdict, "PASS")
    }

    func test16_runValidation_emptyGoalFailed() async {
        let res = await service.run(goal: "", userApproved: false)
        XCTAssertEqual(res.status, .failed)
        XCTAssertEqual(res.errorCode, "INVALID_INPUT")
        XCTAssertEqual(res.verificationVerdict, "FAIL")
    }

    func test17_cancelRun_persistsCancelledCheckpointAndOutcome() async {
        let runRes = await service.run(goal: "Goal to cancel", userApproved: true)
        let cancelRes = await service.cancelRun(runId: runRes.runId)

        XCTAssertEqual(cancelRes.runId, runRes.runId)
        XCTAssertEqual(cancelRes.errorCode, "CANCELLED")
        XCTAssertEqual(cancelRes.verificationVerdict, "CANCELLED")

        let storedRun = await service.getRun(runId: runRes.runId)
        XCTAssertEqual(storedRun?.errorCode, "CANCELLED")
    }

    // MARK: - Additive UI Contract Tests

    func test18_currentAgentStatus_returnsReady() async {
        let status = await service.currentAgentStatus()
        XCTAssertEqual(status, .ready)
    }

    func test19_runStreaming_emitsLifecycleEvents() async {
        let collector = EventCollector()
        let result = await service.runStreaming(
            goal: "Streamed test goal",
            userApproved: true,
            capabilityDispatch: (capabilityId: "mock.echo", input: ["action": "echo", "text": "hello"]),
            onEvent: { event in
                collector.add(event.phase)
            }
        )

        XCTAssertEqual(result.status, .success)
        let emittedPhases = collector.phases
        XCTAssertTrue(emittedPhases.contains(.taskStarted))
        XCTAssertTrue(emittedPhases.contains(.execution))
        XCTAssertTrue(emittedPhases.contains(.planCreated))
        XCTAssertTrue(emittedPhases.contains(.verify))
        XCTAssertTrue(emittedPhases.contains(.taskCompleted))
    }

    func test20_cancel_stopsUnfinishedRun() async {
        // 1. Cancelling a non-existent runId returns false
        let nonExistentRes = await service.cancel(runId: "RUN-NONEXISTENT-999")
        XCTAssertFalse(nonExistentRes)

        // 2. Cancelling an already finished run returns false
        let finishedRun = await service.run(goal: "Goal to finish", userApproved: true)
        let finishedCancelRes = await service.cancel(runId: finishedRun.runId)
        XCTAssertFalse(finishedCancelRes)

        // 3. Cancelling a non-terminal / checkpointed run returns true
        let pendingRun = AgentRunResult(runId: "RUN-PENDING-001", status: .notExecuted, goal: "Pending goal")
        chkStore.save(result: pendingRun)

        let pendingCancelRes = await service.cancel(runId: "RUN-PENDING-001")
        XCTAssertTrue(pendingCancelRes)
    }

    func test21_pendingApproval_recordedOnPolicyDenial() async {
        let runRes = await service.runStreaming(
            goal: "Delete all files in folder",
            userApproved: false,
            capabilityDispatch: nil,
            onEvent: { _ in }
        )

        XCTAssertEqual(runRes.status, .denied)
        let req = await service.pendingApproval(runId: runRes.runId)
        XCTAssertNotNil(req)
        XCTAssertEqual(req?.runId, runRes.runId)
    }

    func test22_listActivity_returnsFilterableRecords() async {
        _ = await service.run(goal: "Success task", userApproved: true)
        _ = await service.run(goal: "Delete database", userApproved: false)

        let all = await service.listActivity(filter: .all)
        let successOnly = await service.listActivity(filter: .success)
        let failedOnly = await service.listActivity(filter: .failed)

        XCTAssertGreaterThanOrEqual(all.count, 2)
        XCTAssertTrue(successOnly.allSatisfy { $0.status == .success })
        XCTAssertTrue(failedOnly.allSatisfy { $0.status == .failed || $0.status == .denied })
        XCTAssertTrue(failedOnly.contains(where: { $0.status == .denied }))
        XCTAssertTrue(all.allSatisfy { $0.durationSeconds >= 0.0 })
    }

    func test23_vaultSummary_calculatesMetrics() async {
        _ = await service.remember(key: "preference1", value: "val1")

        let summary = await service.vaultSummary()
        XCTAssertTrue(summary.isOperational)
        XCTAssertGreaterThanOrEqual(summary.totalItemsCount, 1)
        XCTAssertGreaterThanOrEqual(summary.categoriesCount["user_preference"] ?? 0, 1)
    }

    func test24_listConnections_returnsLocalAndRemoteCapabilities() async {
        let connections = await service.listConnections()
        XCTAssertGreaterThanOrEqual(connections.count, 2)

        let localCap = connections.first(where: { $0.kind == .local })
        let remoteCap = connections.first(where: { $0.kind == .remote })

        XCTAssertNotNil(localCap)
        XCTAssertNotNil(remoteCap)
        XCTAssertEqual(localCap?.state, .localActive)
    }

    // MARK: - Reducer Unit Tests (Phase 2 Requirement 13)

    func test25_reducer_idleToExecutionStarted() {
        let initial = AgentRuntimeState()
        XCTAssertEqual(initial.phase, .idle)

        let next = AgentRuntimeReducer.reduce(
            state: initial,
            event: .executionStarted(goal: "Test Goal", executionId: "RUN-100")
        )

        XCTAssertEqual(next.phase, .thinking)
        XCTAssertEqual(next.currentGoal, "Test Goal")
        XCTAssertEqual(next.executionId, "RUN-100")
        XCTAssertEqual(next.progress, 0.0)
    }

    func test26_reducer_executionStartedToExecuting() {
        var state = AgentRuntimeState()
        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .executionStarted(goal: "Test Goal", executionId: "RUN-101")
        )

        let planSteps = ["Step 1", "Step 2", "Step 3", "Step 4"]
        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .planGenerated(steps: planSteps)
        )

        XCTAssertEqual(state.phase, .executing)
        XCTAssertEqual(state.totalSteps, 4)
        XCTAssertEqual(state.steps.count, 4)
        XCTAssertEqual(state.progress, 0.0)
    }

    func test27_reducer_stepStartedAndCompleted() {
        var state = AgentRuntimeState()
        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .executionStarted(goal: "Test Goal", executionId: "RUN-102")
        )
        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .planGenerated(steps: ["Step 1", "Step 2", "Step 3", "Step 4"])
        )

        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .stepStarted(stepId: "STEP-1", title: "Step 1", index: 0)
        )
        XCTAssertEqual(state.steps[0].status, .active)

        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .stepCompleted(stepId: "STEP-1")
        )
        XCTAssertEqual(state.steps[0].status, .completed)
        XCTAssertEqual(state.progress, 0.25)
    }

    func test28_reducer_multipleStepProgressCalculation() {
        var state = AgentRuntimeState()
        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .executionStarted(goal: "Progress Calculation Goal", executionId: "RUN-103")
        )
        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .planGenerated(steps: ["Step 1", "Step 2", "Step 3", "Step 4"])
        )

        // 0/4 completed -> progress = 0.0
        XCTAssertEqual(state.progress, 0.0)

        // 1/4 completed -> progress = 0.25
        state = AgentRuntimeReducer.reduce(state: state, event: .stepCompleted(stepId: "STEP-1"))
        XCTAssertEqual(state.progress, 0.25)

        // 2/4 completed -> progress = 0.5
        state = AgentRuntimeReducer.reduce(state: state, event: .stepCompleted(stepId: "STEP-2"))
        XCTAssertEqual(state.progress, 0.5)

        // 4/4 completed -> progress = 1.0
        state = AgentRuntimeReducer.reduce(state: state, event: .stepCompleted(stepId: "STEP-3"))
        state = AgentRuntimeReducer.reduce(state: state, event: .stepCompleted(stepId: "STEP-4"))
        XCTAssertEqual(state.progress, 1.0)
    }

    func test29_reducer_stepFailedAndErrorPropagation() {
        var state = AgentRuntimeState()
        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .executionStarted(goal: "Failing Goal", executionId: "RUN-104")
        )
        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .planGenerated(steps: ["Step 1", "Step 2"])
        )

        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .stepFailed(stepId: "STEP-1", error: "Network Timeout")
        )

        XCTAssertEqual(state.phase, .failed)
        XCTAssertEqual(state.error, "Network Timeout")
        XCTAssertEqual(state.steps[0].status, .failed)
        XCTAssertEqual(state.steps[0].errorMessage, "Network Timeout")
    }

    func test30_reducer_executionCompletedAndCancelled() {
        var state = AgentRuntimeState()
        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .executionStarted(goal: "Completion Goal", executionId: "RUN-105")
        )
        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .planGenerated(steps: ["Step 1", "Step 2"])
        )

        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .executionCompleted(output: "Done")
        )

        XCTAssertEqual(state.phase, .completed)
        XCTAssertEqual(state.progress, 1.0)

        // Test cancellation
        var cancelState = AgentRuntimeState()
        cancelState = AgentRuntimeReducer.reduce(
            state: cancelState,
            event: .executionStarted(goal: "Cancellation Goal", executionId: "RUN-106")
        )
        cancelState = AgentRuntimeReducer.reduce(
            state: cancelState,
            event: .executionCancelled
        )

        XCTAssertEqual(cancelState.phase, .cancelled)
        XCTAssertEqual(cancelState.error, "Execution cancelled by user")
    }

    func test31_reducer_newExecutionResetsPreviousState() {
        var state = AgentRuntimeState()
        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .executionStarted(goal: "Old Goal", executionId: "RUN-OLD")
        )
        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .planGenerated(steps: ["Old Step 1", "Old Step 2"])
        )
        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .executionFailed(error: "Previous Error")
        )

        XCTAssertEqual(state.phase, .failed)
        XCTAssertEqual(state.error, "Previous Error")

        // Start new execution
        state = AgentRuntimeReducer.reduce(
            state: state,
            event: .executionStarted(goal: "New Goal", executionId: "RUN-NEW")
        )

        XCTAssertEqual(state.phase, .thinking)
        XCTAssertEqual(state.currentGoal, "New Goal")
        XCTAssertEqual(state.executionId, "RUN-NEW")
        XCTAssertNil(state.error)
        XCTAssertEqual(state.totalSteps, 0)
        XCTAssertEqual(state.steps.count, 0)
        XCTAssertEqual(state.progress, 0.0)
    }

    // MARK: - Big Update Real Local Execution Behavioral Tests

    func test32_genericGoal_invokesRealProviderAndReturnsModelOutput() async {
        let mockProvider = MockLanguageModelProvider(fixedResponseText: "1. Organize inbox\n2. Schedule meetings\n3. Set priorities")
        let runtime = AgentRuntime(
            memoryStore: LocalMemoryStore(storageDir: tempDir.appendingPathComponent("mem_b1")),
            experienceStore: LocalExperienceStore(storageDir: tempDir.appendingPathComponent("exp_b1")),
            checkpointStore: LocalCheckpointStore(storageDir: tempDir.appendingPathComponent("chk_b1")),
            vaultStore: LocalVaultStore(storageDir: tempDir.appendingPathComponent("vlt_b1")),
            languageModelProvider: mockProvider
        )
        let localService = LocalAgentService(runtime: runtime)

        let result = await localService.run(goal: "Create a short plan for organizing my week.", userApproved: true)

        XCTAssertEqual(result.status, .success)
        XCTAssertEqual(result.verificationVerdict, "PASS")
        XCTAssertTrue(result.output?.contains("Organize inbox") ?? false)
        XCTAssertFalse(result.output?.contains("LocalDeterministicPlanner") ?? false)
        XCTAssertFalse(result.output?.contains("Successfully executed goal") ?? false)
        XCTAssertEqual(result.planSteps.count, 3)
    }

    func test33_providerFailure_producesFailedResultWithoutFallback() async {
        let mockProvider = MockLanguageModelProvider()
        mockProvider.setShouldFailLoad(true)

        let runtime = AgentRuntime(
            memoryStore: LocalMemoryStore(storageDir: tempDir.appendingPathComponent("mem_b2")),
            experienceStore: LocalExperienceStore(storageDir: tempDir.appendingPathComponent("exp_b2")),
            checkpointStore: LocalCheckpointStore(storageDir: tempDir.appendingPathComponent("chk_b2")),
            vaultStore: LocalVaultStore(storageDir: tempDir.appendingPathComponent("vlt_b2")),
            languageModelProvider: mockProvider
        )
        let localService = LocalAgentService(runtime: runtime)

        let result = await localService.run(goal: "Plan my schedule", userApproved: true)

        XCTAssertEqual(result.status, .failed)
        XCTAssertEqual(result.verificationVerdict, "FAIL")
        XCTAssertEqual(result.errorCode, "MODEL_NOT_LOADED")
        XCTAssertFalse(result.errorMessage?.isEmpty ?? true)
        XCTAssertFalse(result.output?.contains("Successfully executed goal") ?? false)
    }

    func test34_unloadedModel_failsClosedWithoutCloudOrMockFallback() async {
        let defaults = UserDefaults(suiteName: UUID().uuidString)!
        let settingsStore = LLMSettingsStore(defaults: defaults)
        settingsStore.save(LLMSettings(
            backend: .onDevice,
            onDeviceModelId: ModelCatalog.defaultModelId,
            remoteModel: "",
            baseURL: "",
            privacyMode: true
        ))

        let router = RoutingLanguageModelProvider(settingsStore: settingsStore)
        let runtime = AgentRuntime(
            memoryStore: LocalMemoryStore(storageDir: tempDir.appendingPathComponent("mem_b3")),
            experienceStore: LocalExperienceStore(storageDir: tempDir.appendingPathComponent("exp_b3")),
            checkpointStore: LocalCheckpointStore(storageDir: tempDir.appendingPathComponent("chk_b3")),
            vaultStore: LocalVaultStore(storageDir: tempDir.appendingPathComponent("vlt_b3")),
            languageModelProvider: router
        )
        let localService = LocalAgentService(runtime: runtime)

        let result = await localService.run(goal: "Organize my week", userApproved: true)

        XCTAssertEqual(result.status, .failed)
        XCTAssertEqual(result.verificationVerdict, "FAIL")
        XCTAssertEqual(result.errorCode, "MODEL_NOT_LOADED")
        XCTAssertNil(result.output)
    }

    func test35_cheapPaths_succeedWithoutModel() async {
        let mockProvider = MockLanguageModelProvider()
        mockProvider.setShouldFailLoad(true)

        let runtime = AgentRuntime(
            memoryStore: LocalMemoryStore(storageDir: tempDir.appendingPathComponent("mem_b4")),
            experienceStore: LocalExperienceStore(storageDir: tempDir.appendingPathComponent("exp_b4")),
            checkpointStore: LocalCheckpointStore(storageDir: tempDir.appendingPathComponent("chk_b4")),
            vaultStore: LocalVaultStore(storageDir: tempDir.appendingPathComponent("vlt_b4")),
            languageModelProvider: mockProvider
        )
        let localService = LocalAgentService(runtime: runtime)

        let rememberRes = await localService.run(goal: "Remember that my timezone is UTC", userApproved: true)
        XCTAssertEqual(rememberRes.status, .success)
        XCTAssertEqual(rememberRes.verificationVerdict, "PASS")

        let statusRes = await localService.run(goal: "status", userApproved: true)
        XCTAssertEqual(statusRes.status, .success)
        XCTAssertTrue(statusRes.output?.contains("Agent Status:") ?? false)

        let forgetRes = await localService.forget(key: "timezone")
        XCTAssertEqual(forgetRes.status, .success)
    }
}
