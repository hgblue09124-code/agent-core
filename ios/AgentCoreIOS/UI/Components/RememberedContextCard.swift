// ios/AgentCoreIOS/UI/Components/RememberedContextCard.swift
// Personal Agent Remembered Context Card Component

import SwiftUI

struct RememberedContextCard: View {
    let summary: String

    init(summary: String) {
        self.summary = summary
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Context the agent remembers")
                .font(AgentFont.caption)
                .foregroundColor(AgentColor.textMuted)

            Text(summary.isEmpty ? "No personal context saved yet." : summary)
                .font(AgentFont.secondary)
                .foregroundColor(AgentColor.textSecondary)
                .lineLimit(3)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AgentColor.background2)
        .overlay(
            RoundedRectangle(cornerRadius: AgentRadius.card)
                .stroke(AgentColor.hairline, lineWidth: AgentBorder.hairline)
        )
        .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))
    }
}
