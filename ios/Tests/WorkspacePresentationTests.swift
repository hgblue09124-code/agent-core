// ios/Tests/WorkspacePresentationTests.swift
// Adapter + Home workspace submit: chat → processing → result. No Runtime changes.

import XCTest
@testable import AgentCoreIOS

final class WorkspacePresentationTests: XCTestCase {
    func testIdleMapsToIdleWithoutResult() {
        let snap = WorkspacePresentation.map(state: AgentRuntimeState(), lastResult: nil)
        XCTAssertEqual(snap.presence, .idle)
        XCTAssertFalse(snap.isWorking)
        XCTAssertFalse(snap.resultPresent)
        XCTAssertFalse(snap.showsProgress)
        XCTAssertEqual(snap.activityHeadline, "Ready for a task")
    }

    func testThinkingMapsToThinking() {
        var state = AgentRuntimeState()
        state.phase = .thinking
        state.currentGoal = "Remember blue"
        let snap = WorkspacePresentation.map(state: state, lastResult: nil)
        XCTAssertEqual(snap.presence, .thinking)
        XCTAssertTrue(snap.isWorking)
        XCTAssertFalse(snap.resultPresent)
        XCTAssertTrue(snap.canCancel)
        XCTAssertEqual(snap.activityHeadline, "Thinking…")
    }

    func testExecutingWithPartialStepsMapsToToolProgress() {
        var state = AgentRuntimeState()
        state.phase = .executing
        state.currentGoal = "Run task"
        state.steps = [
            ExecutionStepInfo(stepId: "STEP-1", title: "Remember fact", index: 0, status: .completed),
            ExecutionStepInfo(stepId: "STEP-2", title: "Verify memory", index: 1, status: .active)
        ]
        state.progress = 0.5
        let snap = WorkspacePresentation.map(state: state, lastResult: nil)
        XCTAssertEqual(snap.presence, .toolProgress)
        XCTAssertTrue(snap.showsProgress)
        XCTAssertEqual(snap.activityHeadline, "Verify memory")
        XCTAssertTrue(snap.canCancel)
    }

    func testCompletedResultUsesRunOutput() {
        var state = AgentRuntimeState()
        state.phase = .completed
        state.currentGoal = "Remember that my favorite color is blue"
        state.progress = 1.0
        let result = AgentRunResult(
            runId: "RUN-1",
            status: .success,
            goal: state.currentGoal,
            output: "Remembered favorite color."
        )
        let snap = WorkspacePresentation.map(state: state, lastResult: result)
        XCTAssertEqual(snap.presence, .resultReady)
        XCTAssertTrue(snap.resultPresent)
        XCTAssertTrue(snap.resultOK)
        XCTAssertEqual(snap.resultBody, "Remembered favorite color.")
        XCTAssertEqual(snap.agentReply?.text, "Remembered favorite color.")
        XCTAssertEqual(snap.agentReply?.kicker, "Result")
    }

    func testFailedMapsToErrorAndRetry() {
        var state = AgentRuntimeState()
        state.phase = .failed
        state.currentGoal = "Do a thing"
        state.error = "Policy Denial"
        let snap = WorkspacePresentation.map(state: state, lastResult: nil)
        XCTAssertEqual(snap.presence, .error)
        XCTAssertTrue(snap.canRetry)
        XCTAssertFalse(snap.canCancel)
        XCTAssertEqual(snap.resultHeadline, "Couldn't finish")
        XCTAssertEqual(snap.agentReply?.kicker, "Error")
    }

    @MainActor
    func testSubmitWorkspaceMessageStaysOnHomeAndRecordsChatResult() async {
        let tempDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try? FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        let runtime = AgentRuntime(
            memoryStore: LocalMemoryStore(storageDir: tempDir.appendingPathComponent("memories")),
            experienceStore: LocalExperienceStore(storageDir: tempDir.appendingPathComponent("experiences")),
            checkpointStore: LocalCheckpointStore(storageDir: tempDir.appendingPathComponent("runs")),
            vaultStore: LocalVaultStore(storageDir: tempDir.appendingPathComponent("vault"))
        )
        let service = LocalAgentService(runtime: runtime)
        let viewModel = AgentAppViewModel(
            service: service,
            updateManager: GitHubDataUpdateManager(storageDir: tempDir.appendingPathComponent("data"))
        )

        XCTAssertEqual(viewModel.selectedTab, .home)
        await viewModel.submitWorkspaceMessage("Remember that my favorite color is blue")

        XCTAssertEqual(viewModel.selectedTab, .home)
        XCTAssertEqual(viewModel.conversation.count, 2)
        XCTAssertEqual(viewModel.conversation[0].role, .user)
        XCTAssertEqual(viewModel.conversation[1].role, .agent)
        XCTAssertEqual(viewModel.lastRunResult?.status, .success)
        XCTAssertEqual(viewModel.runtimeStore.state.phase, .completed)
        XCTAssertFalse(viewModel.conversation[1].text.isEmpty)
    }
}
