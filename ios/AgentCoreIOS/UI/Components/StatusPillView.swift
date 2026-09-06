// ios/AgentCoreIOS/UI/Components/StatusPillView.swift
// Personal Agent Status Pill Component

import SwiftUI

struct StatusPillView: View {
    let status: AgentStatus
    let customTitle: String?

    init(status: AgentStatus, customTitle: String? = nil) {
        self.status = status
        self.customTitle = customTitle
    }

    private var titleText: String {
        if let custom = customTitle { return custom }
        switch status {
        case .ready: return "Ready"
        case .thinking: return "Thinking"
        case .running: return "Running"
        case .offline: return "Offline"
        }
    }

    private var backgroundColor: Color {
        switch status {
        case .ready: return AgentColor.successDim
        case .thinking: return AgentColor.accentDim
        case .running: return AgentColor.warningDim
        case .offline: return Color.white.opacity(0.12)
        }
    }

    private var foregroundColor: Color {
        switch status {
        case .ready: return AgentColor.success
        case .thinking: return AgentColor.accent
        case .running: return AgentColor.warning
        case .offline: return AgentColor.offline
        }
    }

    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(foregroundColor)
                .frame(width: 6, height: 6)

            Text(titleText)
                .font(AgentFont.captionSmall)
                .fontWeight(.medium)
                .foregroundColor(foregroundColor)
        }
        .padding(.horizontal, 11)
        .padding(.vertical, 5)
        .background(backgroundColor)
        .clipShape(Capsule())
    }
}
