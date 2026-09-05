// ios/AgentCoreIOS/Views/HomeView.swift
// Home / Dashboard Screen — Personal Agent iOS

import SwiftUI

public struct HomeView: View {
    @ObservedObject public var viewModel: AgentAppViewModel

    public init(viewModel: AgentAppViewModel) {
        self.viewModel = viewModel
    }

    public var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Header Bar with Local Badge
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Personal Agent")
                            .font(.system(size: 20, weight: .bold))
                            .foregroundColor(AgentTheme.text1)
                        Text("On-device authority & continuity")
                            .font(.system(size: 12))
                            .foregroundColor(AgentTheme.text2)
                    }

                    Spacer()

                    LocalIndicator(label: "Private · Local", isShield: true)
                }
                .padding(.top, 8)

                // Central Orb Gravity Card
                VStack(spacing: 16) {
                    AgentOrbView(state: viewModel.state, size: 92)
                        .padding(.top, 12)

                    AgentStatusPill(state: viewModel.state, fontSize: 13)

                    Text(viewModel.state.description)
                        .font(.system(size: 12))
                        .foregroundColor(AgentTheme.text2)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 16)

                    // Docked Pill Composer Input
                    PillComposerInput(
                        text: $viewModel.composerText,
                        placeholder: "Ask your personal agent...",
                        state: viewModel.state,
                        onSubmit: {
                            viewModel.submitComposerTask()
                        }
                    )
                    .padding(.top, 4)
                }
                .agentCard(padding: 16)

                // Quick Tasks / Recent Runs Section
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("Quick Actions")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(AgentTheme.text1)

                        Spacer()

                        Button("View Activity") {
                            viewModel.selectedTab = 2 // Switch to Activity tab
                        }
                        .font(.system(size: 12, weight: .medium))
                        .foregroundColor(AgentTheme.accent)
                    }

                    VStack(spacing: 8) {
                        Button(action: {
                            viewModel.currentGoal = "Draft replies to unread emails from this week and flag anything urgent."
                            viewModel.selectedTab = 1
                            viewModel.runTask(goal: viewModel.currentGoal)
                        }) {
                            AgentListRow(
                                title: "Draft Email Replies",
                                subtitle: "Inbox analysis & draft generation",
                                icon: "envelope.fill",
                                iconColor: AgentTheme.accent,
                                tileBackground: AgentTheme.accentDim,
                                showChevron: true
                            )
                        }

                        Button(action: {
                            viewModel.currentGoal = "Inspect workspace architecture & verify continuous security bounds."
                            viewModel.selectedTab = 1
                            viewModel.runTask(goal: viewModel.currentGoal)
                        }) {
                            AgentListRow(
                                title: "Inspect Workspace Architecture",
                                subtitle: "Local system & contract validation",
                                icon: "bolt.fill",
                                iconColor: AgentTheme.cyan,
                                tileBackground: AgentTheme.cyan.opacity(0.14),
                                showChevron: true
                            )
                        }

                        Button(action: {
                            viewModel.currentGoal = "Backup personal vault notes and synchronize local configuration."
                            viewModel.selectedTab = 1
                            viewModel.runTask(goal: viewModel.currentGoal)
                        }) {
                            AgentListRow(
                                title: "Backup Personal Notes",
                                subtitle: "Local vault memory backup",
                                icon: "lock.shield.fill",
                                iconColor: AgentTheme.success,
                                tileBackground: AgentTheme.successDim,
                                showChevron: true
                            )
                        }
                    }
                }
                .agentCard(padding: 14)
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .background(AgentTheme.bg1.ignoresSafeArea())
    }
}
