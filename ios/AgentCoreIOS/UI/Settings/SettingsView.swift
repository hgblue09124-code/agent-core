// ios/AgentCoreIOS/UI/Settings/SettingsView.swift
// Personal Agent Settings View — User Preferences & App Information

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var viewModel: AgentAppViewModel
    @AppStorage("backgroundExecution") private var backgroundExecution: Bool = true
    @AppStorage("privacyMode") private var privacyMode: Bool = true

    init() {}

    private var appVersionLabel: String {
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0.1.0"
        let build = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "1"
        return "\(version) (Build \(build))"
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: AgentSpacing.lg) {
                // Header
                Text("Settings")
                    .font(AgentFont.h1)
                    .foregroundColor(AgentColor.textPrimary)

                // Group 1: General Preferences
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
                        }
                        .padding(.vertical, 10)
                    }
                }

                // Group 2: Storage & System Info
                VStack(alignment: .leading, spacing: AgentSpacing.xs) {
                    Text("Storage & System")
                        .font(AgentFont.caption)
                        .foregroundColor(AgentColor.textMuted)

                    SettingsCard {
                        SettingsRowView(title: "Storage", detail: "Local On-Device", showChevron: false)

                        Divider().background(AgentColor.hairline)

                        SettingsRowView(title: "Appearance", detail: "Dark (Read-Only)", showChevron: false)

                        Divider().background(AgentColor.hairline)

                        SettingsRowView(title: "Planner Provider", detail: viewModel.health?.providerName ?? "LocalDeterministicPlanner", showChevron: false)
                    }
                }

                // Group 3: Data Update Section (Preserving Data Update v0.1)
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

                // Group 4: About
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
    }
}
