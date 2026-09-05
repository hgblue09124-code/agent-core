// ios/AgentCoreIOS/Views/SettingsView.swift
// Settings Screen — Personal Agent iOS

import SwiftUI

public struct SettingsView: View {
    @ObservedObject public var viewModel: AgentAppViewModel

    public init(viewModel: AgentAppViewModel) {
        self.viewModel = viewModel
    }

    public var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // Header Bar
                HStack {
                    Text("Settings")
                        .font(.system(size: 20, weight: .bold))
                        .foregroundColor(AgentTheme.text1)

                    Spacer()
                }
                .padding(.top, 8)

                // Settings Group Card
                VStack(spacing: 12) {
                    AgentToggle(title: "Background execution", isOn: $viewModel.backgroundExecution)

                    Divider().background(AgentTheme.hair)

                    AgentToggle(title: "Privacy mode", isOn: $viewModel.privacyMode)

                    Divider().background(AgentTheme.hair)

                    AgentListRow(
                        title: "Storage Usage",
                        icon: "internaldrive",
                        rightText: "1.4 GB",
                        showChevron: true
                    )

                    Divider().background(AgentTheme.hair)

                    AgentListRow(
                        title: "Appearance",
                        icon: "paintpalette",
                        rightText: "Dark",
                        showChevron: true
                    )

                    Divider().background(AgentTheme.hair)

                    AgentListRow(
                        title: "About Personal Agent",
                        subtitle: "v0.1.0-beta · Core Kernel Authority",
                        icon: "info.circle",
                        showChevron: true
                    )
                }
                .agentCard(padding: 14)
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .background(AgentTheme.bg1.ignoresSafeArea())
    }
}
