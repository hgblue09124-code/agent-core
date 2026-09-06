// ios/AgentCoreIOS/UI/Settings/SettingsView.swift
// Personal Agent Settings — preferences, LLM backends, model catalog.

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var viewModel: AgentAppViewModel
    @AppStorage("backgroundExecution") private var backgroundExecution: Bool = true
    @AppStorage("privacyMode") private var privacyMode: Bool = true
    @ObservedObject private var downloads = ModelDownloadManager.shared
    @State private var settings: LLMSettings = LLMSettingsStore.shared.load()
    @State private var apiKey: String = ""
    @State private var downloadError: String = ""
    @State private var testResult: String = ""

    init() {}

    private var appVersionLabel: String {
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0.2.0"
        let build = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "1"
        return "\(version) (Build \(build))"
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: AgentSpacing.lg) {
                Text("Settings")
                    .font(AgentFont.h1)
                    .foregroundColor(AgentColor.textPrimary)

                VStack(alignment: .leading, spacing: AgentSpacing.xs) {
                    Text("User Preferences")
                        .font(AgentFont.caption)
                        .foregroundColor(AgentColor.textMuted)

                    SettingsCard {
                        HStack {
                            Text("Background execution")
                                .font(AgentFont.body)
                                .foregroundColor(AgentColor.textPrimary)
                            Spacer()
                            Toggle("", isOn: $backgroundExecution)
                                .labelsHidden()
                                .tint(AgentColor.accent)
                        }
                        .padding(.vertical, 10)

                        Divider().background(AgentColor.hairline)

                        HStack {
                            Text("Privacy mode")
                                .font(AgentFont.body)
                                .foregroundColor(AgentColor.textPrimary)
                            Spacer()
                            Toggle("", isOn: $privacyMode)
                                .labelsHidden()
                                .tint(AgentColor.accent)
                                .onChange(of: privacyMode) { value in
                                    settings.privacyMode = value
                                    persist()
                                }
                        }
                        .padding(.vertical, 10)
                    }
                }

                llmSection

                VStack(alignment: .leading, spacing: AgentSpacing.xs) {
                    Text("Storage & System")
                        .font(AgentFont.caption)
                        .foregroundColor(AgentColor.textMuted)

                    SettingsCard {
                        SettingsRowView(title: "Storage", detail: "Local On-Device", showChevron: false)

                        Divider().background(AgentColor.hairline)

                        SettingsRowView(title: "Appearance", detail: "Dark (Read-Only)", showChevron: false)

                        Divider().background(AgentColor.hairline)

                        SettingsRowView(
                            title: "Active Provider",
                            detail: viewModel.health?.providerName ?? RoutingLanguageModelProvider.shared.displayStatus().name,
                            showChevron: false
                        )
                    }
                }

                VStack(alignment: .leading, spacing: AgentSpacing.xs) {
                    Text("Data Update v0.1")
                        .font(AgentFont.caption)
                        .foregroundColor(AgentColor.textMuted)

                    SettingsCard {
                        SettingsRowView(title: "Installed Data Version", detail: viewModel.updateReport.installedDataVersion, showChevron: false)

                        Divider().background(AgentColor.hairline)

                        SettingsRowView(title: "Update Status", detail: viewModel.updateReport.status.rawValue, showChevron: false)

                        if let err = viewModel.updateReport.lastError {
                            Divider().background(AgentColor.hairline)
                            HStack {
                                Text("Last Error")
                                    .font(AgentFont.body)
                                    .foregroundColor(AgentColor.danger)
                                Spacer()
                                Text(err)
                                    .font(AgentFont.captionSmall)
                                    .foregroundColor(AgentColor.danger)
                            }
                            .padding(.vertical, 10)
                        }
                    }
                }

                VStack(alignment: .leading, spacing: AgentSpacing.xs) {
                    Text("About")
                        .font(AgentFont.caption)
                        .foregroundColor(AgentColor.textMuted)

                    SettingsCard {
                        SettingsRowView(title: "Version", detail: appVersionLabel, showChevron: false)

                        Divider().background(AgentColor.hairline)

                        SettingsRowView(title: "Architecture", detail: "Agent Core Local Kernel", showChevron: false)
                    }
                }
            }
            .padding(AgentSpacing.lg)
        }
        .background(AgentColor.background1.ignoresSafeArea())
        .onAppear {
            settings = LLMSettingsStore.shared.load()
            privacyMode = settings.privacyMode
            apiKey = LLMSettingsStore.shared.apiKey(for: settings.backend)
            downloads.refreshInstalled()
        }
    }

    private var llmSection: some View {
        VStack(alignment: .leading, spacing: AgentSpacing.xs) {
            Text("Language Model")
                .font(AgentFont.caption)
                .foregroundColor(AgentColor.textMuted)

            SettingsCard {
                Picker("Backend", selection: $settings.backend) {
                    ForEach(LLMBackend.allCases.filter { $0 != .mock }) { backend in
                        Text(backend.displayName).tag(backend)
                    }
                }
                .pickerStyle(.menu)
                .tint(AgentColor.accent)
                .onChange(of: settings.backend) { backend in
                    if settings.remoteModel.isEmpty || ModelCatalog.spec(id: settings.remoteModel) != nil {
                        settings.remoteModel = backend.defaultModel
                    }
                    if settings.baseURL.isEmpty {
                        settings.baseURL = backend.defaultBaseURL
                    }
                    apiKey = LLMSettingsStore.shared.apiKey(for: backend)
                    persist()
                }
                .padding(.vertical, 8)

                if settings.backend.isRemoteCloud || settings.backend == .ollama || settings.backend == .custom {
                    Divider().background(AgentColor.hairline)
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Model")
                            .font(AgentFont.captionSmall)
                            .foregroundColor(AgentColor.textMuted)
                        TextField("model id", text: $settings.remoteModel)
                            .textInputAutocapitalization(.never)
                            .disableAutocorrection(true)
                            .font(AgentFont.mono)
                            .foregroundColor(AgentColor.textPrimary)
                            .onChange(of: settings.remoteModel) { _ in persist() }
                        Text("Base URL")
                            .font(AgentFont.captionSmall)
                            .foregroundColor(AgentColor.textMuted)
                        TextField("https://…", text: $settings.baseURL)
                            .textInputAutocapitalization(.never)
                            .disableAutocorrection(true)
                            .font(AgentFont.mono)
                            .foregroundColor(AgentColor.textPrimary)
                            .onChange(of: settings.baseURL) { _ in persist() }
                        if settings.backend.isRemoteCloud {
                            Text("API key")
                                .font(AgentFont.captionSmall)
                                .foregroundColor(AgentColor.textMuted)
                            SecureField("stored in Keychain", text: $apiKey)
                                .textInputAutocapitalization(.never)
                                .disableAutocorrection(true)
                                .font(AgentFont.mono)
                                .onChange(of: apiKey) { value in
                                    LLMSettingsStore.shared.setAPIKey(value, for: settings.backend)
                                }
                        }
                    }
                    .padding(.vertical, 8)
                }
            }

            if settings.backend == .onDevice {
                Text("Tiny → medium GGUF (weights only)")
                    .font(AgentFont.caption)
                    .foregroundColor(AgentColor.textMuted)
                    .padding(.top, 8)

                SettingsCard {
                    ForEach(Array(ModelCatalog.all.enumerated()), id: \.element.id) { index, spec in
                        modelRow(spec)
                        if index < ModelCatalog.all.count - 1 {
                            Divider().background(AgentColor.hairline)
                        }
                    }
                }

                if !downloadError.isEmpty {
                    Text(downloadError)
                        .font(AgentFont.captionSmall)
                        .foregroundColor(AgentColor.danger)
                }
            }

            if !testResult.isEmpty {
                Text(testResult)
                    .font(AgentFont.captionSmall)
                    .foregroundColor(AgentColor.textSecondary)
            }

            Button {
                Task { await testGeneration() }
            } label: {
                Text("Test generation")
                    .font(AgentFont.body)
                    .foregroundColor(AgentColor.accent)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
            }
        }
    }

    private func modelRow(_ spec: LLMModelSpec) -> some View {
        let installed = downloads.installedIds.contains(spec.id)
        let fraction = downloads.progress[spec.id] ?? 0
        let selected = settings.onDeviceModelId == spec.id
        return VStack(alignment: .leading, spacing: 6) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(spec.displayName)
                        .font(AgentFont.body)
                        .foregroundColor(AgentColor.textPrimary)
                    Text("\(spec.sizeClass.rawValue) · \(spec.quantization) · \(spec.sizeLabel)")
                        .font(AgentFont.captionSmall)
                        .foregroundColor(AgentColor.textMuted)
                }
                Spacer()
                if selected {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(AgentColor.success)
                }
            }
            HStack {
                if installed {
                    Button("Use") {
                        settings.onDeviceModelId = spec.id
                        persist()
                    }
                    .font(AgentFont.caption)
                    Button("Delete") {
                        try? downloads.delete(spec)
                    }
                    .font(AgentFont.caption)
                    .foregroundColor(AgentColor.danger)
                } else if fraction > 0 && fraction < 1 {
                    ProgressView(value: fraction)
                        .tint(AgentColor.accent)
                    Button("Cancel") { downloads.cancel(spec) }
                        .font(AgentFont.caption)
                } else {
                    Button("Download") {
                        Task { await download(spec) }
                    }
                    .font(AgentFont.caption)
                    .foregroundColor(AgentColor.accent)
                }
            }
        }
        .padding(.vertical, 10)
    }

    private func persist() {
        settings.privacyMode = privacyMode
        LLMSettingsStore.shared.save(settings)
        Task { await viewModel.refreshState() }
    }

    private func download(_ spec: LLMModelSpec) async {
        downloadError = ""
        do {
            _ = try await downloads.download(spec)
            settings.onDeviceModelId = spec.id
            persist()
        } catch {
            downloadError = error.localizedDescription
        }
    }

    private func testGeneration() async {
        persist()
        testResult = "Testing…"
        do {
            let provider = RoutingLanguageModelProvider.shared
            try await provider.load()
            let response = try await provider.generate(
                LanguageModelRequest(messages: [
                    LanguageModelMessage(role: .user, content: "Reply with the single word pong.")
                ])
            )
            testResult = String(response.text.prefix(240))
        } catch {
            testResult = error.localizedDescription
        }
        await viewModel.refreshState()
    }
}
