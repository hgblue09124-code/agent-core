// ios/AgentCoreIOS/UI/Design/AgentDesignTokens.swift
// Personal Agent UI Design Tokens — Native SwiftUI Implementation

import SwiftUI

// MARK: - Color Hex Extension

extension Color {
    init(hex: UInt32, opacity: Double = 1.0) {
        let red = Double((hex & 0xFF0000) >> 16) / 255.0
        let green = Double((hex & 0x00FF00) >> 8) / 255.0
        let blue = Double(hex & 0x0000FF) / 255.0
        self.init(.sRGB, red: red, green: green, blue: blue, opacity: opacity)
    }
}

// MARK: - AgentColor Tokens

enum AgentColor {
    static let background0 = Color(hex: 0x020203)
    static let background1 = Color(hex: 0x0A0A0D)
    static let background2 = Color(hex: 0x141417)
    static let background3 = Color(hex: 0x1D1D22)
    static let background4 = Color(hex: 0x26262C)

    static let hairline = Color.white.opacity(0.08)
    static let hairlineStrong = Color.white.opacity(0.14)

    static let textPrimary = Color(hex: 0xF5F5F7)
    static let textSecondary = Color(hex: 0xF5F5F7, opacity: 0.62)
    static let textMuted = Color(hex: 0xF5F5F7, opacity: 0.36)

    static let accent = Color(hex: 0x7C8CFF)
    static let accentDim = Color(hex: 0x7C8CFF, opacity: 0.14)

    static let violet = Color(hex: 0xB18CFF)
    static let cyan = Color(hex: 0x7FE0E0)

    static let success = Color(hex: 0x3DD68C)
    static let successDim = Color(hex: 0x3DD68C, opacity: 0.14)

    static let warning = Color(hex: 0xF5B84D)
    static let warningDim = Color(hex: 0xF5B84D, opacity: 0.14)

    static let danger = Color(hex: 0xF5716B)
    static let dangerDim = Color(hex: 0xF5716B, opacity: 0.14)

    static let offline = Color(hex: 0x8B8B92)
}

// MARK: - AgentFont Tokens

enum AgentFont {
    static let display = Font.system(size: 34, weight: .semibold, design: .default)
    static let h1 = Font.system(size: 26, weight: .semibold, design: .default)
    static let title = Font.system(size: 22, weight: .semibold, design: .default)
    static let headline = Font.system(size: 17, weight: .semibold, design: .default)
    static let subheadline = Font.system(size: 14.5, weight: .semibold, design: .default)
    static let body = Font.system(size: 15, weight: .medium, design: .default)
    static let secondary = Font.system(size: 13, weight: .regular, design: .default)
    static let caption = Font.system(size: 12, weight: .medium, design: .default)
    static let captionSmall = Font.system(size: 11, weight: .medium, design: .default)
    static let mono = Font.system(size: 12, weight: .regular, design: .monospaced)
}

// MARK: - AgentSpacing Tokens

enum AgentSpacing {
    static let xs: CGFloat = 4
    static let sm: CGFloat = 8
    static let md: CGFloat = 12
    static let lg: CGFloat = 16
    static let xl: CGFloat = 20
    static let xxl: CGFloat = 24
    static let xxxl: CGFloat = 32
}

// MARK: - AgentRadius Tokens

enum AgentRadius {
    static let small: CGFloat = 8
    static let tile: CGFloat = 12
    static let segmented: CGFloat = 14
    static let card: CGFloat = 20
    static let button: CGFloat = 24
    static let pill: CGFloat = 100
}

// MARK: - AgentBorder Tokens

enum AgentBorder {
    static let hairline: CGFloat = 1.0
    static let hairlineStrong: CGFloat = 1.0
}
