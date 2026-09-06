// ios/AgentCoreIOS/Runtime/AgentRuntimeEvent.swift
// Event Models for Agent Runtime Execution Lifecycle

import Foundation

public enum AgentRuntimeEvent: Sendable, Equatable {
    case executionStarted(goal: String, executionId: String)
    case thinkingStarted
    case planningStarted
    case planGenerated(steps: [String])
    case stepStarted(stepId: String, title: String, index: Int)
    case stepCompleted(stepId: String)
    case stepFailed(stepId: String, error: String)
    case executionCompleted(output: String?)
    case executionFailed(error: String)
    case executionCancelled
}
