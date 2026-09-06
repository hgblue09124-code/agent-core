// ios/AgentCoreIOS/UI/Execute/ExecuteView.swift
// Personal Agent Execute View — Live Execution Observer

import SwiftUI

public struct ExecuteView: View {
    @EnvironmentObject private var viewModel: AgentAppViewModel

    public init() {}

    private var currentOrbStatus: AgentStatus {
        switch viewModel.executionState {
        case .idle, .completed, .cancelled:
            return .ready
        case .preparing, .running, .waitingForPermission:
            return .thinking
        case .failed:
            return .ready
        }
    }

    private var totalSteps: Int { 4 }

    private var completedStepCount: Int {
        switch viewModel.executionState {
        case .idle: return 0
        case .preparing: return 0
        case .waitingForPermission: return 1
        case .running: return 2
        case .completed: return 4
        case .failed, .cancelled: return 2
        }
    }

    private var currentProgress: Double {
        if viewModel.executionState == .idle { return 0.0 }
        if viewModel.executionState == .completed { return 1.0 }
        return Double(completedStepCount) / Double(totalSteps)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: AgentSpacing.lg) {
                // Header & Live Status Pill
                HStack {
                    Text("Execute")
                        .font(AgentFont.h1)
                        .foregroundColor(AgentColor.textPrimary)

                    Spacer()

                    StatusPillView(status: currentOrbStatus)
                }

                // Task Goal Input / Summary Card
                VStack(alignment: .leading, spacing: AgentSpacing.sm) {
                    Text("Task Goal")
                        .font(AgentFont.caption)
                        .foregroundColor(AgentColor.textMuted)

                    TextField("Enter goal (e.g. Summarize weekly emails)", text: $viewModel.currentGoal)
                        .font(AgentFont.body)
                        .padding(AgentSpacing.md)
                        .background(AgentColor.background3)
                        .foregroundColor(AgentColor.textPrimary)
                        .cornerRadius(AgentRadius.tile)
                        .overlay(
                            RoundedRectangle(cornerRadius: AgentRadius.tile)
                                .stroke(AgentColor.hairline, lineWidth: AgentBorder.hairline)
                        )

                    HStack(spacing: AgentSpacing.sm) {
                        Button(action: {
                            Task {
                                await viewModel.runTask(requestPermissionPrompt: false)
                            }
                        }) {
                            Text("Run Task")
                                .font(AgentFont.subheadline)
                                .foregroundColor(AgentColor.background1)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 12)
                                .background(AgentColor.accent)
                                .clipShape(RoundedRectangle(cornerRadius: AgentRadius.button))
                        }
                        .disabled(viewModel.executionState == .running || viewModel.executionState == .preparing)

                        Button(action: {
                            Task {
                                await viewModel.runTask(requestPermissionPrompt: true)
                            }
                        }) {
                            Text("Run + Permission")
                                .font(AgentFont.subheadline)
                                .foregroundColor(AgentColor.textPrimary)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 12)
                                .background(AgentColor.background3)
                                .overlay(
                                    RoundedRectangle(cornerRadius: AgentRadius.button)
                                        .stroke(AgentColor.hairlineStrong, lineWidth: AgentBorder.hairlineStrong)
                                )
                                .clipShape(RoundedRectangle(cornerRadius: AgentRadius.button))
                        }
                        .disabled(viewModel.executionState == .running || viewModel.executionState == .preparing)
                    }
                }
                .padding(AgentSpacing.lg)
                .background(AgentColor.background2)
                .overlay(
                    RoundedRectangle(cornerRadius: AgentRadius.card)
                        .stroke(AgentColor.hairline, lineWidth: AgentBorder.hairline)
                )
                .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))

                // Execution Steps Stream Card
                VStack(alignment: .leading, spacing: AgentSpacing.md) {
                    Text("Execution Stream")
                        .font(AgentFont.caption)
                        .foregroundColor(AgentColor.textMuted)

                    VStack(alignment: .leading, spacing: AgentSpacing.sm) {
                        StepProgressRow(
                            title: "Initialize runtime context & policy checks",
                            status: stepStatusForPhase(0)
                        )

                        StepProgressRow(
                            title: "Generate execution plan & resolve capabilities",
                            status: stepStatusForPhase(1)
                        )

                        StepProgressRow(
                            title: "Execute goal steps on Agent Core",
                            status: stepStatusForPhase(2)
                        )

                        StepProgressRow(
                            title: "Verify execution output & record experience",
                            status: stepStatusForPhase(3)
                        )
                    }

                    ProgressBarView(
                        progress: currentProgress,
                        fillColor: progressFillColor
                    )
                }
                .padding(AgentSpacing.lg)
                .background(AgentColor.background2)
                .overlay(
                    RoundedRectangle(cornerRadius: AgentRadius.card)
                        .stroke(AgentColor.hairline, lineWidth: AgentBorder.hairline)
                )
                .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))

                // Last Run Result / Error Banner
                if let result = viewModel.lastRunResult {
                    VStack(alignment: .leading, spacing: AgentSpacing.xs) {
                        HStack {
                            Text("Run Result (\(result.runId))")
                                .font(AgentFont.headline)
                                .foregroundColor(AgentColor.textPrimary)

                            Spacer()

                            Text(result.status.rawValue)
                                .font(AgentFont.captionSmall)
                                .fontWeight(.bold)
                                .foregroundColor(result.status == .success ? AgentColor.success : AgentColor.danger)
                        }

                        if let output = result.output, !output.isEmpty {
                            Text(output)
                                .font(AgentFont.secondary)
                                .foregroundColor(AgentColor.textSecondary)
                        }

                        if let err = result.errorMessage, !err.isEmpty {
                            Text(err)
                                .font(AgentFont.caption)
                                .foregroundColor(AgentColor.danger)
                        }
                    }
                    .padding(AgentSpacing.lg)
                    .background(result.status == .success ? AgentColor.successDim : AgentColor.dangerDim)
                    .overlay(
                        RoundedRectangle(cornerRadius: AgentRadius.card)
                            .stroke(result.status == .success ? AgentColor.success : AgentColor.danger, lineWidth: AgentBorder.hairline)
                    )
                    .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))
                }

                if let errPayload = viewModel.lastErrorPayload, viewModel.lastRunResult == nil {
                    VStack(alignment: .leading, spacing: AgentSpacing.xs) {
                        Text("Execution Error")
                            .font(AgentFont.headline)
                            .foregroundColor(AgentColor.danger)

                        Text(errPayload)
                            .font(AgentFont.secondary)
                            .foregroundColor(AgentColor.danger)
                    }
                    .padding(AgentSpacing.lg)
                    .background(AgentColor.dangerDim)
                    .overlay(
                        RoundedRectangle(cornerRadius: AgentRadius.card)
                            .stroke(AgentColor.danger, lineWidth: AgentBorder.hairline)
                    )
                    .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))
                }

                // Control Action Buttons (Cancel / Retry)
                HStack(spacing: AgentSpacing.md) {
                    Button(action: {
                        viewModel.cancelTask()
                    }) {
                        Text("Cancel")
                            .font(AgentFont.body)
                            .fontWeight(.semibold)
                            .foregroundColor(AgentColor.textPrimary)
                            .frame(maxWidth: .infinity)
                            .frame(height: 48)
                            .background(AgentColor.background3)
                            .overlay(
                                RoundedRectangle(cornerRadius: AgentRadius.button)
                                    .stroke(AgentColor.hairlineStrong, lineWidth: AgentBorder.hairlineStrong)
                            )
                            .clipShape(RoundedRectangle(cornerRadius: AgentRadius.button))
                    }

                    Button(action: {
                        Task {
                            await viewModel.runTask(requestPermissionPrompt: false)
                        }
                    }) {
                        Text("Retry")
                            .font(AgentFont.body)
                            .fontWeight(.semibold)
                            .foregroundColor(AgentColor.textPrimary)
                            .frame(maxWidth: .infinity)
                            .frame(height: 48)
                            .background(AgentColor.background3)
                            .overlay(
                                RoundedRectangle(cornerRadius: AgentRadius.button)
                                    .stroke(AgentColor.hairlineStrong, lineWidth: AgentBorder.hairlineStrong)
                            )
                            .clipShape(RoundedRectangle(cornerRadius: AgentRadius.button))
                    }
                    .disabled(viewModel.executionState == .running || viewModel.executionState == .preparing)
                    .opacity((viewModel.executionState == .running || viewModel.executionState == .preparing) ? 0.5 : 1.0)
                }
            }
            .padding(AgentSpacing.lg)
        }
        .background(AgentColor.background1.ignoresSafeArea())
    }

    private func stepStatusForPhase(_ stepIndex: Int) -> ExecutionStepStatus {
        switch viewModel.executionState {
        case .idle:
            return .pending
        case .preparing:
            return stepIndex == 0 ? .active : .pending
        case .waitingForPermission:
            return stepIndex <= 1 ? .completed : (stepIndex == 2 ? .active : .pending)
        case .running:
            if stepIndex < 2 { return .completed }
            if stepIndex == 2 { return .active }
            return .pending
        case .completed:
            return .completed
        case .failed, .cancelled:
            if stepIndex < 2 { return .completed }
            return .failed
        }
    }

    private var progressFillColor: Color {
        switch viewModel.executionState {
        case .completed: return AgentColor.success
        case .failed, .cancelled: return AgentColor.danger
        case .running, .preparing, .waitingForPermission: return AgentColor.warning
        case .idle: return AgentColor.accent
        }
    }
}
