// ios/AgentCoreIOS/Views/ActivityView.swift
// Activity Timeline Screen — Personal Agent iOS

import SwiftUI

public struct ActivityView: View {
    @ObservedObject public var viewModel: AgentAppViewModel

    public init(viewModel: AgentAppViewModel) {
        self.viewModel = viewModel
    }

    public var body: some View {
        ScrollView(.vertical, showsIndicators: true) {
            VStack(spacing: 16) {
                // Header Bar
                HStack {
                    Text("Activity")
                        .font(.system(size: 20, weight: .bold))
                        .foregroundColor(AgentTheme.text1)

                    Spacer()

                    Text("\(viewModel.filteredExperiences.count) runs")
                        .font(.system(size: 12))
                        .foregroundColor(AgentTheme.text3)
                }
                .padding(.top, 8)

                // Filter Segment Control
                AgentSegmentedControl(
                    options: ["All", "Success", "Failed"],
                    selected: $viewModel.activityFilter
                )

                // Timeline List Card
                if viewModel.filteredExperiences.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "clock.arrow.circlepath")
                            .font(.system(size: 28))
                            .foregroundColor(AgentTheme.text3)
                        Text("No activity matching '\(viewModel.activityFilter)'")
                            .font(.system(size: 13))
                            .foregroundColor(AgentTheme.text2)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 32)
                    .agentCard(padding: 14)
                } else {
                    VStack(spacing: 12) {
                        ForEach(viewModel.filteredExperiences, id: \.runId) { exp in
                            let isSuccess = exp.outcome.uppercased() == "COMPLETED" || exp.outcome.uppercased() == "SUCCESS"
                            let iconName = isSuccess ? "checkmark" : "xmark"
                            let iconColor = isSuccess ? AgentTheme.success : AgentTheme.danger
                            let bgTile = isSuccess ? AgentTheme.successDim : AgentTheme.dangerDim

                            AgentListRow(
                                title: exp.goal,
                                subtitle: "Run \(exp.runId) · \(exp.outcome.lowercased())",
                                icon: iconName,
                                iconColor: iconColor,
                                tileBackground: bgTile,
                                rightText: "0.8s"
                            )

                            if exp.runId != viewModel.filteredExperiences.last?.runId {
                                Divider()
                                    .background(AgentTheme.hair)
                            }
                        }
                    }
                    .agentCard(padding: 14)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .background(AgentTheme.bg1.ignoresSafeArea())
    }
}
