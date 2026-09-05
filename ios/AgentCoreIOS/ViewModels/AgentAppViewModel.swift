// ios/AgentCoreIOS/ViewModels/AgentAppViewModel.swift
// State ViewModel and Service Bridge — Personal Agent iOS

import Foundation
import Combine
import SwiftUI

public struct ExecutionStep: Identifiable, Codable {
    public var id: String
    public var title: String
    public var status: String // "COMPLETED", "RUNNING", "PENDING", "FAILED"
    public var detail: String?

    public init(id: String = UUID().uuidString, title: String, status: String, detail: String? = nil) {
        self.id = id
        self.title = title
        self.status = status
        self.detail = detail
    }
}

public struct VaultCategory: Identifiable {
    public var id: String { name }
    public var name: String
    public var icon: String
    public var count: Int
}

public struct CapabilityConnection: Identifiable {
    public var id: String { name }
    public var name: String
    public var subtitle: String
    public var type: ConnectionType
    public var isConnected: Bool
}

@MainActor
public final class AgentAppViewModel: ObservableObject {
    // Current State
    @Published public var state: AgentState = .idle
    @Published public var selectedTab: Int = 0 // 0: Home, 1: Agent, 2: Activity, 3: Vault, 4: Connections, 5: Settings

    // Input & Goals
    @Published public var composerText: String = ""
    @Published public var currentGoal: String = "Draft replies to unread emails from this week and flag anything urgent."
    @Published public var currentRunId: String = "-"
    @Published public var progress: Double = 0.0

    // Execution Steps for Live Task View
    @Published public var liveSteps: [ExecutionStep] = []
    @Published public var lastOutput: String = "Ready"
    @Published public var failureReason: String? = nil

    // Activity Filter & Items
    @Published public var activityFilter: String = "All" // "All", "Success", "Failed"
    @Published public var experiences: [Experience] = []

    // Memory / Vault Items
    @Published public var searchQuery: String = ""
    @Published public var memories: [MemoryItem] = []
    @Published public var vaultCategories: [VaultCategory] = [
        VaultCategory(name: "Documents", icon: "folder", count: 128),
        VaultCategory(name: "Notes", icon: "doc.text", count: 54),
        VaultCategory(name: "Preferences", icon: "gearshape", count: 18),
        VaultCategory(name: "Credentials", icon: "key", count: 6)
    ]

    // Connections List
    @Published public var connections: [CapabilityConnection] = [
        CapabilityConnection(name: "Local Model", subtitle: "On-device · always available", type: .local, isConnected: true),
        CapabilityConnection(name: "GitHub Capabilities", subtitle: "Connected · remote API", type: .remote, isConnected: true),
        CapabilityConnection(name: "Calendar", subtitle: "Connected · remote", type: .remote, isConnected: true),
        CapabilityConnection(name: "Email Storage", subtitle: "Local personal vault · fallback", type: .local, isConnected: true)
    ]

    // Settings State
    @Published public var backgroundExecution: Bool = true
    @Published public var privacyMode: Bool = true
    @Published public var updateReport: DataUpdateStateReport = DataUpdateStateReport()

    private let service: LocalAgentServiceProtocol
    private let updateManager: GitHubDataUpdateManager
    private var activeTask: Task<Void, Never>? = nil

    public init(service: LocalAgentServiceProtocol? = nil, updateManager: GitHubDataUpdateManager? = nil) {
        self.service = service ?? LocalAgentService()
        self.updateManager = updateManager ?? GitHubDataUpdateManager()
        self.updateReport = self.updateManager.getStateReport()
        Task { await refreshData() }
    }

    // MARK: - Actions

    public func submitComposerTask() {
        let goal = composerText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !goal.isEmpty else { return }
        currentGoal = goal
        composerText = ""
        selectedTab = 1 // Switch to Execute View
        runTask(goal: currentGoal)
    }

    public func runTask(goal: String, userApproved: Bool = false) {
        guard state != .running && state != .thinking else { return }

        currentGoal = goal
        failureReason = nil
        progress = 0.1
        state = .thinking

        liveSteps = [
            ExecutionStep(title: "Observe workspace & personal context", status: "RUNNING"),
            ExecutionStep(title: "Reason goal decomposition", status: "PENDING"),
            ExecutionStep(title: "Authorize policy permissions", status: "PENDING"),
            ExecutionStep(title: "Execute capability dispatch", status: "PENDING"),
            ExecutionStep(title: "Verify task result & record experience", status: "PENDING")
        ]

        activeTask = Task {
            try? await Task.sleep(nanoseconds: 600_000_000) // 0.6s Thinking transition
            guard !Task.isCancelled else { return }

            self.state = .running
            self.progress = 0.35
            self.liveSteps[0].status = "COMPLETED"
            self.liveSteps[1].status = "RUNNING"

            try? await Task.sleep(nanoseconds: 700_000_000) // 0.7s
            guard !Task.isCancelled else { return }

            self.progress = 0.60
            self.liveSteps[1].status = "COMPLETED"
            self.liveSteps[2].status = "RUNNING"

            let result = await self.service.run(goal: goal, userApproved: userApproved)

            guard !Task.isCancelled else { return }

            self.currentRunId = result.runId
            self.lastOutput = result.output ?? "-"

            if result.status == .denied {
                self.state = .approvalRequired
                self.progress = 0.60
                self.liveSteps[2].status = "FAILED"
                self.liveSteps[2].detail = "Policy permission required for write operation"
                return
            }

            self.progress = 0.85
            self.liveSteps[2].status = "COMPLETED"
            self.liveSteps[3].status = "COMPLETED"
            self.liveSteps[4].status = "RUNNING"

            try? await Task.sleep(nanoseconds: 500_000_000)

            if result.status == .success {
                self.progress = 1.0
                self.state = .completed
                self.liveSteps[4].status = "COMPLETED"
            } else {
                self.state = .failed
                self.failureReason = result.errorMessage ?? "Task execution failed"
                self.liveSteps[4].status = "FAILED"
            }

            await self.refreshData()
        }
    }

    public func cancelTask() {
        guard state == .running || state == .thinking || state == .approvalRequired else { return }
        activeTask?.cancel()
        state = .cancelling
        progress = 0.0

        Task {
            try? await Task.sleep(nanoseconds: 500_000_000)
            self.state = .idle
            self.lastOutput = "Task cancelled by user"
            for i in 0..<self.liveSteps.count {
                if self.liveSteps[i].status == "RUNNING" {
                    self.liveSteps[i].status = "FAILED"
                    self.liveSteps[i].detail = "Cancelled"
                }
            }
        }
    }

    public func retryTask() {
        runTask(goal: currentGoal, userApproved: true)
    }

    public func approveWritePolicy() {
        runTask(goal: currentGoal, userApproved: true)
    }

    public func rememberFact(key: String, value: String) async {
        _ = await service.remember(key: key, value: value)
        await refreshData()
    }

    public func deleteMemory(key: String) async {
        _ = await service.forget(key: key)
        await refreshData()
    }

    public func checkForDataUpdates() async {
        updateReport = await updateManager.checkForUpdates()
    }

    public func syncDataNow() async {
        updateReport = await updateManager.syncNow()
    }

    public func refreshData() async {
        memories = await service.retrieve(query: searchQuery)
        experiences = await service.getExperience()
        updateReport = updateManager.getStateReport()
    }

    public var filteredExperiences: [Experience] {
        switch activityFilter {
        case "Success":
            return experiences.filter { $0.outcome.uppercased() == "COMPLETED" || $0.outcome.uppercased() == "SUCCESS" }
        case "Failed":
            return experiences.filter { $0.outcome.uppercased() == "FAILED" || $0.outcome.uppercased() == "DENIED" }
        default:
            return experiences
        }
    }
}
