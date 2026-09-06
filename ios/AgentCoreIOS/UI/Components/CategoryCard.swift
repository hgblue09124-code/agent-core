// ios/AgentCoreIOS/UI/Components/CategoryCard.swift
// Personal Agent Vault Category Card Component

import SwiftUI

struct CategoryCard: View {
    let title: String
    let itemCount: Int
    let iconName: String

    init(title: String, itemCount: Int, iconName: String = "folder.fill") {
        self.title = title
        self.itemCount = itemCount
        self.iconName = iconName
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: iconName)
                .font(.system(size: 18, weight: .medium))
                .foregroundColor(AgentColor.textSecondary)

            Text(title)
                .font(AgentFont.subheadline)
                .foregroundColor(AgentColor.textPrimary)

            Text("\(itemCount) items")
                .font(AgentFont.captionSmall)
                .foregroundColor(AgentColor.textMuted)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AgentColor.background2)
        .overlay(
            RoundedRectangle(cornerRadius: AgentRadius.card)
                .stroke(AgentColor.hairline, lineWidth: AgentBorder.hairline)
        )
        .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))
    }
}
