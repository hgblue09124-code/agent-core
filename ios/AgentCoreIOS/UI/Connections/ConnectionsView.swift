// ios/AgentCoreIOS/UI/Connections/ConnectionsView.swift
// Personal Agent Connections View — Capability & Service Integrations

import SwiftUI

struct ConnectionsView: View {
    @EnvironmentObject private var viewModel: AgentAppViewModel

    init() {}

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: AgentSpacing.lg) {
                // Header
                Text("Connections")
                    .font(AgentFont.h1)
                    .foregroundColor(AgentColor.textPrimary)

                // Connections List Container Card
                VStack(spacing: 0) {
                    if viewModel.connections.isEmpty {
                        VStack(spacing: 8) {
                            Image(systemName: "network")
                                .font(.system(size: 24))
                                .foregroundColor(AgentColor.textMuted)

                            Text("No connection services available.")
                                .font(AgentFont.secondary)
                                .foregroundColor(AgentColor.textMuted)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(AgentSpacing.xxl)
                    } else {
                        ForEach(viewModel.connections) { connection in
                            ConnectionRowView(
                                connection: connection,
                                onToggle: {
                                    // Non-destructive connection interaction
                                }
                            )

                            if connection.id != viewModel.connections.last?.id {
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
            .padding(AgentSpacing.lg)
        }
        .background(AgentColor.background1.ignoresSafeArea())
        .onAppear {
            Task {
                await viewModel.loadConnections()
            }
        }
    }
}
