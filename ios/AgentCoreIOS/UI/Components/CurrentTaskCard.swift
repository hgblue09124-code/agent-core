// ios/AgentCoreIOS/UI/Components/CurrentTaskCard.swift
// Personal Agent Current Task Card Component

import SwiftUI

struct CurrentTaskCard: View {
    let goal: String
    let subtext: String
    let progress: Double
    let status: AgentStatus

    init(
        goal: String,
        subtext: String,
        progress: Double = 0.0,
        status: AgentStatus = .running
    ) {
        self.goal = goal
        self.subtext = subtext
        self.progress = progress
        self.status = status
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Current task")
                    .font(AgentFont.caption)
                    .foregroundColor(AgentColor.textMuted)

                Spacer()

                StatusPillView(status: status)
            }

            HStack(spacing: 10) {
                ZStack {
                    RoundedRectangle(cornerRadius: AgentRadius.tile)
                        .fill(AgentColor.warningDim)
                        .frame(width: 38, height: 38)

                    Image(systemName: "arrow.triangle.2.circlepath")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(AgentColor.warning)
                }

                VStack(alignment: .leading, spacing: 2) {
                    Text(goal)
                        .font(AgentFont.subheadline)
                        .foregroundColor(AgentColor.textPrimary)
                        .lineLimit(1)

                    Text(subtext)
                        .font(AgentFont.secondary)
                        .foregroundColor(AgentColor.textSecondary)
                        .lineLimit(1)
                }
            }

            ProgressBarView(progress: progress, fillColor: status == .running ? AgentColor.warning : AgentColor.accent)
        }
        .padding(16)
        .background(AgentColor.background2)
        .overlay(
            RoundedRectangle(cornerRadius: AgentRadius.card)
                .stroke(AgentColor.hairline, lineWidth: AgentBorder.hairline)
        )
        .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))
    }
}
