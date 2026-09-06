// ios/AgentCoreIOS/UI/Components/QuickActionCard.swift
// Personal Agent Quick Action Card Component

import SwiftUI

public struct QuickActionCard: View {
    public let title: String
    public let iconName: String
    public let isAccent: Bool
    public let action: () -> Void

    public init(
        title: String,
        iconName: String,
        isAccent: Bool = false,
        action: @escaping () -> Void
    ) {
        self.title = title
        self.iconName = iconName
        self.isAccent = isAccent
        self.action = action
    }

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 10) {
                ZStack {
                    RoundedRectangle(cornerRadius: AgentRadius.tile)
                        .fill(isAccent ? AgentColor.accentDim : AgentColor.background3)
                        .overlay(
                            RoundedRectangle(cornerRadius: AgentRadius.tile)
                                .stroke(isAccent ? Color.clear : AgentColor.hairline, lineWidth: AgentBorder.hairline)
                        )
                        .frame(width: 38, height: 38)

                    Image(systemName: iconName)
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundColor(isAccent ? AgentColor.accent : AgentColor.textPrimary)
                }

                Text(title)
                    .font(AgentFont.subheadline)
                    .foregroundColor(AgentColor.textPrimary)
                    .multilineTextAlignment(.leading)
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
        .buttonStyle(.plain)
    }
}
