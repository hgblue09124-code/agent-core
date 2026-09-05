// ios/AgentCoreIOS/DesignSystem/ConnectionChip.swift
// Connection Chips (Local vs Remote) — Personal Agent iOS

import SwiftUI

public enum ConnectionType {
    case local
    case remote
}

public struct ConnectionChip: View {
    public let type: ConnectionType

    public init(type: ConnectionType) {
        self.type = type
    }

    public var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(chipColor)
                .frame(width: 5, height: 5)

            Text(type == .local ? "Local" : "Remote")
                .font(.system(size: 10, weight: .semibold))
                .foregroundColor(chipColor)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 3)
        .background(chipBackground)
        .cornerRadius(AgentTheme.radiusPill)
        .overlay(
            RoundedRectangle(cornerRadius: AgentTheme.radiusPill)
                .stroke(chipColor.opacity(0.3), lineWidth: 1)
        )
    }

    private var chipColor: Color {
        switch type {
        case .local: return AgentTheme.success
        case .remote: return AgentTheme.accent
        }
    }

    private var chipBackground: Color {
        switch type {
        case .local: return AgentTheme.successDim
        case .remote: return AgentTheme.accentDim
        }
    }
}
