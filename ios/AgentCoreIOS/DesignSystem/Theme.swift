// ios/AgentCoreIOS/DesignSystem/Theme.swift
// Source of Truth Design System Tokens — Personal Agent iOS

import SwiftUI

public enum AgentState: String, CaseIterable, Codable {
    case idle = "IDLE"
    case thinking = "THINKING"
    case running = "RUNNING"
    case completed = "COMPLETED"
    case failed = "FAILED"
    case offline = "OFFLINE"
    case approvalRequired = "APPROVAL_REQUIRED"
    case cancelling = "CANCELLING"
    case empty = "EMPTY"

    public var title: String {
        switch self {
        case .idle: return "Ready"
        case .thinking: return "Thinking"
        case .running: return "Running"
        case .completed: return "Completed"
        case .failed: return "Failed"
        case .offline: return "Offline"
        case .approvalRequired: return "Approval Required"
        case .cancelling: return "Cancelling"
        case .empty: return "No Activity"
        }
    }

    public var description: String {
        switch self {
        case .idle: return "Waiting for a task. No motion, orb static."
        case .thinking: return "Orb rotates slowly, gradient breathing."
        case .running: return "Active execution loop with live step tracking."
        case .completed: return "Task finished successfully."
        case .failed: return "Task execution encountered an error."
        case .offline: return "On-device tasks still work; remote ones queue."
        case .approvalRequired: return "Mutating action requires explicit user permission."
        case .cancelling: return "Stopping task execution cleanly..."
        case .empty: return "No agent tasks or history recorded yet."
        }
    }
}

public struct AgentTheme {
    // Colors matching Claude UI Design Concept
    public static let bg0 = Color(hex: 0x020203)
    public static let bg1 = Color(hex: 0x0A0A0D)
    public static let bg2 = Color(hex: 0x141417)
    public static let bg3 = Color(hex: 0x1D1D22)
    public static let bg4 = Color(hex: 0x26262C)

    public static let hair = Color.white.opacity(0.08)
    public static let hairStrong = Color.white.opacity(0.14)

    public static let text1 = Color(hex: 0xF5F5F7)
    public static let text2 = Color(hex: 0xF5F5F7).opacity(0.62)
    public static let text3 = Color(hex: 0xF5F5F7).opacity(0.36)

    public static let accent = Color(hex: 0x7C8CFF)
    public static let accentDim = Color(hex: 0x7C8CFF).opacity(0.14)
    public static let violet = Color(hex: 0xB18CFF)
    public static let cyan = Color(hex: 0x7FE0E0)

    public static let success = Color(hex: 0x3DD68C)
    public static let successDim = Color(hex: 0x3DD68C).opacity(0.14)

    public static let warning = Color(hex: 0xF5B84D)
    public static let warningDim = Color(hex: 0xF5B84D).opacity(0.14)

    public static let danger = Color(hex: 0xF5716B)
    public static let dangerDim = Color(hex: 0xF5716B).opacity(0.14)

    public static let offline = Color(hex: 0x8B8B92)

    // Corner Radiuses
    public static let radiusS: CGFloat = 8
    public static let radiusM: CGFloat = 14
    public static let radiusL: CGFloat = 20
    public static let radiusPill: CGFloat = 999
}

extension Color {
    init(hex: UInt, alpha: Double = 1.0) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xff) / 255.0,
            green: Double((hex >> 8) & 0xff) / 255.0,
            blue: Double(hex & 0xff) / 255.0,
            opacity: alpha
        )
    }
}

public struct AgentCardModifier: ViewModifier {
    var padding: CGFloat = 14

    public func body(content: Content) -> some View {
        content
            .padding(padding)
            .background(AgentTheme.bg2)
            .cornerRadius(AgentTheme.radiusM)
            .overlay(
                RoundedRectangle(cornerRadius: AgentTheme.radiusM)
                    .stroke(AgentTheme.hair, lineWidth: 1)
            )
    }
}

extension View {
    public func agentCard(padding: CGFloat = 14) -> some View {
        self.modifier(AgentCardModifier(padding: padding))
    }
}
