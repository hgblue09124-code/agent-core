// ios/AgentCoreIOS/Runtime/AgentRuntimeStore.swift
// Store managing AgentRuntimeState and bridging with AgentRuntime execution

import Foundation
import SwiftUI

@MainActor
public final class AgentRuntimeStore: ObservableObject {
    @Published public private(set) var state: AgentRuntimeState

    private let service: LocalAgentServiceProtocol
    private var activeTask: Task<Void, Never>?

    public init(service: LocalAgentServiceProtocol? = nil, initialState: AgentRuntimeState = AgentRuntimeState()) {
        self.service = service ?? LocalAgentService()
        self.state = initialState
    }

    public func send(_ event: AgentRuntimeEvent) {
        state = AgentRuntimeReducer.reduce(state: state, event: event)
    }

    public func run(goal: String, userApproved: Bool = false) async {
        let trimmedGoal = goal.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedGoal.isEmpty else {
            send(.executionStarted(goal: goal, executionId: "RUN-INVALID"))
            send(.executionFailed(error: "Task goal cannot be empty."))
            return
        }

        let runId = String(format: "RUN-%05d", Int(Date().timeIntervalSince1970 * 1000) % 100000)
        send(.executionStarted(goal: trimmedGoal, executionId: runId))

        // Capture service (Sendable) immutably so the concurrent Task does not
        // need to touch the MainActor-isolated `self` until after the await.
        let service = self.service

        activeTask = Task { @MainActor [weak self] in
            let result = await service.runStreaming(
                goal: trimmedGoal,
                userApproved: userApproved,
                capabilityDispatch: nil,
                onEvent: { [weak self] runEvent in
                    Task { @MainActor [weak self] in
                        self?.handleRunEvent(runEvent)
                    }
                }
            )

            guard let self else { return }

            if result.status == .success {
                self.send(.executionCompleted(output: result.output))
            } else if result.status == .denied {
                self.send(.executionFailed(error: result.errorMessage ?? "Policy Denial: Explicit user approval required."))
            } else if result.errorCode == "CANCELLED" {
                self.send(.executionCancelled)
            } else {
                self.send(.executionFailed(error: result.errorMessage ?? "Execution failed."))
            }
        }

        await activeTask?.value
    }

    public func cancel() {
        if let runId = state.executionId {
            let currentService = service
            Task {
                _ = await currentService.cancel(runId: runId)
            }
        }
        activeTask?.cancel()
        send(.executionCancelled)
    }

    public func retry() async {
        let currentGoal = state.currentGoal
        guard !currentGoal.isEmpty else { return }
        await run(goal: currentGoal, userApproved: true)
    }

    private func handleRunEvent(_ event: AgentRunEvent) {
        switch event.phase {
        case .taskStarted:
            send(.thinkingStarted)

        case .planCreated, .plan:
            if let payloadSteps = event.payload?["planSteps"] {
                let steps = payloadSteps.components(separatedBy: "\n").filter { !$0.isEmpty }
                send(.planGenerated(steps: steps))
            } else {
                send(.planningStarted)
            }

        case .execution, .execute:
            let stepId = event.payload?["stepId"] ?? "STEP-\(state.currentStep + 1)"
            let title = event.summary
            send(.stepStarted(stepId: stepId, title: title, index: state.currentStep))

        case .observeResult:
            let stepId = event.payload?["stepId"] ?? "STEP-\(state.currentStep + 1)"
            if event.status == .pass || event.status == .ok {
                send(.stepCompleted(stepId: stepId))
            } else if event.status == .fail || event.status == .error {
                send(.stepFailed(stepId: stepId, error: event.summary))
            }

        case .taskCompleted:
            send(.executionCompleted(output: event.summary))

        case .taskFailed:
            if event.payload?["errorCode"] == "CANCELLED" {
                send(.executionCancelled)
            } else {
                send(.executionFailed(error: event.summary))
            }

        default:
            break
        }
    }
}
