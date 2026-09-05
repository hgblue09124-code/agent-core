// ios/AgentCoreIOS/DesignSystem/AgentOrbView.swift
// Multi-stop gradient animated Agent Orb — Personal Agent iOS

import SwiftUI

public struct AgentOrbView: View {
    public let state: AgentState
    public var size: CGFloat = 84

    @State private var rotation: Double = 0
    @State private var pulseScale: CGFloat = 1.0

    public init(state: AgentState, size: CGFloat = 84) {
        self.state = state
        self.size = size
    }

    public var body: some View {
        ZStack {
            // Outer glow blur for active states
            if state == .thinking || state == .running {
                Circle()
                    .fill(gradientColors)
                    .blur(radius: size * 0.25)
                    .opacity(0.5)
                    .scaleEffect(pulseScale)
            }

            // Main Orb Container
            Circle()
                .fill(gradientColors)
                .rotationEffect(.degrees(rotation))
                .scaleEffect(pulseScale)
                .frame(width: size, height: size)
                .overlay(
                    Circle()
                        .stroke(AgentTheme.hairStrong, lineWidth: 1)
                )

            // Inner Core Indicator
            Circle()
                .fill(coreColor)
                .frame(width: size * 0.22, height: size * 0.22)
                .shadow(color: coreColor.opacity(0.8), radius: 4)
        }
        .onAppear {
            updateAnimation()
        }
        .onChange(of: state) {
            updateAnimation()
        }
    }

    private var gradientColors: LinearGradient {
        switch state {
        case .idle:
            return LinearGradient(
                colors: [AgentTheme.accent, AgentTheme.violet.opacity(0.8)],
                startPoint: .topLeading, endPoint: .bottomTrailing
            )
        case .thinking:
            return LinearGradient(
                colors: [AgentTheme.cyan, AgentTheme.violet, AgentTheme.accent],
                startPoint: .top, endPoint: .bottom
            )
        case .running:
            return LinearGradient(
                colors: [AgentTheme.accent, AgentTheme.cyan, AgentTheme.violet],
                startPoint: .leading, endPoint: .trailing
            )
        case .completed:
            return LinearGradient(
                colors: [AgentTheme.success, AgentTheme.cyan.opacity(0.8)],
                startPoint: .topLeading, endPoint: .bottomTrailing
            )
        case .failed, .cancelling:
            return LinearGradient(
                colors: [AgentTheme.danger, AgentTheme.warning.opacity(0.8)],
                startPoint: .topLeading, endPoint: .bottomTrailing
            )
        case .offline, .empty:
            return LinearGradient(
                colors: [AgentTheme.offline.opacity(0.6), AgentTheme.bg4],
                startPoint: .topLeading, endPoint: .bottomTrailing
            )
        case .approvalRequired:
            return LinearGradient(
                colors: [AgentTheme.warning, AgentTheme.danger.opacity(0.8)],
                startPoint: .topLeading, endPoint: .bottomTrailing
            )
        }
    }

    private var coreColor: Color {
        switch state {
        case .idle: return AgentTheme.text1
        case .thinking: return AgentTheme.cyan
        case .running: return AgentTheme.accent
        case .completed: return AgentTheme.success
        case .failed, .cancelling: return AgentTheme.danger
        case .offline, .empty: return AgentTheme.offline
        case .approvalRequired: return AgentTheme.warning
        }
    }

    private func updateAnimation() {
        switch state {
        case .thinking:
            withAnimation(.linear(duration: 4.0).repeatForever(autoreverses: false)) {
                rotation = 360
            }
            withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) {
                pulseScale = 1.05
            }
        case .running:
            withAnimation(.linear(duration: 2.0).repeatForever(autoreverses: false)) {
                rotation = 360
            }
            withAnimation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true)) {
                pulseScale = 1.08
            }
        default:
            withAnimation(.easeOut(duration: 0.3)) {
                rotation = 0
                pulseScale = 1.0
            }
        }
    }
}
