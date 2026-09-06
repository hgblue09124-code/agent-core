// ios/AgentCoreIOS/UI/Components/SettingsCard.swift
// Personal Agent Settings Card Container Component

import SwiftUI

public struct SettingsCard<Content: View>: View {
    public let content: Content

    public init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            content
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 4)
        .background(AgentColor.background2)
        .overlay(
            RoundedRectangle(cornerRadius: AgentRadius.card)
                .stroke(AgentColor.hairline, lineWidth: AgentBorder.hairline)
        )
        .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))
    }
}

public struct SettingsRowView: View {
    public let title: String
    public let detail: String?
    public let showChevron: Bool

    public init(title: String, detail: String? = nil, showChevron: Bool = true) {
        self.title = title
        self.detail = detail
        self.showChevron = showChevron
    }

    var body: some View {
        HStack {
            Text(title)
                .font(AgentFont.body)
                .foregroundColor(AgentColor.textPrimary)

            Spacer()

            if let detail = detail {
                Text(detail)
                    .font(AgentFont.secondary)
                    .foregroundColor(AgentColor.textMuted)
            }

            if showChevron {
                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(AgentColor.textMuted)
            }
        }
        .padding(.vertical, 12)
    }
}
