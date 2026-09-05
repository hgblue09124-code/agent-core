// ios/AgentCoreIOS/Views/ExecuteView.swift
// Agent / Execute Screen — Personal Agent iOS

import SwiftUI

public struct ExecuteView: View {
    @ObservedObject public var viewModel: AgentAppViewModel

    public init(viewModel: AgentAppViewModel) {
        self.viewModel = viewModel
    }

    public var body: some View {
        ScrollView(.vertical, showsIndicators: true) {
            VStack(spacing: 16) {
                // Header Bar
                HStack {
                    Text("Execute")
                        .font(.system(size: 20, weight: .bold))
                        .foregroundColor(AgentTheme.text1)

                    Spacer()

                    AgentStatusPill(state: viewModel.state, fontSize: 11.5)
                }
                .padding(.top, 8)

                // Current Task Goal Card
                VStack(alignment: .leading, spacing: 8) {
                    Text("CURRENT TASK")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(AgentTheme.text3)

                    Text("\"\(viewModel.currentGoal)\"")
                        .font(.system(size: 13.5, weight: .medium))
                        .foregroundColor(AgentTheme.text1)
                        .lineSpacing(3)

                    if viewModel.state == .running || viewModel.state == .thinking {
                        AgentProgressBar(progress: viewModel.progress)
                            .padding(.top, 6)
                    }
                }
                .agentCard(padding: 14)

                // Policy Approval Card if Required
                if viewModel.state == .approvalRequired {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundColor(AgentTheme.warning)
                            Text("User Permission Required")
                                .font(.system(size: 13, weight: .bold))
                                .foregroundColor(AgentTheme.warning)
                        }

                        Text("This task requires write/mutating permissions to execute capability actions.")
                            .font(.system(size: 12))
                            .foregroundColor(AgentTheme.text2)

                        HStack(spacing: 12) {
                            Button(action: {
                                viewModel.cancelTask()
                            }) {
                                Text("Deny")
                                    .font(.system(size: 12.5, weight: .semibold))
                                    .foregroundColor(AgentTheme.text1)
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 8)
                                    .background(AgentTheme.bg4)
                                    .cornerRadius(AgentTheme.radiusS)
                            }

                            Button(action: {
                                viewModel.approveWritePolicy()
                            }) {
                                Text("Approve & Run")
                                    .font(.system(size: 12.5, weight: .semibold))
                                    .foregroundColor(AgentTheme.bg0)
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 8)
                                    .background(AgentTheme.warning)
                                    .cornerRadius(AgentTheme.radiusS)
                            }
                        }
                    }
                    .agentCard(padding: 14)
                }

                // Live Steps Timeline Card
                VStack(alignment: .leading, spacing: 12) {
                    Text("LIVE EXECUTION STEPS")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(AgentTheme.text3)

                    VStack(alignment: .leading, spacing: 12) {
                        ForEach(viewModel.liveSteps) { step in
                            HStack(spacing: 12) {
                                ZStack {
                                    if step.status == "COMPLETED" {
                                        Circle()
                                            .fill(AgentTheme.successDim)
                                            .frame(width: 24, height: 24)
                                        Image(systemName: "checkmark")
                                            .font(.system(size: 11, weight: .bold))
                                            .foregroundColor(AgentTheme.success)
                                    } else if step.status == "RUNNING" {
                                        AgentOrbView(state: .running, size: 24)
                                    } else if step.status == "FAILED" {
                                        Circle()
                                            .fill(AgentTheme.dangerDim)
                                            .frame(width: 24, height: 24)
                                        Image(systemName: "xmark")
                                            .font(.system(size: 11, weight: .bold))
                                            .foregroundColor(AgentTheme.danger)
                                    } else {
                                        Circle()
                                            .stroke(AgentTheme.hairStrong, lineWidth: 1.5)
                                            .frame(width: 24, height: 24)
                                    }
                                }

                                VStack(alignment: .leading, spacing: 2) {
                                    Text(step.title)
                                        .font(.system(size: 12.5, weight: step.status == "RUNNING" ? .semibold : .regular))
                                        .foregroundColor(step.status == "PENDING" ? AgentTheme.text3 : AgentTheme.text1)

                                    if let detail = step.detail {
                                        Text(detail)
                                            .font(.system(size: 11))
                                            .foregroundColor(AgentTheme.danger)
                                    }
                                }

                                Spacer()
                            }
                        }
                    }
                }
                .agentCard(padding: 14)

                // Action Controls: Cancel / Retry Buttons
                HStack(spacing: 12) {
                    if viewModel.state == .running || viewModel.state == .thinking {
                        Button(action: {
                            viewModel.cancelTask()
                        }) {
                            HStack {
                                Image(systemName: "stop.fill")
                                Text("Cancel Execution")
                            }
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundColor(AgentTheme.danger)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 10)
                            .background(AgentTheme.dangerDim)
                            .cornerRadius(AgentTheme.radiusM)
                        }
                    } else if viewModel.state == .failed {
                        Button(action: {
                            viewModel.retryTask()
                        }) {
                            HStack {
                                Image(systemName: "arrow.clockwise")
                                Text("Retry Task")
                            }
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundColor(AgentTheme.bg0)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 10)
                            .background(AgentTheme.accent)
                            .cornerRadius(AgentTheme.radiusM)
                        }
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .background(AgentTheme.bg1.ignoresSafeArea())
    }
}
