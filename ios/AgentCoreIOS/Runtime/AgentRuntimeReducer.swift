// ios/AgentCoreIOS/Runtime/AgentRuntimeReducer.swift
// Deterministic Pure State Reducer for Agent Execution

import Foundation

public struct AgentRuntimeReducer: Sendable {
    public init() {}

    public static func reduce(state: AgentRuntimeState, event: AgentRuntimeEvent) -> AgentRuntimeState {
        var newState = state

        switch event {
        case .executionStarted(let goal, let executionId):
            newState.phase = .thinking
            newState.currentGoal = goal
            newState.executionId = executionId
            newState.currentStep = 0
            newState.totalSteps = 0
            newState.steps = []
            newState.progress = 0.0
            newState.error = nil
            newState.startedAt = Date()
            newState.completedAt = nil

        case .thinkingStarted:
            newState.phase = .thinking

        case .planningStarted:
            newState.phase = .planning

        case .planGenerated(let planSteps):
            newState.phase = .executing
            newState.totalSteps = planSteps.count
            newState.steps = planSteps.enumerated().map { idx, stepTitle in
                ExecutionStepInfo(
                    stepId: "STEP-\(idx + 1)",
                    title: stepTitle,
                    index: idx,
                    status: .pending
                )
            }
            newState.currentStep = 0
            newState.progress = planSteps.isEmpty ? 0.0 : 0.0

        case .stepStarted(let stepId, let title, let index):
            newState.phase = .executing
            newState.currentStep = index
            if let idx = newState.steps.firstIndex(where: { $0.stepId == stepId || $0.index == index }) {
                newState.steps[idx].status = .active
            } else {
                let newStep = ExecutionStepInfo(
                    stepId: stepId,
                    title: title,
                    index: index,
                    status: .active
                )
                newState.steps.append(newStep)
                newState.totalSteps = max(newState.totalSteps, newState.steps.count)
            }
            recomputeProgress(&newState)

        case .stepCompleted(let stepId):
            if let idx = newState.steps.firstIndex(where: { $0.stepId == stepId }) {
                newState.steps[idx].status = .completed
            }
            recomputeProgress(&newState)

        case .stepFailed(let stepId, let error):
            if let idx = newState.steps.firstIndex(where: { $0.stepId == stepId }) {
                newState.steps[idx].status = .failed
                newState.steps[idx].errorMessage = error
            }
            newState.phase = .failed
            newState.error = error
            newState.completedAt = Date()
            recomputeProgress(&newState)

        case .executionCompleted:
            newState.phase = .completed
            for idx in 0..<newState.steps.count {
                if newState.steps[idx].status == .active || newState.steps[idx].status == .pending {
                    newState.steps[idx].status = .completed
                }
            }
            newState.progress = 1.0
            newState.completedAt = Date()

        case .executionFailed(let error):
            newState.phase = .failed
            newState.error = error
            newState.completedAt = Date()
            recomputeProgress(&newState)

        case .executionCancelled:
            newState.phase = .cancelled
            newState.error = "Execution cancelled by user"
            newState.completedAt = Date()
            recomputeProgress(&newState)
        }

        return newState
    }

    private static func recomputeProgress(_ state: inout AgentRuntimeState) {
        guard state.totalSteps > 0 else {
            state.progress = (state.phase == .completed) ? 1.0 : 0.0
            return
        }
        let completedCount = state.steps.filter { $0.status == .completed }.count
        state.progress = min(1.0, max(0.0, Double(completedCount) / Double(state.totalSteps)))
    }
}
