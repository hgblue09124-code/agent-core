// ios/AgentCoreIOS/UI/Design/AgentDesignTokens.swift
// Personal Agent UI Design Tokens — Native SwiftUI Implementation

import SwiftUI

// MARK: - Color Hex Extension

extension Color {
    public init(hex: UInt32, opacity: Double = 1.0) {
        let red = Double((hex & 0xFF0000) >> 16) / 255.0
        let green = Double((hex & 0x00FF00) >> 8) / 255.0
        let blue = Double(hex & 0x0000FF) / 255.0
        self.init(.sRGB, red: red, green: green, blue: blue, opacity: opacity)
    }
}

// MARK: - AgentColor Tokens

public enum AgentColor {
    public static let background0 = Color(hex: 0x020203)
    public static let background1 = Color(hex: 0x0A0A0D)
    public static let background2 = Color(hex: 0x141417)
    public static let background3 = Color(hex: 0x1D1D22)
    public static let background4 = Color(hex: 0x26262C)

    public static let hairline = Color.white.opacity(0.08)
    public static let hairlineStrong = Color.white.opacity(0.14)

    public static let textPrimary = Color(hex: 0xF5F5F7)
    public static let textSecondary = Color(hex: 0xF5F5F7, opacity: 0.62)
    public static let textMuted = Color(hex: 0xF5F5F7, opacity: 0.36)

    public static let accent = Color(hex: 0x7C8CFF)
    public static let accentDim = Color(hex: 0x7C8CFF, opacity: 0.14)

    public static let violet = Color(hex: 0xB18CFF)
    public static let cyan = Color(hex: 0x7FE0E0)

    public static let success = Color(hex: 0x3DD68C)
    public static let successDim = Color(hex: 0x3DD68C, opacity: 0.14)

    public static let warning = Color(hex: 0xF5B84D)
    public static let warningDim = Color(hex: 0xF5B84D, opacity: 0.14)

    public static let danger = Color(hex: 0xF5716B)
    public static let dangerDim = Color(hex: 0xF5716B, opacity: 0.14)

    public static let offline = Color(hex: 0x8B8B92)
}

// MARK: - AgentFont Tokens

public enum AgentFont {
    public static let display = Font.system(size: 34, weight: .semibold, design: .default)
    public static let h1 = Font.system(size: 26, weight: .semibold, design: .default)
    public static let title = Font.system(size: 22, weight: .semibold, design: .default)
    public static let headline = Font.system(size: 17, weight: .semibold, design: .default)
    public static let subheadline = Font.system(size: 14.5, weight: .semibold, design: .default)
    public static let body = Font.system(size: 15, weight: .medium, design: .default)
    public static let secondary = Font.system(size: 13, weight: .regular, design: .default)
    public static let caption = Font.system(size: 12, weight: .medium, design: .default)
    public static let captionSmall = Font.system(size: 11, weight: .medium, design: .default)
    public static let mono = Font.system(size: 12, weight: .regular, design: .monospaced)
}

// MARK: - AgentSpacing Tokens

public enum AgentSpacing {
    public static let xs: CGFloat = 4
    public static let sm: CGFloat = 8
    public static let md: CGFloat = 12
    public static let lg: CGFloat = 16
    public static let xl: CGFloat = 20
    public static let xxl: CGFloat = 24
    public static let xxxl: CGFloat = 32
}

// MARK: - AgentRadius Tokens

public enum AgentRadius {
    public static let small: CGFloat = 8
    public static let tile: CGFloat = 12
    public static let segmented: CGFloat = 14
    public static let card: CGFloat = 20
    public static let button: CGFloat = 24
    public static let pill: CGFloat = 100
}

// MARK: - AgentBorder Tokens

public enum AgentBorder {
    public static let hairline: CGFloat = 1.0
    public static let hairlineStrong: CGFloat = 1.0
}
