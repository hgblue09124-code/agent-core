// ios/AgentCoreIOS/UI/Review/ReviewView.swift
// Interactive Review Console — Developer Testing Console Restyled for Dark Theme

import SwiftUI

public struct ReviewView: View {
    @EnvironmentObject private var viewModel: AgentAppViewModel

    public init() {}

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: AgentSpacing.lg) {
                // Title Header
                VStack(alignment: .leading, spacing: 4) {
                    Text("Interactive Review Console")
                        .font(AgentFont.h1)
                        .foregroundColor(AgentColor.textPrimary)

                    Text("Agent-Core Validation Environment")
                        .font(AgentFont.caption)
                        .foregroundColor(AgentColor.textMuted)
                }

                // Section 1: Review Dashboard
                VStack(alignment: .leading, spacing: AgentSpacing.md) {
                    HStack {
                        Text("Review Dashboard")
                            .font(AgentFont.headline)
                            .foregroundColor(AgentColor.textPrimary)

                        Spacer()

                        Button("Run All Checks") {
                            Task { await viewModel.runAllReviewChecks() }
                        }
                        .font(AgentFont.caption)
                        .fontWeight(.semibold)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(AgentColor.accent)
                        .foregroundColor(AgentColor.background1)
                        .clipShape(Capsule())
                    }

                    Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 8) {
                        GridRow {
                            StatusCell(title: "Agent-Core", status: viewModel.agentCoreStatus)
                            StatusCell(title: "AgentRuntime", status: viewModel.agentRuntimeStatus)
                        }
                        GridRow {
                            StatusCell(title: "Local Storage", status: viewModel.localStorageStatus)
                            StatusCell(title: "Memory / Vault", status: viewModel.memoryVaultStatus)
                        }
                        GridRow {
                            StatusCell(title: "Connection", status: viewModel.connectionStatus)
                            StatusCell(title: "Execution", status: viewModel.currentExecutionStatus)
                        }
                    }
                }
                .padding(AgentSpacing.lg)
                .background(AgentColor.background2)
                .overlay(
                    RoundedRectangle(cornerRadius: AgentRadius.card)
                        .stroke(AgentColor.hairline, lineWidth: AgentBorder.hairline)
                )
                .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))

                // Section 2: Interactive Agent Test
                VStack(alignment: .leading, spacing: AgentSpacing.md) {
                    Text("Agent Execution Test")
                        .font(AgentFont.headline)
                        .foregroundColor(AgentColor.textPrimary)

                    TextField("Enter task (e.g. Remember that my favorite color is blue.)", text: $viewModel.currentGoal)
                        .font(AgentFont.body)
                        .padding(AgentSpacing.md)
                        .background(AgentColor.background3)
                        .foregroundColor(AgentColor.textPrimary)
                        .cornerRadius(AgentRadius.tile)

                    HStack(spacing: 8) {
                        Button("Run") {
                            Task { await viewModel.runTask(requestPermissionPrompt: false) }
                        }
                        .font(AgentFont.caption)
                        .fontWeight(.semibold)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(AgentColor.accent)
                        .foregroundColor(AgentColor.background1)
                        .clipShape(Capsule())

                        Button("Run (Prompt Permission)") {
                            Task { await viewModel.runTask(requestPermissionPrompt: true) }
                        }
                        .font(AgentFont.caption)
                        .fontWeight(.semibold)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(AgentColor.background3)
                        .foregroundColor(AgentColor.textPrimary)
                        .clipShape(Capsule())

                        Button("Cancel") {
                            viewModel.cancelTask()
                        }
                        .font(AgentFont.caption)
                        .fontWeight(.semibold)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(AgentColor.dangerDim)
                        .foregroundColor(AgentColor.danger)
                        .clipShape(Capsule())
                    }

                    HStack {
                        Text("Lifecycle State:")
                            .font(AgentFont.caption)
                            .foregroundColor(AgentColor.textMuted)

                        Text(viewModel.executionState.rawValue)
                            .font(AgentFont.captionSmall)
                            .fontWeight(.bold)
                            .foregroundColor(viewModel.executionState.color)
                    }
                }
                .padding(AgentSpacing.lg)
                .background(AgentColor.background2)
                .overlay(
                    RoundedRectangle(cornerRadius: AgentRadius.card)
                        .stroke(AgentColor.hairline, lineWidth: AgentBorder.hairline)
                )
                .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))

                // Section 3: Automated Review Checks Summary
                VStack(alignment: .leading, spacing: AgentSpacing.md) {
                    Text("Automated Review Checks")
                        .font(AgentFont.headline)
                        .foregroundColor(AgentColor.textPrimary)

                    ForEach(viewModel.reviewChecks) { item in
                        HStack {
                            Text("\(item.id). \(item.name)")
                                .font(AgentFont.body)
                                .foregroundColor(AgentColor.textPrimary)

                            Spacer()

                            Text(item.status.rawValue)
                                .font(AgentFont.captionSmall)
                                .fontWeight(.bold)
                                .foregroundColor(item.status.color)
                        }

                        Text("   Component: \(item.component) | Result: \(item.message)")
                            .font(AgentFont.captionSmall)
                            .foregroundColor(AgentColor.textMuted)

                        Divider().background(AgentColor.hairline)
                    }

                    HStack {
                        Text("\(viewModel.passCount) / 10 PASS")
                            .font(AgentFont.title)
                            .foregroundColor(viewModel.passCount == 10 ? AgentColor.success : AgentColor.warning)

                        Spacer()

                        Text("Blockers: \(viewModel.blockerDetails.count)")
                            .font(AgentFont.caption)
                            .fontWeight(.bold)
                            .foregroundColor(viewModel.blockerDetails.isEmpty ? AgentColor.success : AgentColor.danger)
                    }
                }
                .padding(AgentSpacing.lg)
                .background(AgentColor.background2)
                .overlay(
                    RoundedRectangle(cornerRadius: AgentRadius.card)
                        .stroke(AgentColor.hairline, lineWidth: AgentBorder.hairline)
                )
                .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))
            }
            .padding(AgentSpacing.lg)
        }
        .background(AgentColor.background1.ignoresSafeArea())
    }
}
