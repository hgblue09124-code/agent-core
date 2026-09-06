// ios/AgentCoreIOS/UI/Execute/ExecuteView.swift
// Personal Agent Execute View — Live Execution Observer

import SwiftUI

struct ExecuteView: View {
    @EnvironmentObject private var viewModel: AgentAppViewModel

    init() {}

    private var runtimeState: AgentRuntimeState {
        viewModel.runtimeStore.state
    }

    private var currentOrbStatus: AgentStatus {
        runtimeState.status
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
                        .disabled(runtimeState.phase == .executing || runtimeState.phase == .thinking || runtimeState.phase == .planning)

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
                        .disabled(runtimeState.phase == .executing || runtimeState.phase == .thinking || runtimeState.phase == .planning)
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
                        if runtimeState.steps.isEmpty {
                            StepProgressRow(
                                title: runtimeState.phase == .idle ? "Ready to execute goal" : "Generating execution plan...",
                                status: runtimeState.phase == .idle ? .pending : .active
                            )
                        } else {
                            ForEach(runtimeState.steps) { step in
                                StepProgressRow(
                                    title: step.title,
                                    status: step.status
                                )
                            }
                        }
                    }

                    ProgressBarView(
                        progress: runtimeState.progress,
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

                if let err = runtimeState.error, viewModel.lastRunResult == nil {
                    VStack(alignment: .leading, spacing: AgentSpacing.xs) {
                        Text("Execution Error")
                            .font(AgentFont.headline)
                            .foregroundColor(AgentColor.danger)

                        Text(err)
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
                            await viewModel.retryTask()
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
                    .disabled(runtimeState.phase == .executing || runtimeState.phase == .thinking || runtimeState.phase == .planning)
                    .opacity((runtimeState.phase == .executing || runtimeState.phase == .thinking || runtimeState.phase == .planning) ? 0.5 : 1.0)
                }
            }
            .padding(AgentSpacing.lg)
        }
        .background(AgentColor.background1.ignoresSafeArea())
    }

    private var progressFillColor: Color {
        switch runtimeState.phase {
        case .completed: return AgentColor.success
        case .failed, .cancelled: return AgentColor.danger
        case .executing, .thinking, .planning: return AgentColor.warning
        case .idle: return AgentColor.accent
        }
    }
}
