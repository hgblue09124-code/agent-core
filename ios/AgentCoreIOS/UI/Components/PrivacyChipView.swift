// ios/AgentCoreIOS/UI/Components/PrivacyChipView.swift
// Personal Agent Privacy & On-Device Chip Component

import SwiftUI

struct PrivacyChipView: View {
    let label: String
    let isLocal: Bool

    init(label: String = "On-device", isLocal: Bool = true) {
        self.label = label
        self.isLocal = isLocal
    }

    var body: some View {
        HStack(spacing: 5) {
            Image(systemName: isLocal ? "lock.shield.fill" : "globe")
                .font(.system(size: 11, weight: .semibold))

            Text(label)
                .font(AgentFont.captionSmall)
                .fontWeight(.medium)
        }
        .padding(.horizontal, 9)
        .padding(.vertical, 3)
        .background(isLocal ? AgentColor.successDim : AgentColor.background3)
        .foregroundColor(isLocal ? AgentColor.success : AgentColor.textSecondary)
        .overlay(
            RoundedRectangle(cornerRadius: AgentRadius.small)
                .stroke(isLocal ? Color.clear : AgentColor.hairline, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: AgentRadius.small))
    }
}
