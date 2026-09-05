// ios/AgentCoreIOS/Views/ConnectionsView.swift
// Connections (API / Capabilities) Screen — Personal Agent iOS

import SwiftUI

public struct ConnectionsView: View {
    @ObservedObject public var viewModel: AgentAppViewModel

    public init(viewModel: AgentAppViewModel) {
        self.viewModel = viewModel
    }

    public var body: some View {
        ScrollView(.vertical, showsIndicators: true) {
            VStack(spacing: 16) {
                // Header Bar
                HStack {
                    Text("Connections")
                        .font(.system(size: 20, weight: .bold))
                        .foregroundColor(AgentTheme.text1)

                    Spacer()

                    Text("Local vs Remote")
                        .font(.system(size: 11.5))
                        .foregroundColor(AgentTheme.text3)
                }
                .padding(.top, 8)

                // Connections List Card
                VStack(spacing: 12) {
                    ForEach(viewModel.connections) { conn in
                        AgentListRow(
                            title: conn.name,
                            subtitle: conn.subtitle,
                            icon: conn.type == .local ? "cpu" : "network",
                            iconColor: conn.type == .local ? AgentTheme.success : AgentTheme.accent,
                            tileBackground: conn.type == .local ? AgentTheme.successDim : AgentTheme.accentDim,
                            rightBadge: AnyView(ConnectionChip(type: conn.type))
                        )

                        if conn.id != viewModel.connections.last?.id {
                            Divider()
                                .background(AgentTheme.hair)
                        }
                    }
                }
                .agentCard(padding: 14)

                // GitHub Data Update Card (Data/Config Only)
                VStack(alignment: .leading, spacing: 10) {
                    Text("GITHUB DATA SYNC (DATA/CONFIG ONLY)")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(AgentTheme.text3)

                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Data Version")
                                .font(.system(size: 12, weight: .medium))
                                .foregroundColor(AgentTheme.text1)
                            Text(viewModel.updateReport.installedDataVersion)
                                .font(.system(size: 11))
                                .foregroundColor(AgentTheme.text2)
                        }

                        Spacer()

                        Button("Check Updates") {
                            Task { await viewModel.checkForDataUpdates() }
                        }
                        .font(.system(size: 11.5, weight: .semibold))
                        .foregroundColor(AgentTheme.accent)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .background(AgentTheme.accentDim)
                        .cornerRadius(AgentTheme.radiusS)
                    }

                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Sync Status")
                                .font(.system(size: 12, weight: .medium))
                                .foregroundColor(AgentTheme.text1)
                            Text(viewModel.updateReport.status.rawValue)
                                .font(.system(size: 11))
                                .foregroundColor(AgentTheme.text2)
                        }

                        Spacer()

                        Button("Sync Now") {
                            Task { await viewModel.syncDataNow() }
                        }
                        .font(.system(size: 11.5, weight: .semibold))
                        .foregroundColor(AgentTheme.bg0)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 5)
                        .background(AgentTheme.accent)
                        .cornerRadius(AgentTheme.radiusS)
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
