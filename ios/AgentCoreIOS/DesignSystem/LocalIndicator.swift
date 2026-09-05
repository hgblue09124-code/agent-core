// ios/AgentCoreIOS/DesignSystem/LocalIndicator.swift
// Local / On-device Security Badge — Personal Agent iOS

import SwiftUI

public struct LocalIndicator: View {
    public var label: String = "Private · Local"
    public var isShield: Bool = true

    public init(label: String = "Private · Local", isShield: Bool = true) {
        self.label = label
        self.isShield = isShield
    }

    public var body: some View {
        HStack(spacing: 5) {
            Image(systemName: isShield ? "shield.fill" : "lock.fill")
                .font(.system(size: 10, weight: .bold))
                .foregroundColor(AgentTheme.success)

            Text(label)
                .font(.system(size: 11, weight: .semibold))
                .foregroundColor(AgentTheme.success)
        }
        .padding(.horizontal, 9)
        .padding(.vertical, 4)
        .background(AgentTheme.successDim)
        .cornerRadius(AgentTheme.radiusPill)
        .overlay(
            RoundedRectangle(cornerRadius: AgentTheme.radiusPill)
                .stroke(AgentTheme.success.opacity(0.3), lineWidth: 1)
        )
    }
}
