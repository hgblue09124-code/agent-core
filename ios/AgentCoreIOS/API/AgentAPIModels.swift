// ios/AgentCoreIOS/API/AgentAPIModels.swift
// Native iOS Local Agent API v0.1 Result & Spec Codable Models

import Foundation

/// Status enum representing operational outcomes deterministically.
public enum Status: String, Codable, Sendable {
    case success = "SUCCESS"
    case failed = "FAILED"
    case denied = "DENIED"
    case notExecuted = "NOT_EXECUTED"
}

/// Codable result model for Agent run and resume execution.
public struct AgentRunResult: Codable, Sendable, Identifiable {
    public var id: String { runId }
    public let runId: String
    public let status: Status
    public let goal: String
    public let output: String?
    public let createdAt: String
    public let updatedAt: String
    public let errorCode: String?
    public let errorMessage: String?
    public let planSteps: [String]
    public let authorized: Bool
    public let verificationVerdict: String

    public init(
        runId: String,
        status: Status,
        goal: String,
        output: String? = nil,
        createdAt: String = ISO8601DateFormatter().string(from: Date()),
        updatedAt: String = ISO8601DateFormatter().string(from: Date()),
        errorCode: String? = nil,
        errorMessage: String? = nil,
        planSteps: [String] = [],
        authorized: Bool = true,
        verificationVerdict: String = "PASS"
    ) {
        self.runId = runId
        self.status = status
        self.goal = goal
        self.output = output
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.errorCode = errorCode
        self.errorMessage = errorMessage
        self.planSteps = planSteps
        self.authorized = authorized
        self.verificationVerdict = verificationVerdict
    }
}

/// Codable memory item stored in local memory layer.
public struct MemoryItem: Codable, Sendable, Identifiable {
    public var id: String { memoryId }
    public let memoryId: String
    public let key: String
    public let value: String
    public let memoryType: String
    public let importance: Double
    public let createdAt: String
    public let updatedAt: String

    public init(
        memoryId: String,
        key: String,
        value: String,
        memoryType: String = "short_term",
        importance: Double = 0.5,
        createdAt: String = ISO8601DateFormatter().string(from: Date()),
        updatedAt: String = ISO8601DateFormatter().string(from: Date())
    ) {
        self.memoryId = memoryId
        self.key = key
        self.value = value
        self.memoryType = memoryType
        self.importance = importance
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }
}

/// Result model for memory creation/update operations.
public struct MemoryResult: Codable, Sendable {
    public let status: Status
    public let item: MemoryItem?
    public let errorMessage: String?

    public init(status: Status, item: MemoryItem? = nil, errorMessage: String? = nil) {
        self.status = status
        self.item = item
        self.errorMessage = errorMessage
    }
}

/// Specification model for pluggable capability modules.
public struct Capability: Codable, Sendable, Identifiable {
    public var id: String { capabilityId }
    public let capabilityId: String
    public let name: String
    public let description: String
    public let version: String
    public let readOnly: Bool
    public let requiresUserApproval: Bool
    public let isRemote: Bool

    public init(
        capabilityId: String,
        name: String,
        description: String,
        version: String = "1.0.0",
        readOnly: Bool = true,
        requiresUserApproval: Bool = false,
        isRemote: Bool = false
    ) {
        self.capabilityId = capabilityId
        self.name = name
        self.description = description
        self.version = version
        self.readOnly = readOnly
        self.requiresUserApproval = requiresUserApproval
        self.isRemote = isRemote
    }
}

/// Result model for capability execution.
public struct CapabilityResult: Codable, Sendable {
    public let capabilityId: String
    public let status: Status
    public let output: String?
    public let errorMessage: String?

    public init(capabilityId: String, status: Status, output: String? = nil, errorMessage: String? = nil) {
        self.capabilityId = capabilityId
        self.status = status
        self.output = output
        self.errorMessage = errorMessage
    }
}

/// Codable experience record for agent learning traceability.
public struct Experience: Codable, Sendable, Identifiable {
    public var id: String { runId }
    public let runId: String
    public let goal: String
    public let outcome: String
    public let durationSeconds: Double
    public let timestamp: String

    public init(
        runId: String,
        goal: String,
        outcome: String,
        durationSeconds: Double = 0.0,
        timestamp: String = ISO8601DateFormatter().string(from: Date())
    ) {
        self.runId = runId
        self.goal = goal
        self.outcome = outcome
        self.durationSeconds = durationSeconds
        self.timestamp = timestamp
    }
}

/// Health and diagnostic status model for native agent runtime.
public struct AgentHealth: Codable, Sendable {
    public let status: String
    public let isLocalOnly: Bool
    public let providerName: String
    public let providerStatus: String
    public let isVaultAvailable: Bool
    public let storagePath: String
    public let activeCapabilitiesCount: Int

    public init(
        status: String = "HEALTHY",
        isLocalOnly: Bool = true,
        providerName: String = "LocalDeterministicPlanner",
        providerStatus: String = "DETERMINISTIC_TEST",
        isVaultAvailable: Bool = true,
        storagePath: String = "Application Support/AgentCore/",
        activeCapabilitiesCount: Int = 2
    ) {
        self.status = status
        self.isLocalOnly = isLocalOnly
        self.providerName = providerName
        self.providerStatus = providerStatus
        self.isVaultAvailable = isVaultAvailable
        self.storagePath = storagePath
        self.activeCapabilitiesCount = activeCapabilitiesCount
    }
}

// MARK: - Additive UI Contract Models

/// High-level operational status of the Agent.
public enum AgentStatus: String, Codable, Sendable {
    case ready = "READY"
    case thinking = "THINKING"
    case running = "RUNNING"
    case offline = "OFFLINE"
}

/// Event lifecycle phases during execution (mirroring core.events.schema.EventPhase).
public enum AgentEventPhase: String, Codable, Sendable {
    case taskStarted = "TASK_STARTED"
    case planCreated = "PLAN_CREATED"
    case execution = "EXECUTION"
    case observation = "OBSERVATION"
    case verify = "VERIFY"
    case learning = "LEARNING"
    case experience = "EXPERIENCE"
    case memoryUpdated = "MEMORY_UPDATED"
    case taskCompleted = "TASK_COMPLETED"
    case taskFailed = "TASK_FAILED"
    case bootstrap = "BOOTSTRAP"
    case retrieve = "RETRIEVE"
    case reason = "REASON"
    case plan = "PLAN"
    case decide = "DECIDE"
    case authorize = "AUTHORIZE"
    case execute = "EXECUTE"
    case observeResult = "OBSERVE_RESULT"
    case replan = "REPLAN"
    case waitingForUser = "WAITING_FOR_USER"
}

/// Event execution status outcomes.
public enum AgentEventStatus: String, Codable, Sendable {
    case pending = "PENDING"
    case running = "RUNNING"
    case pass = "PASS"
    case fail = "FAIL"
    case ok = "OK"
    case error = "ERROR"
}

/// Streamed execution progress event.
public struct AgentRunEvent: Codable, Sendable, Identifiable {
    public var id: String { eventId }
    public let eventId: String
    public let runId: String
    public let phase: AgentEventPhase
    public let status: AgentEventStatus
    public let summary: String
    public let timestamp: String
    public let payload: [String: String]?

    public init(
        eventId: String = UUID().uuidString,
        runId: String,
        phase: AgentEventPhase,
        status: AgentEventStatus,
        summary: String,
        timestamp: String = ISO8601DateFormatter().string(from: Date()),
        payload: [String: String]? = nil
    ) {
        self.eventId = eventId
        self.runId = runId
        self.phase = phase
        self.status = status
        self.summary = summary
        self.timestamp = timestamp
        self.payload = payload
    }
}

/// Model capturing a pending authorization request when policy denies execution without user approval.
public struct PermissionRequest: Codable, Sendable, Identifiable {
    public var id: String { requestId }
    public let requestId: String
    public let runId: String
    public let capabilityId: String
    public let action: String
    public let input: [String: String]
    public let reason: String
    public let createdAt: String

    public init(
        requestId: String = UUID().uuidString,
        runId: String,
        capabilityId: String,
        action: String = "",
        input: [String: String] = [:],
        reason: String,
        createdAt: String = ISO8601DateFormatter().string(from: Date())
    ) {
        self.requestId = requestId
        self.runId = runId
        self.capabilityId = capabilityId
        self.action = action
        self.input = input
        self.reason = reason
        self.createdAt = createdAt
    }
}

/// Filter criteria for listing historical activities.
public enum ActivityFilter: String, Codable, Sendable {
    case all = "ALL"
    case success = "SUCCESS"
    case failed = "FAILED"
}

/// Summary record of a past run or activity.
public struct ActivityRecord: Codable, Sendable, Identifiable {
    public var id: String { recordId }
    public let recordId: String
    public let runId: String
    public let goal: String
    public let status: Status
    public let durationSeconds: Double
    public let createdAt: String

    // Computed properties for UI compatibility
    public var task: String { goal }
    public var state: String { status.rawValue }
    public var timestamp: String { createdAt }
    public var duration: String { String(format: "%.2fs", durationSeconds) }
    public var resultOrError: String { status == .success ? "Success" : "Failed" }

    public init(
        recordId: String = UUID().uuidString,
        runId: String = "",
        goal: String,
        status: Status,
        durationSeconds: Double = 0.0,
        createdAt: String = ISO8601DateFormatter().string(from: Date())
    ) {
        self.recordId = recordId
        self.runId = runId.isEmpty ? recordId : runId
        self.goal = goal
        self.status = status
        self.durationSeconds = durationSeconds
        self.createdAt = createdAt
    }
}

/// Personal Vault category classification.
public enum VaultCategory: String, Codable, Sendable {
    case userPreference = "user_preference"
    case runHistory = "run_history"
    case credential = "credential"
    case document = "document"
    case uncategorized = "uncategorized"
}

/// Summary metrics of the personal vault storage.
public struct VaultSummary: Codable, Sendable {
    public let isOperational: Bool
    public let totalItemsCount: Int
    public let categoriesCount: [String: Int]
    public let storageBytes: Int64

    public init(
        isOperational: Bool = true,
        totalItemsCount: Int = 0,
        categoriesCount: [String: Int] = [:],
        storageBytes: Int64 = 0
    ) {
        self.isOperational = isOperational
        self.totalItemsCount = totalItemsCount
        self.categoriesCount = categoriesCount
        self.storageBytes = storageBytes
    }
}

/// Type of capability connection (local vs remote).
public enum ConnectionKind: String, Codable, Sendable {
    case local = "LOCAL"
    case remote = "REMOTE"
}

/// Operational state of a connection capability.
public enum ConnectionState: String, Codable, Sendable {
    case localActive = "LOCAL_ACTIVE"
    case remoteConfigured = "REMOTE_CONFIGURED"
    case remoteNotConfigured = "REMOTE_NOT_CONFIGURED"
}

/// Detailed connection status model for UI dashboard.
public struct ConnectionStatus: Codable, Sendable, Identifiable {
    public var id: String { capabilityId }
    public let capabilityId: String
    public let name: String
    public let kind: ConnectionKind
    public let state: ConnectionState
    public let description: String
    public let requiresApproval: Bool

    public init(
        capabilityId: String,
        name: String,
        kind: ConnectionKind,
        state: ConnectionState,
        description: String,
        requiresApproval: Bool
    ) {
        self.capabilityId = capabilityId
        self.name = name
        self.kind = kind
        self.state = state
        self.description = description
        self.requiresApproval = requiresApproval
    }
}
