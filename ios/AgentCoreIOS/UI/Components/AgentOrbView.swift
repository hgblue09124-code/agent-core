// ios/AgentCoreIOS/UI/Components/AgentOrbView.swift
// Personal Agent Ambient Orb View

import SwiftUI

public struct AgentOrbView: View {
    public enum OrbSize {
        case default118
        case mini14
        case custom(CGFloat)

        public var dimension: CGFloat {
            switch self {
            case .default118: return 118
            case .mini14: return 14
            case .custom(let val): return val
            }
        }

        public var coreSize: CGFloat {
            switch self {
            case .default118: return 14
            case .mini14: return 3
            case .custom(let val): return max(3, val * 0.12)
            }
        }
    }

    public let status: AgentStatus
    public let size: OrbSize
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var isSpinning: Bool = false

    public init(status: AgentStatus = .ready, size: OrbSize = .default118) {
        self.status = status
        self.size = size
    }

    private var conicGradient: AngularGradient {
        AngularGradient(
            gradient: Gradient(colors: [
                Color(hex: 0x4B5BE0),
                AgentColor.accent,
                AgentColor.violet,
                AgentColor.cyan,
                Color(hex: 0x4B5BE0)
            ]),
            center: .center
        )
    }

    private var shouldAnimate: Bool {
        (status == .thinking || status == .running) && !reduceMotion
    }

    var body: some View {
        ZStack {
            // Conic Gradient Orb Circle
            Circle()
                .fill(conicGradient)
                .frame(width: size.dimension, height: size.dimension)
                .rotationEffect(.degrees(isSpinning ? 360 : 0))
                .animation(
                    shouldAnimate ? Animation.linear(duration: 5.0).repeatForever(autoreverses: false) : .default,
                    value: isSpinning
                )

            // Inner dark mask for ring effect
            Circle()
                .fill(AgentColor.background1)
                .opacity(0.86)
                .frame(width: max(0, size.dimension - (size.dimension * 0.10)), height: max(0, size.dimension - (size.dimension * 0.10)))

            // Glowing Core Dot
            Circle()
                .fill(AgentColor.textPrimary)
                .frame(width: size.coreSize, height: size.coreSize)
                .shadow(color: AgentColor.accent.opacity(0.6), radius: size.dimension * 0.15)
        }
        .onAppear {
            if shouldAnimate {
                isSpinning = true
            }
        }
        .onChange(of: status) { newStatus in
            if (newStatus == .thinking || newStatus == .running) && !reduceMotion {
                isSpinning = true
            } else {
                isSpinning = false
            }
        }
        .accessibilityLabel("Agent Status: \(status.rawValue)")
    }
}
