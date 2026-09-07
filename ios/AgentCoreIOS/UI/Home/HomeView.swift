// ios/AgentCoreIOS/UI/Home/HomeView.swift
// Personal Agent Home — native User Workspace (conversation, live state, progress, result)

import SwiftUI

struct HomeView: View {
    @EnvironmentObject private var viewModel: AgentAppViewModel
    @State private var inputText: String = ""

    init() {}

    private var runtimeState: AgentRuntimeState {
        viewModel.runtimeStore.state
    }

    private var snapshot: WorkspaceSnapshot {
        WorkspacePresentation.map(state: runtimeState, lastResult: viewModel.lastRunResult)
    }

    private var currentStatus: AgentStatus {
        runtimeState.status
    }

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: AgentSpacing.lg) {
                        headerRow
                        identityCard
                        conversationSection
                        workSection
                        if snapshot.resultPresent {
                            resultSection
                        }
                        if snapshot.canCancel || snapshot.canRetry {
                            actionsRow
                        }
                        quickActionsSection
                        recentActivitySection
                        Color.clear.frame(height: 1).id("workspace-bottom")
                    }
                    .padding(AgentSpacing.lg)
                }
                .onChange(of: viewModel.conversation.count) { _, _ in
                    withAnimation(.easeOut(duration: 0.2)) {
                        proxy.scrollTo("workspace-bottom", anchor: .bottom)
                    }
                }
                .onChange(of: snapshot.presence) { _, _ in
                    proxy.scrollTo("workspace-bottom", anchor: .bottom)
                }
            }

            composerBar
        }
        .background(AgentColor.background1.ignoresSafeArea())
    }

    private var headerRow: some View {
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
    }

    private var identityCard: some View {
        VStack(spacing: AgentSpacing.md) {
            HStack {
                StatusPillView(status: currentStatus)
                Spacer()
                PrivacyChipView(label: "On-device", isLocal: true)
            }

            VStack(spacing: AgentSpacing.md) {
                AgentOrbView(status: currentStatus, size: .default118)

                Text(snapshot.activityHeadline)
                    .font(AgentFont.secondary)
                    .foregroundColor(AgentColor.textMuted)
                    .multilineTextAlignment(.center)
            }
            .padding(.vertical, AgentSpacing.sm)
        }
        .padding(AgentSpacing.lg)
        .background(AgentColor.background2)
        .overlay(
            RoundedRectangle(cornerRadius: AgentRadius.card)
                .stroke(AgentColor.hairline, lineWidth: AgentBorder.hairline)
        )
        .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))
    }

    private var conversationSection: some View {
        VStack(alignment: .leading, spacing: AgentSpacing.sm) {
            Text("Conversation")
                .font(AgentFont.caption)
                .foregroundColor(AgentColor.textMuted)

            VStack(alignment: .leading, spacing: AgentSpacing.sm) {
                if viewModel.conversation.isEmpty && !snapshot.isWorking {
                    conversationBubble(
                        role: .agent,
                        kicker: "Agent",
                        text: "Ask your agent to do something…"
                    )
                } else {
                    ForEach(viewModel.conversation) { message in
                        conversationBubble(role: message.role, kicker: message.kicker, text: message.text)
                    }
                    if snapshot.isWorking {
                        conversationBubble(role: .agent, kicker: "Agent", text: snapshot.activityHeadline)
                    }
                }
            }
        }
    }

    private func conversationBubble(role: WorkspaceMessage.Role, kicker: String?, text: String) -> some View {
        VStack(alignment: role == .user ? .trailing : .leading, spacing: 4) {
            if let kicker, role == .agent {
                Text(kicker)
                    .font(AgentFont.captionSmall)
                    .foregroundColor(AgentColor.textMuted)
            }
            Text(text)
                .font(AgentFont.body)
                .foregroundColor(AgentColor.textPrimary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(role == .user ? AgentColor.background3 : AgentColor.background2)
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(AgentColor.hairline, lineWidth: AgentBorder.hairline)
        )
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .frame(maxWidth: .infinity, alignment: role == .user ? .trailing : .leading)
    }

    private var workSection: some View {
        VStack(alignment: .leading, spacing: AgentSpacing.sm) {
            Text("What my agent is doing")
                .font(AgentFont.caption)
                .foregroundColor(AgentColor.textMuted)

            if snapshot.isWorking {
                CurrentTaskCard(
                    goal: snapshot.goal.isEmpty ? "Processing…" : snapshot.goal,
                    subtext: snapshot.activityHeadline,
                    progress: snapshot.progress,
                    status: currentStatus
                )
                if snapshot.showsProgress {
                    VStack(alignment: .leading, spacing: AgentSpacing.sm) {
                        ProgressBarView(
                            progress: snapshot.progress,
                            fillColor: currentStatus == .running ? AgentColor.warning : AgentColor.accent
                        )
                        ForEach(snapshot.steps) { step in
                            StepProgressRow(title: step.title, status: step.status)
                        }
                    }
                    .padding(AgentSpacing.md)
                    .background(AgentColor.background2)
                    .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))
                }
            } else if snapshot.resultPresent {
                CurrentTaskCard(
                    goal: snapshot.goal,
                    subtext: snapshot.resultHeadline,
                    progress: snapshot.resultOK ? 1.0 : snapshot.progress,
                    status: snapshot.resultOK ? .ready : .running
                )
            } else {
                VStack(alignment: .leading, spacing: 4) {
                    Text("No active background objective")
                        .font(AgentFont.body)
                        .foregroundColor(AgentColor.textPrimary)
                    Text("Type an objective below or run a task to give your agent work.")
                        .font(AgentFont.caption)
                        .foregroundColor(AgentColor.textMuted)
                }
                .padding(AgentSpacing.md)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(AgentColor.background2)
                .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))
            }
        }
    }

    private var resultSection: some View {
        VStack(alignment: .leading, spacing: AgentSpacing.sm) {
            Text(snapshot.resultHeadline)
                .font(AgentFont.caption)
                .foregroundColor(AgentColor.textMuted)
            Text(snapshot.resultBody)
                .font(AgentFont.headline)
                .foregroundColor(snapshot.resultOK ? AgentColor.success : AgentColor.danger)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(AgentSpacing.lg)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(snapshot.resultOK ? AgentColor.successDim : AgentColor.dangerDim)
        .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))
    }

    private var actionsRow: some View {
        HStack(spacing: AgentSpacing.md) {
            if snapshot.canCancel {
                Button(action: { viewModel.cancelTask() }) {
                    Text("Cancel")
                        .font(AgentFont.subheadline)
                        .foregroundColor(AgentColor.textPrimary)
                        .frame(maxWidth: .infinity)
                        .frame(height: 44)
                        .background(AgentColor.background3)
                        .clipShape(Capsule())
                }
            }
            if snapshot.canRetry {
                Button(action: {
                    Task { await viewModel.retryWorkspace() }
                }) {
                    Text("Retry")
                        .font(AgentFont.subheadline)
                        .foregroundColor(AgentColor.background1)
                        .frame(maxWidth: .infinity)
                        .frame(height: 44)
                        .background(AgentColor.accent)
                        .clipShape(Capsule())
                }
            }
        }
    }

    private var composerBar: some View {
        InputPillView(
            text: $inputText,
            placeholder: "Ask your agent to do something…",
            onSubmit: {
                submitTaskFromHome()
            }
        )
        .padding(.horizontal, AgentSpacing.lg)
        .padding(.top, AgentSpacing.sm)
        .padding(.bottom, AgentSpacing.md)
        .background(
            AgentColor.background1
                .ignoresSafeArea(edges: .bottom)
        )
    }

    private var quickActionsSection: some View {
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
    }

    private var recentActivitySection: some View {
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

    private func submitTaskFromHome() {
        let taskGoal = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !taskGoal.isEmpty else { return }
        inputText = ""
        Task {
            await viewModel.submitWorkspaceMessage(taskGoal)
        }
    }
}
