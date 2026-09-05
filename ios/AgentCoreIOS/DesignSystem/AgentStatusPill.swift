// ios/AgentCoreIOS/DesignSystem/AgentStatusPill.swift
// Status Pills for 9 Interaction States — Personal Agent iOS

import SwiftUI

public struct AgentStatusPill: View {
    public let state: AgentState
    public var fontSize: CGFloat = 12.5

    @State private var pulse: Bool = false

    public init(state: AgentState, fontSize: CGFloat = 12.5) {
        self.state = state
        self.fontSize = fontSize
    }

    public var body: some View {
        HStack(spacing: 6) {
            // Dot Indicator
            Circle()
                .fill(dotColor)
                .frame(width: fontSize * 0.55, height: fontSize * 0.55)
                .scaleEffect(pulse ? 1.25 : 1.0)
                .opacity(pulse ? 1.0 : 0.7)

            Text(state.title)
                .font(.system(size: fontSize, weight: .semibold))
                .foregroundColor(textColor)
        }
        .padding(.horizontal, fontSize * 0.9)
        .padding(.vertical, fontSize * 0.45)
        .background(backgroundColor)
        .cornerRadius(AgentTheme.radiusPill)
        .overlay(
            RoundedRectangle(cornerRadius: AgentTheme.radiusPill)
                .stroke(borderColor, lineWidth: 1)
        )
        .onAppear {
            if state == .thinking || state == .running {
                withAnimation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true)) {
                    pulse = true
                }
            }
        }
    }

    private var dotColor: Color {
        switch state {
        case .idle: return AgentTheme.success
        case .thinking: return AgentTheme.cyan
        case .running: return AgentTheme.accent
        case .completed: return AgentTheme.success
        case .failed, .cancelling: return AgentTheme.danger
        case .offline, .empty: return AgentTheme.offline
        case .approvalRequired: return AgentTheme.warning
        }
    }

    private var textColor: Color {
        switch state {
        case .idle, .completed: return AgentTheme.success
        case .thinking: return AgentTheme.cyan
        case .running: return AgentTheme.accent
        case .failed, .cancelling: return AgentTheme.danger
        case .offline, .empty: return AgentTheme.text3
        case .approvalRequired: return AgentTheme.warning
        }
    }

    private var backgroundColor: Color {
        switch state {
        case .idle, .completed: return AgentTheme.successDim
        case .thinking: return AgentTheme.cyan.opacity(0.14)
        case .running: return AgentTheme.accentDim
        case .failed, .cancelling: return AgentTheme.dangerDim
        case .offline, .empty: return AgentTheme.bg3
        case .approvalRequired: return AgentTheme.warningDim
        }
    }

    private var borderColor: Color {
        switch state {
        case .idle, .completed: return AgentTheme.success.opacity(0.3)
        case .thinking: return AgentTheme.cyan.opacity(0.3)
        case .running: return AgentTheme.accent.opacity(0.3)
        case .failed, .cancelling: return AgentTheme.danger.opacity(0.3)
        case .offline, .empty: return AgentTheme.hair
        case .approvalRequired: return AgentTheme.warning.opacity(0.3)
        }
    }
}
