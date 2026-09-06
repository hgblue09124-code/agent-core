// ios/AgentCoreIOS/Runtime/AgentRuntimeState.swift
// Single Source of Truth for Agent Execution State

import Foundation

public enum AgentExecutionPhase: String, Codable, Sendable, Equatable {
    case idle
    case thinking
    case planning
    case executing
    case completed
    case failed
    case cancelled
}

public enum ExecutionStepStatus: String, Codable, Sendable, Equatable {
    case completed
    case active
    case pending
    case failed
}

public struct ExecutionStepInfo: Codable, Sendable, Identifiable, Equatable {
    public var id: String { stepId }
    public let stepId: String
    public let title: String
    public let index: Int
    public var status: ExecutionStepStatus
    public var errorMessage: String?

    public init(
        stepId: String,
        title: String,
        index: Int,
        status: ExecutionStepStatus = .pending,
        errorMessage: String? = nil
    ) {
        self.stepId = stepId
        self.title = title
        self.index = index
        self.status = status
        self.errorMessage = errorMessage
    }
}

public struct AgentRuntimeState: Codable, Sendable, Equatable {
    public var phase: AgentExecutionPhase
    public var currentGoal: String
    public var executionId: String?
    public var currentStep: Int
    public var totalSteps: Int
    public var steps: [ExecutionStepInfo]
    public var progress: Double
    public var error: String?
    public var startedAt: Date?
    public var completedAt: Date?

    public init(
        phase: AgentExecutionPhase = .idle,
        currentGoal: String = "",
        executionId: String? = nil,
        currentStep: Int = 0,
        totalSteps: Int = 0,
        steps: [ExecutionStepInfo] = [],
        progress: Double = 0.0,
        error: String? = nil,
        startedAt: Date? = nil,
        completedAt: Date? = nil
    ) {
        self.phase = phase
        self.currentGoal = currentGoal
        self.executionId = executionId
        self.currentStep = currentStep
        self.totalSteps = totalSteps
        self.steps = steps
        self.progress = progress
        self.error = error
        self.startedAt = startedAt
        self.completedAt = completedAt
    }

    public var status: AgentStatus {
        switch phase {
        case .idle, .completed, .failed, .cancelled:
            return .ready
        case .thinking, .planning:
            return .thinking
        case .executing:
            return .running
        }
    }
}
