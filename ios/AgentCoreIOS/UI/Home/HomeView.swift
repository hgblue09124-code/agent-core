// ios/AgentCoreIOS/UI/Home/HomeView.swift
// Personal Agent Home View — Reconstructed around Personal Agent Concept

import SwiftUI

struct HomeView: View {
    @EnvironmentObject private var viewModel: AgentAppViewModel
    @State private var inputText: String = ""

    init() {}

    private var runtimeState: AgentRuntimeState {
        viewModel.runtimeStore.state
    }

    private var currentStatus: AgentStatus {
        runtimeState.status
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: AgentSpacing.lg) {
                // 1. Header Row
                HStack(alignment: .center) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Good evening")
                            .font(AgentFont.caption)
                            .foregroundColor(AgentColor.textMuted)

                        Text("Your agent")
                            .font(AgentFont.h1)
                            .foregroundColor(AgentColor.textPrimary)
                    }

                    Spacer()

                    // Bell Notification Tile
                    ZStack {
                        RoundedRectangle(cornerRadius: AgentRadius.tile)
                            .fill(AgentColor.background3)
                            .frame(width: 38, height: 38)
                            .overlay(
                                RoundedRectangle(cornerRadius: AgentRadius.tile)
                                    .stroke(AgentColor.hairline, lineWidth: AgentBorder.hairline)
                            )

                        Image(systemName: "bell.fill")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundColor(AgentColor.textPrimary)
                    }
                }
                .padding(.top, AgentSpacing.xs)

                // 2. Agent Status Card (Orb, Status Pill, Docked Composer)
                VStack(spacing: AgentSpacing.md) {
                    // Top status bar
                    HStack {
                        StatusPillView(status: currentStatus)
                        Spacer()
                        PrivacyChipView(label: "On-device", isLocal: true)
                    }

                    // Ambient Orb Block
                    VStack(spacing: AgentSpacing.md) {
                        AgentOrbView(status: currentStatus, size: .default118)

                        Text(orbStatusSubtext)
                            .font(AgentFont.secondary)
                            .foregroundColor(AgentColor.textMuted)
                    }
                    .padding(.vertical, AgentSpacing.sm)

                    // Docked Input Composer Pill
                    InputPillView(
                        text: $inputText,
                        placeholder: "Ask your agent to do something…",
                        onSubmit: {
                            submitTaskFromHome()
                        }
                    )
                }
                .padding(AgentSpacing.lg)
                .background(AgentColor.background2)
                .overlay(
                    RoundedRectangle(cornerRadius: AgentRadius.card)
                        .stroke(AgentColor.hairline, lineWidth: AgentBorder.hairline)
                )
                .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))

                // 3. Quick Actions (2-Column Grid)
                VStack(alignment: .leading, spacing: AgentSpacing.sm) {
                    Text("Quick actions")
                        .font(AgentFont.caption)
                        .foregroundColor(AgentColor.textMuted)

                    HStack(spacing: AgentSpacing.md) {
                        QuickActionCard(
                            title: "Run a task",
                            iconName: "bolt.fill",
                            isAccent: true,
                            action: {
                                viewModel.selectedTab = .agent
                            }
                        )

                        QuickActionCard(
                            title: "Search memory",
                            iconName: "lock.shield.fill",
                            isAccent: false,
                            action: {
                                viewModel.selectedTab = .vault
                            }
                        )
                    }
                }

                // 4. Current / Active Objective Card ("What is my Agent doing for me?")
                VStack(alignment: .leading, spacing: AgentSpacing.sm) {
                    Text("What my agent is doing")
                        .font(AgentFont.caption)
                        .foregroundColor(AgentColor.textMuted)

                    if runtimeState.phase == .executing || runtimeState.phase == .thinking || runtimeState.phase == .planning {
                        CurrentTaskCard(
                            goal: runtimeState.currentGoal,
                            subtext: "Agent is processing objective on local runtime",
                            progress: runtimeState.progress,
                            status: .running
                        )
                    } else if let last = viewModel.lastRunResult {
                        CurrentTaskCard(
                            goal: last.goal,
                            subtext: last.status == .success ? "Objective completed cleanly" : (last.errorMessage ?? "Objective failed"),
                            progress: last.status == .success ? 1.0 : 0.0,
                            status: last.status == .success ? .ready : .running
                        )
                    } else {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("No active background objective")
                                .font(AgentFont.body)
                                .foregroundColor(AgentColor.textPrimary)
                            Text("Type an objective above or run a task to give your agent work.")
                                .font(AgentFont.caption)
                                .foregroundColor(AgentColor.textMuted)
                        }
                        .padding(AgentSpacing.md)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(AgentColor.background2)
                        .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))
                    }
                }

                // 5. Recent Activity Card List
                VStack(alignment: .leading, spacing: AgentSpacing.sm) {
                    HStack {
                        Text("Recent activity")
                            .font(AgentFont.caption)
                            .foregroundColor(AgentColor.textMuted)

                        Spacer()

                        Button(action: {
                            viewModel.selectedTab = .activity
                        }) {
                            Text("See all")
                                .font(AgentFont.secondary)
                                .foregroundColor(AgentColor.accent)
                        }
                    }

                    VStack(spacing: 0) {
                        if viewModel.activities.isEmpty {
                            Text("No recent activity recorded.")
                                .font(AgentFont.secondary)
                                .foregroundColor(AgentColor.textMuted)
                                .padding(AgentSpacing.lg)
                        } else {
                            ForEach(Array(viewModel.activities.prefix(2))) { record in
                                ActivityRowView(record: record)

                                if record.id != viewModel.activities.prefix(2).last?.id {
                                    Divider()
                                        .background(AgentColor.hairline)
                                }
                            }
                        }
                    }
                    .padding(.horizontal, AgentSpacing.md)
                    .padding(.vertical, AgentSpacing.xs)
                    .background(AgentColor.background2)
                    .overlay(
                        RoundedRectangle(cornerRadius: AgentRadius.card)
                            .stroke(AgentColor.hairline, lineWidth: AgentBorder.hairline)
                    )
                    .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))
                }
            }
            .padding(AgentSpacing.lg)
        }
        .background(AgentColor.background1.ignoresSafeArea())
    }

    private var orbStatusSubtext: String {
        switch runtimeState.phase {
        case .idle:
            return "Idle · ready for tasks"
        case .thinking, .planning, .executing:
            return "Executing · processing goal"
        case .completed:
            return "Completed · task finished"
        case .failed:
            return "Failed · inspect error"
        case .cancelled:
            return "Cancelled · user stopped"
        }
    }

    private func submitTaskFromHome() {
        let taskGoal = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !taskGoal.isEmpty else { return }
        viewModel.currentGoal = taskGoal
        inputText = ""
        viewModel.selectedTab = .agent
        Task {
            await viewModel.runTask(requestPermissionPrompt: false)
        }
    }
}
