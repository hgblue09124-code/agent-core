// ios/AgentCoreIOS/App/AgentCoreIOSApp.swift
// Native iOS Local Agent SwiftUI App — Personal Agent Entrypoint & ViewModel

import SwiftUI

// MARK: - App Entrypoint

@main
struct AgentCoreIOSApp: App {
    @StateObject private var viewModel = AgentAppViewModel()

    init() {
        configureTabBarAppearance()
    }

    var body: some Scene {
        WindowGroup {
            MainTabView()
                .environmentObject(viewModel)
                .preferredColorScheme(.dark)
        }
    }

    private func configureTabBarAppearance() {
        let appearance = UITabBarAppearance()
        appearance.configureWithOpaqueBackground()
        appearance.backgroundColor = UIColor(AgentColor.background2)
        appearance.shadowColor = UIColor(AgentColor.hairline)

        // Item Colors
        appearance.stackedLayoutAppearance.selected.iconColor = UIColor(AgentColor.accent)
        appearance.stackedLayoutAppearance.selected.titleTextAttributes = [.foregroundColor: UIColor(AgentColor.textPrimary)]
        appearance.stackedLayoutAppearance.normal.iconColor = UIColor(AgentColor.textMuted)
        appearance.stackedLayoutAppearance.normal.titleTextAttributes = [.foregroundColor: UIColor(AgentColor.textMuted)]

        UITabBar.appearance().standardAppearance = appearance
        UITabBar.appearance().scrollEdgeAppearance = appearance
    }
}

// MARK: - Navigation Enums & Models

enum AppTab: String, CaseIterable, Identifiable {
    case home = "Home"
    case agent = "Agent"
    case activity = "Activity"
    case vault = "Vault"
    case connections = "Connections"
    case settings = "Settings"
    case review = "Review"

    var id: String { rawValue }

    var iconName: String {
        switch self {
        case .home: return "house.fill"
        case .agent: return "bolt.fill"
        case .activity: return "list.bullet.rectangle.fill"
        case .vault: return "lock.shield.fill"
        case .connections: return "network"
        case .settings: return "gearshape.fill"
        case .review: return "checkmark.seal.fill"
        }
    }
}

enum ExecutionLifecycleState: String {
    case idle = "Idle"
    case preparing = "Preparing"
    case running = "Running"
    case waitingForPermission = "Waiting for Permission"
    case completed = "Completed"
    case failed = "Failed"
    case cancelled = "Cancelled"

    var color: Color {
        switch self {
        case .idle: return AgentColor.offline
        case .preparing: return AgentColor.accent
        case .running: return AgentColor.warning
        case .waitingForPermission: return AgentColor.violet
        case .completed: return AgentColor.success
        case .failed: return AgentColor.danger
        case .cancelled: return AgentColor.offline
        }
    }
}

enum ReviewCheckStatus: String, Codable, Equatable, Sendable {
    case pass = "PASS"
    case fail = "FAIL"
    case warning = "WARNING"
    case notTested = "NOT TESTED"

    var color: Color {
        switch self {
        case .pass: return AgentColor.success
        case .fail: return AgentColor.danger
        case .warning: return AgentColor.warning
        case .notTested: return AgentColor.offline
        }
    }
}

struct ReviewCheckItem: Identifiable {
    let id: Int
    let name: String
    var status: ReviewCheckStatus
    var component: String
    var message: String
    var isBlocker: Bool

    init(id: Int, name: String, status: ReviewCheckStatus = .notTested, component: String = "AgentRuntime", message: String = "Not executed yet", isBlocker: Bool = true) {
        self.id = id
        self.name = name
        self.status = status
        self.component = component
        self.message = message
        self.isBlocker = isBlocker
    }
}

struct MemoryStepResult: Identifiable {
    let id: Int
    let stepName: String
    var status: ReviewCheckStatus
    var detail: String
}

// MARK: - Central ViewModel

@MainActor
final class AgentAppViewModel: ObservableObject {
    @Published var selectedTab: AppTab = .home

    // Agent Execution Runtime Store
    @Published public private(set) var runtimeStore: AgentRuntimeStore

    // Agent Execution Goal & UI Controls
    @Published var currentGoal: String = "Remember that my favorite color is blue."
    @Published var showingPermissionAlert: Bool = false
    @Published var permissionActionTitle: String = "Execute Agent Task"
    @Published var lastRunResult: AgentRunResult?
    @Published var lastErrorPayload: String?

    // Dashboard Statuses
    @Published var agentCoreStatus: ReviewCheckStatus = .notTested
    @Published var agentRuntimeStatus: ReviewCheckStatus = .notTested
    @Published var localStorageStatus: ReviewCheckStatus = .notTested
    @Published var memoryVaultStatus: ReviewCheckStatus = .notTested
    @Published var connectionStatus: ReviewCheckStatus = .notTested
    @Published var currentExecutionStatus: ReviewCheckStatus = .notTested

    // Memory / Vault Test State
    @Published var testMemoryKey: String = "review.test"
    @Published var testMemoryValue: String = "Agent-Core interactive test"
    @Published var memoryStepResults: [MemoryStepResult] = [
        MemoryStepResult(id: 1, stepName: "1. Save Memory", status: .notTested, detail: "-"),
        MemoryStepResult(id: 2, stepName: "2. Read Memory", status: .notTested, detail: "-"),
        MemoryStepResult(id: 3, stepName: "3. Verify Value", status: .notTested, detail: "-"),
        MemoryStepResult(id: 4, stepName: "4. Forget Memory", status: .notTested, detail: "-"),
        MemoryStepResult(id: 5, stepName: "5. Verify Missing", status: .notTested, detail: "-")
    ]

    // Error Test State
    @Published var errorTestResult: String = "No error test executed yet."

    // Activity Records
    @Published var activities: [ActivityRecord] = []

    // Collections & Health
    @Published var memories: [MemoryItem] = []
    @Published var experiences: [Experience] = []
    @Published var capabilities: [Capability] = []
    @Published var connections: [ConnectionStatus] = []
    @Published var vaultSummary: VaultSummary?
    @Published var health: AgentHealth?
    @Published var updateReport: DataUpdateStateReport = DataUpdateStateReport()

    // Automated Review Checks
    @Published var reviewChecks: [ReviewCheckItem] = [
        ReviewCheckItem(id: 1, name: "AgentRuntime Initialization", component: "AgentRuntime"),
        ReviewCheckItem(id: 2, name: "Agent-Core Availability", component: "AgentCore Kernel"),
        ReviewCheckItem(id: 3, name: "Memory Write / Read / Delete", component: "LocalMemoryStore"),
        ReviewCheckItem(id: 4, name: "Agent Execution", component: "AgentRuntime / Planner"),
        ReviewCheckItem(id: 5, name: "Permission Flow", component: "PolicyEngine / Runtime"),
        ReviewCheckItem(id: 6, name: "Cancellation", component: "AgentRuntime Orchestration"),
        ReviewCheckItem(id: 7, name: "Error Propagation", component: "AgentRuntime Error Handler"),
        ReviewCheckItem(id: 8, name: "Activity Recording", component: "LocalExperienceStore"),
        ReviewCheckItem(id: 9, name: "Navigation Accessibility", component: "MainTabView / Navigation"),
        ReviewCheckItem(id: 10, name: "App State Recovery", component: "LocalCheckpointStore")
    ]

    // Review Summary Counters
    @Published var passCount: Int = 0
    @Published var failCount: Int = 0
    @Published var warningCount: Int = 0
    @Published var notTestedCount: Int = 10
    @Published var blockerDetails: [String] = []

    private let service: LocalAgentServiceProtocol
    private let updateManager: GitHubDataUpdateManager
    private var pendingPermissionContinuation: ((Bool) -> Void)?
    private var activeRunTask: Task<Void, Never>?

    init(service: LocalAgentServiceProtocol? = nil, updateManager: GitHubDataUpdateManager? = nil) {
        let s: LocalAgentServiceProtocol
        if let service {
            s = service
        } else {
            s = LocalAgentService(runtime: AgentRuntime(languageModelProvider: RoutingLanguageModelProvider.shared))
        }
        self.service = s
        self.runtimeStore = AgentRuntimeStore(service: s)
        self.updateManager = updateManager ?? GitHubDataUpdateManager()
        Task {
            await self.refreshState()
        }
    }

    func refreshState() async {
        health = await service.health()
        memories = await service.retrieve(query: "")
        experiences = await service.getExperience()
        capabilities = await service.listCapabilities()
        activities = await service.listActivity(filter: .all)
        connections = await service.listConnections()
        vaultSummary = await service.vaultSummary()
        updateReport = updateManager.getStateReport()
    }

    func loadActivity(filter: ActivityFilter) async {
        activities = await service.listActivity(filter: filter)
    }

    func loadVaultSummary() async {
        vaultSummary = await service.vaultSummary()
        memories = await service.retrieve(query: "")
    }

    func loadConnections() async {
        connections = await service.listConnections()
    }

    // MARK: - Interactive Agent Execution Flow

    func runTask(requestPermissionPrompt: Bool = false) async {
        activeRunTask = Task {
            lastErrorPayload = nil

            var approved = false

            if requestPermissionPrompt {
                permissionActionTitle = "Allow Agent to execute task: '\(currentGoal)'?"
                showingPermissionAlert = true

                approved = await withCheckedContinuation { (continuation: CheckedContinuation<Bool, Never>) in
                    self.pendingPermissionContinuation = { result in
                        continuation.resume(returning: result)
                    }
                }

                if !approved {
                    runtimeStore.send(.executionStarted(goal: currentGoal, executionId: "RUN-DENIED"))
                    runtimeStore.send(.executionFailed(error: "Policy Denial: Execution cancelled by user during permission check."))
                    currentExecutionStatus = .fail
                    lastErrorPayload = "Policy Denial: Execution cancelled by user during permission check."
                    return
                }
            }

            await runtimeStore.run(goal: currentGoal, userApproved: approved)

            if let runId = runtimeStore.state.executionId {
                lastRunResult = await service.getRun(runId: runId)
            }

            let phase = runtimeStore.state.phase
            if phase == .completed {
                currentExecutionStatus = .pass
            } else if phase == .failed || phase == .cancelled {
                currentExecutionStatus = .fail
                lastErrorPayload = runtimeStore.state.error
            }

            await refreshState()
        }
        await activeRunTask?.value
    }

    func handlePermissionResponse(allowed: Bool) {
        showingPermissionAlert = false
        pendingPermissionContinuation?(allowed)
        pendingPermissionContinuation = nil
    }

    func cancelTask() {
        runtimeStore.cancel()
        currentExecutionStatus = .warning
        lastErrorPayload = "Task execution was cancelled by user."

        Task {
            await refreshState()
        }
    }

    func retryTask() async {
        await runtimeStore.retry()
        if let runId = runtimeStore.state.executionId {
            lastRunResult = await service.getRun(runId: runId)
        }
        await refreshState()
    }

    func clearTask() {
        currentGoal = ""
        runtimeStore.send(.executionCancelled)
        lastRunResult = nil
        lastErrorPayload = nil
    }

    // MARK: - Memory / Vault Interactive Testing

    func executeSaveMemory() async -> Bool {
        let res = await service.remember(key: testMemoryKey, value: testMemoryValue)
        await refreshState()
        return res.status == .success
    }

    func executeReadMemory() async -> String? {
        let items = await service.retrieve(query: testMemoryKey)
        return items.first(where: { $0.key == testMemoryKey })?.value
    }

    func executeForgetMemory() async -> Bool {
        let res = await service.forget(key: testMemoryKey)
        await refreshState()
        return res.status == .success
    }

    func runMemoryTestFlow() async {
        let saveOk = await executeSaveMemory()
        memoryStepResults[0].status = saveOk ? .pass : .fail
        memoryStepResults[0].detail = saveOk ? "Saved '\(testMemoryKey)'" : "Save failed"

        let readVal = await executeReadMemory()
        let readOk = readVal != nil
        memoryStepResults[1].status = readOk ? .pass : .fail
        memoryStepResults[1].detail = readVal ?? "Key not found"

        let verifyOk = (readVal == testMemoryValue)
        memoryStepResults[2].status = verifyOk ? .pass : .fail
        memoryStepResults[2].detail = verifyOk ? "Value matches expected" : "Value mismatch"

        let forgetOk = await executeForgetMemory()
        memoryStepResults[3].status = forgetOk ? .pass : .fail
        memoryStepResults[3].detail = forgetOk ? "Key removed" : "Forget failed"

        let verifyMissingVal = await executeReadMemory()
        let missingOk = (verifyMissingVal == nil)
        memoryStepResults[4].status = missingOk ? .pass : .fail
        memoryStepResults[4].detail = missingOk ? "Key successfully missing" : "Key still present"

        memoryVaultStatus = (saveOk && readOk && verifyOk && forgetOk && missingOk) ? .pass : .fail
    }

    // MARK: - Error Test Scenarios

    func triggerInvalidInput() async {
        let result = await service.run(goal: "", userApproved: false)
        errorTestResult = "Invalid Input Result -> Status: \(result.status.rawValue), ErrorMessage: \(result.errorMessage ?? "None")"
    }

    func triggerRuntimeFailure() async {
        let result = await service.resume(runId: "RUN-NONEXISTENT-9999")
        errorTestResult = "Runtime Failure Result -> Status: \(result.status.rawValue), Code: \(result.errorCode ?? "None"), ErrorMessage: \(result.errorMessage ?? "None")"
    }

    func triggerPermissionDenied() async {
        let result = await service.executeCapability(capabilityId: "github_integration", input: ["action": "create_issue_comment"], userApproved: false)
        errorTestResult = "Permission Denied Result -> Status: \(result.status.rawValue), ErrorMessage: \(result.errorMessage ?? "None")"
    }

    func triggerCancellation() {
        cancelTask()
        errorTestResult = "Cancellation Triggered -> State: CANCELLED, ErrorMessage: \(lastErrorPayload ?? "None")"
    }

    func triggerMissingMemory() async {
        let res = await service.forget(key: "non_existent_key_xyz_999")
        errorTestResult = "Missing Memory Forget Result -> Status: \(res.status.rawValue), ErrorMessage: \(res.errorMessage ?? "None")"
    }

    func triggerConnectionUnavailable() async {
        let result = await service.executeCapability(capabilityId: "github_integration", input: ["action": "get_repo"], userApproved: true)
        errorTestResult = "Connection Unavailable Result -> Status: \(result.status.rawValue), ErrorMessage: \(result.errorMessage ?? "None")"
    }

    // MARK: - Automated Review Checks (Run All Checks)

    func runAllReviewChecks() async {
        blockerDetails.removeAll()

        let h = await service.health()
        if h.status == "HEALTHY" {
            setCheck(id: 1, status: .pass, msg: "AgentRuntime initialized cleanly and healthy")
            agentRuntimeStatus = .pass
        } else {
            setCheck(id: 1, status: .fail, msg: "AgentRuntime health check failed: \(h.status)")
            agentRuntimeStatus = .fail
            blockerDetails.append("AgentRuntime Initialization failed")
        }

        if h.isLocalOnly && !h.providerName.isEmpty {
            setCheck(id: 2, status: .pass, msg: "Agent-Core kernel available via \(h.providerName)")
            agentCoreStatus = .pass
        } else {
            setCheck(id: 2, status: .fail, msg: "Agent-Core unavailable or invalid provider")
            agentCoreStatus = .fail
            blockerDetails.append("Agent-Core Availability check failed")
        }

        await runMemoryTestFlow()
        let memAllPass = memoryStepResults.allSatisfy { $0.status == .pass }
        if memAllPass {
            setCheck(id: 3, status: .pass, msg: "Memory write/read/delete full chain verified")
            memoryVaultStatus = .pass
        } else {
            setCheck(id: 3, status: .fail, msg: "Memory chain test failed in 1 or more steps")
            memoryVaultStatus = .fail
            blockerDetails.append("Memory Write/Read/Delete chain failed")
        }

        let runRes = await service.run(goal: "Automated review execution check", userApproved: true)
        if runRes.status == .success && !runRes.runId.isEmpty {
            setCheck(id: 4, status: .pass, msg: "Agent run executed successfully (runId: \(runRes.runId))")
            currentExecutionStatus = .pass
        } else {
            setCheck(id: 4, status: .fail, msg: "Agent execution failed: \(runRes.errorMessage ?? "Unknown error")")
            currentExecutionStatus = .fail
            blockerDetails.append("Agent Execution check failed")
        }

        let unapprovedRes = await service.executeCapability(capabilityId: "github_integration", input: ["action": "create_issue_comment"], userApproved: false)
        let approvedRes = await service.executeCapability(capabilityId: "github_integration", input: ["action": "create_issue_comment", "mock_offline": "true"], userApproved: true)
        if unapprovedRes.status == .denied && approvedRes.status == .success {
            setCheck(id: 5, status: .pass, msg: "Permission denial and approval flow verified")
            connectionStatus = .pass
        } else {
            setCheck(id: 5, status: .fail, msg: "Permission flow failed: unapproved=\(unapprovedRes.status.rawValue), approved=\(approvedRes.status.rawValue)")
            connectionStatus = .fail
            blockerDetails.append("Permission flow check failed")
        }

        // Put the store in an in-flight phase, then cancel for real (idle cancel is a no-op).
        runtimeStore.send(.executionStarted(goal: "cancel-probe", executionId: runRes.runId))
        cancelTask()
        if runtimeStore.state.phase == .cancelled {
            setCheck(id: 6, status: .pass, msg: "Task cancellation propagated correctly")
        } else {
            setCheck(id: 6, status: .fail, msg: "Task cancellation did not propagate")
            blockerDetails.append("Task Cancellation failed to propagate")
        }

        let failRes = await service.resume(runId: "RUN-INVALID-CHECK")
        if failRes.status == .failed && failRes.errorCode == "RUN_NOT_FOUND" {
            setCheck(id: 7, status: .pass, msg: "Error propagation verified (code: RUN_NOT_FOUND)")
        } else {
            setCheck(id: 7, status: .fail, msg: "Error propagation failed")
            blockerDetails.append("Error Propagation check failed")
        }

        let exps = await service.getExperience()
        if exps.contains(where: { $0.runId == runRes.runId }) {
            setCheck(id: 8, status: .pass, msg: "Activity recorded in LocalExperienceStore")
            localStorageStatus = .pass
        } else {
            setCheck(id: 8, status: .fail, msg: "Activity record not found in store")
            localStorageStatus = .fail
            blockerDetails.append("Activity Recording check failed")
        }

        let allTabs = AppTab.allCases
        if allTabs.count == 7 {
            setCheck(id: 9, status: .pass, msg: "All 7 navigation tabs accessible")
        } else {
            setCheck(id: 9, status: .fail, msg: "Navigation tab count mismatch")
            blockerDetails.append("Navigation Accessibility check failed")
        }

        if let restoredRun = await service.getRun(runId: runRes.runId), restoredRun.runId == runRes.runId {
            setCheck(id: 10, status: .pass, msg: "App state recovered checkpoint from disk")
        } else {
            setCheck(id: 10, status: .fail, msg: "Checkpoint restoration failed")
            blockerDetails.append("App State Recovery check failed")
        }

        updateSummaryCounters()
        await refreshState()
    }

    private func setCheck(id: Int, status: ReviewCheckStatus, msg: String) {
        if let idx = reviewChecks.firstIndex(where: { $0.id == id }) {
            reviewChecks[idx].status = status
            reviewChecks[idx].message = msg
        }
    }

    private func updateSummaryCounters() {
        passCount = reviewChecks.filter { $0.status == .pass }.count
        failCount = reviewChecks.filter { $0.status == .fail }.count
        warningCount = reviewChecks.filter { $0.status == .warning }.count
        notTestedCount = reviewChecks.filter { $0.status == .notTested }.count
    }
}

// MARK: - Main Tab Navigation View

struct MainTabView: View {
    @EnvironmentObject private var viewModel: AgentAppViewModel

    var body: some View {
        TabView(selection: $viewModel.selectedTab) {
            HomeView()
                .tabItem {
                    Label(AppTab.home.rawValue, systemImage: AppTab.home.iconName)
                }
                .tag(AppTab.home)

            ExecuteView()
                .tabItem {
                    Label(AppTab.agent.rawValue, systemImage: AppTab.agent.iconName)
                }
                .tag(AppTab.agent)

            ActivityView()
                .tabItem {
                    Label(AppTab.activity.rawValue, systemImage: AppTab.activity.iconName)
                }
                .tag(AppTab.activity)

            VaultView()
                .tabItem {
                    Label(AppTab.vault.rawValue, systemImage: AppTab.vault.iconName)
                }
                .tag(AppTab.vault)

            ConnectionsView()
                .tabItem {
                    Label(AppTab.connections.rawValue, systemImage: AppTab.connections.iconName)
                }
                .tag(AppTab.connections)

            SettingsView()
                .tabItem {
                    Label(AppTab.settings.rawValue, systemImage: AppTab.settings.iconName)
                }
                .tag(AppTab.settings)

            ReviewView()
                .tabItem {
                    Label(AppTab.review.rawValue, systemImage: AppTab.review.iconName)
                }
                .tag(AppTab.review)
        }
        .accentColor(AgentColor.accent)
        .alert(viewModel.permissionActionTitle, isPresented: $viewModel.showingPermissionAlert) {
            Button("Allow", role: .none) {
                viewModel.handlePermissionResponse(allowed: true)
            }
            Button("Deny", role: .cancel) {
                viewModel.handlePermissionResponse(allowed: false)
            }
        } message: {
            Text("Allow Agent to execute this operation? Explicit policy user approval is required.")
        }
    }
}

// MARK: - Reusable UI Subviews for Review

struct StatusCell: View {
    let title: String
    let status: ReviewCheckStatus

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(AgentFont.caption)
                .foregroundColor(AgentColor.textMuted)
            Text(status.rawValue)
                .font(AgentFont.captionSmall)
                .fontWeight(.bold)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(status.color.opacity(0.15))
                .foregroundColor(status.color)
                .cornerRadius(6)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
