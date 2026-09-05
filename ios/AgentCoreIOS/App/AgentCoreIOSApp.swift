// ios/AgentCoreIOS/App/AgentCoreIOSApp.swift
// SwiftUI Diagnostic Interface — Personal Agent Local

import SwiftUI

@main
struct AgentCoreIOSApp: App {
    var body: some Scene {
        WindowGroup {
            DiagnosticMainView()
        }
    }
}

struct DiagnosticMainView: View {
    @StateObject private var viewModel = DiagnosticViewModel()

    var body: some View {
        NavigationView {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    // Title & Badge Header
                    HStack {
                        VStack(alignment: .leading) {
                            Text("Personal Agent Local")
                                .font(.title.bold())
                            Text("Native Local iOS Diagnostic Interface")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                        Spacer()
                        Text("LOCAL ONLY")
                            .font(.caption.bold())
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(Color.green.opacity(0.2))
                            .foregroundColor(.green)
                            .cornerRadius(8)
                    }
                    .padding()
                    .background(Color(UIColor.secondarySystemBackground))
                    .cornerRadius(12)

                    // Agent Action Buttons
                    HStack(spacing: 8) {
                        Button("[Run]") { Task { await viewModel.runTask() } }
                            .buttonStyle(.borderedProminent)

                        Button("[Remember]") { Task { await viewModel.rememberFact() } }
                            .buttonStyle(.bordered)

                        Button("[Retrieve]") { Task { await viewModel.retrieveFacts() } }
                            .buttonStyle(.bordered)

                        Button("[Resume]") { Task { await viewModel.resumeRun() } }
                            .buttonStyle(.bordered)

                        Button("[Health]") { Task { await viewModel.checkHealth() } }
                            .buttonStyle(.bordered)
                    }

                    // Update Action Buttons
                    HStack(spacing: 8) {
                        Button("[Check Updates]") { Task { await viewModel.checkForDataUpdates() } }
                            .buttonStyle(.bordered)

                        Button("[Sync Now]") { Task { await viewModel.syncDataNow() } }
                            .buttonStyle(.borderedProminent)
                    }

                    Divider()

                    // Display Sections
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Agent Status")
                            .font(.headline)
                        Group {
                            DetailRow(label: "Goal", value: viewModel.currentGoal)
                            DetailRow(label: "Status", value: viewModel.status)
                            DetailRow(label: "Run ID", value: viewModel.runId)
                            DetailRow(label: "Output", value: viewModel.output)
                            DetailRow(label: "Provider", value: viewModel.provider)
                            DetailRow(label: "Storage Status", value: viewModel.storageStatus)
                        }

                        Divider()

                        Text("GitHub Data Update Status (Data/Config Only)")
                            .font(.headline)
                        Group {
                            DetailRow(label: "Installed Data Version", value: viewModel.updateReport.installedDataVersion)
                            DetailRow(label: "Latest Known Version", value: viewModel.updateReport.latestKnownVersion ?? "Unknown")
                            DetailRow(label: "Update Status", value: viewModel.updateReport.status.rawValue)
                            DetailRow(label: "Last Successful Sync", value: viewModel.updateReport.lastSuccessfulSync ?? "Never")
                            DetailRow(label: "Last Error", value: viewModel.updateReport.lastError ?? "None")
                        }

                        Divider()

                        Text("Memories (\(viewModel.memories.count))")
                            .font(.headline)
                        ForEach(viewModel.memories) { mem in
                            Text("• [\(mem.key)]: \(mem.value)")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }

                        Divider()

                        Text("Experiences (\(viewModel.experiences.count))")
                            .font(.headline)
                        ForEach(viewModel.experiences) { exp in
                            Text("• [\(exp.runId)]: \(exp.goal) (\(exp.outcome))")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .padding()
                    .background(Color(UIColor.secondarySystemBackground))
                    .cornerRadius(12)
                }
                .padding()
            }
            .navigationTitle("Agent-Core Beta")
        }
    }
}

struct DetailRow: View {
    let label: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.caption.bold())
                .foregroundColor(.secondary)
            Text(value.isEmpty ? "-" : value)
                .font(.body)
        }
    }
}

@MainActor
final class DiagnosticViewModel: ObservableObject {
    @Published var currentGoal: String = "Inspect workspace architecture"
    @Published var status: String = "IDLE"
    @Published var runId: String = "-"
    @Published var output: String = "Ready"
    @Published var provider: String = "LocalDeterministicPlanner (TEST / DEVELOPMENT PROVIDER)"
    @Published var storageStatus: String = "Application Support/AgentCore/"
    @Published var memories: [MemoryItem] = []
    @Published var experiences: [Experience] = []
    @Published var updateReport: DataUpdateStateReport = DataUpdateStateReport()

    private let service: LocalAgentServiceProtocol
    private let updateManager: GitHubDataUpdateManager

    init(service: LocalAgentServiceProtocol? = nil, updateManager: GitHubDataUpdateManager? = nil) {
        self.service = service ?? LocalAgentService()
        self.updateManager = updateManager ?? GitHubDataUpdateManager()
        self.updateReport = self.updateManager.getStateReport()
    }

    func runTask() async {
        status = "RUNNING..."
        let res = await service.run(goal: currentGoal, userApproved: false)
        status = res.status.rawValue
        runId = res.runId
        output = res.output ?? "-"
        await refresh()
    }

    func rememberFact() async {
        _ = await service.remember(key: "preferred_editor", value: "Neovim")
        output = "Remembered key 'preferred_editor' = 'Neovim'"
        await refresh()
    }

    func retrieveFacts() async {
        memories = await service.retrieve(query: "")
        output = "Retrieved \(memories.count) memory item(s)"
    }

    func resumeRun() async {
        guard runId != "-" else { return }
        let res = await service.resume(runId: runId)
        status = res.status.rawValue
        output = res.output ?? "-"
        await refresh()
    }

    func checkHealth() async {
        let h = await service.health()
        status = h.status
        provider = "\(h.providerName) [\(h.providerStatus)]"
        storageStatus = h.storagePath
        output = "Health check: Vault available=\(h.isVaultAvailable), LocalOnly=\(h.isLocalOnly)"
    }

    func checkForDataUpdates() async {
        updateReport = await updateManager.checkForUpdates()
    }

    func syncDataNow() async {
        // Trigger check then sync if update available
        let check = await updateManager.checkForUpdates()
        if check.status == .updateAvailable {
            let sampleManifest = AppDataManifest(
                schemaVersion: 1,
                dataVersion: "2026.09.05.001",
                minimumClientVersion: "0.1.0",
                files: [
                    ManifestFileEntry(path: "agent-config/default.json", sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", size: 0)
                ]
            )
            updateReport = await updateManager.performUpdate(manifest: sampleManifest, fileDataMap: ["agent-config/default.json": Data()])
        } else {
            updateReport = check
        }
    }

    private func refresh() async {
        memories = await service.retrieve(query: "")
        experiences = await service.getExperience()
        updateReport = updateManager.getStateReport()
    }
}
