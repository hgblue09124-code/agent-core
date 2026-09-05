// ios/AgentCoreIOS/DesignSystem/CustomComponents.swift
// Reusable Design System UI Components — Personal Agent iOS

import SwiftUI

// Pill Composer Input
public struct PillComposerInput: View {
    @Binding public var text: String
    public var placeholder: String = "Ask your personal agent..."
    public var state: AgentState = .idle
    public var onSubmit: () -> Void

    public init(text: Binding<String>, placeholder: String = "Ask your personal agent...", state: AgentState = .idle, onSubmit: @escaping () -> Void) {
        self._text = text
        self.placeholder = placeholder
        self.state = state
        self.onSubmit = onSubmit
    }

    public var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "sparkles")
                .foregroundColor(AgentTheme.accent)
                .font(.system(size: 16))

            TextField(placeholder, text: $text)
                .font(.system(size: 14))
                .foregroundColor(AgentTheme.text1)
                .disabled(state == .running || state == .thinking)

            Button(action: onSubmit) {
                ZStack {
                    Circle()
                        .fill(text.isEmpty ? AgentTheme.bg4 : AgentTheme.accent)
                        .frame(width: 32, height: 32)

                    Image(systemName: "arrow.up")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(text.isEmpty ? AgentTheme.text3 : AgentTheme.bg0)
                }
            }
            .disabled(text.isEmpty || state == .running || state == .thinking)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(AgentTheme.bg3)
        .cornerRadius(AgentTheme.radiusPill)
        .overlay(
            RoundedRectangle(cornerRadius: AgentTheme.radiusPill)
                .stroke(AgentTheme.hairStrong, lineWidth: 1)
        )
    }
}

// Segmented Control
public struct AgentSegmentedControl: View {
    public let options: [String]
    @Binding public var selected: String

    public init(options: [String], selected: Binding<String>) {
        self.options = options
        self._selected = selected
    }

    public var body: some View {
        HStack(spacing: 4) {
            ForEach(options, id: \.self) { opt in
                Button(action: {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        selected = opt
                    }
                }) {
                    Text(opt)
                        .font(.system(size: 12.5, weight: .medium))
                        .foregroundColor(selected == opt ? AgentTheme.text1 : AgentTheme.text2)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 7)
                        .background(selected == opt ? AgentTheme.bg4 : Color.clear)
                        .cornerRadius(AgentTheme.radiusS)
                }
            }
        }
        .padding(3)
        .background(AgentTheme.bg2)
        .cornerRadius(AgentTheme.radiusM)
        .overlay(
            RoundedRectangle(cornerRadius: AgentTheme.radiusM)
                .stroke(AgentTheme.hair, lineWidth: 1)
        )
    }
}

// List Row
public struct AgentListRow: View {
    public let title: String
    public var subtitle: String? = nil
    public var icon: String
    public var iconColor: Color = AgentTheme.text2
    public var tileBackground: Color = AgentTheme.bg3
    public var rightText: String? = nil
    public var rightBadge: AnyView? = nil
    public var showChevron: Bool = false

    public init(
        title: String,
        subtitle: String? = nil,
        icon: String,
        iconColor: Color = AgentTheme.text2,
        tileBackground: Color = AgentTheme.bg3,
        rightText: String? = nil,
        rightBadge: AnyView? = nil,
        showChevron: Bool = false
    ) {
        self.title = title
        self.subtitle = subtitle
        self.icon = icon
        self.iconColor = iconColor
        self.tileBackground = tileBackground
        self.rightText = rightText
        self.rightBadge = rightBadge
        self.showChevron = showChevron
    }

    public var body: some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: AgentTheme.radiusS)
                    .fill(tileBackground)
                    .frame(width: 32, height: 32)

                Image(systemName: icon)
                    .font(.system(size: 14))
                    .foregroundColor(iconColor)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(AgentTheme.text1)

                if let sub = subtitle {
                    Text(subtitleText(sub))
                        .font(.system(size: 11))
                        .foregroundColor(AgentTheme.text3)
                }
            }

            Spacer()

            if let badge = rightBadge {
                badge
            } else if let rt = rightText {
                Text(rt)
                    .font(.system(size: 12))
                    .foregroundColor(AgentTheme.text3)
            }

            if showChevron {
                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundColor(AgentTheme.text3)
            }
        }
        .padding(.vertical, 4)
    }

    private func subtitleText(_ text: String) -> String {
        return text
    }
}

// Progress Bar
public struct AgentProgressBar: View {
    public var progress: Double // 0.0 to 1.0

    public init(progress: Double) {
        self.progress = progress
    }

    public var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: AgentTheme.radiusPill)
                    .fill(AgentTheme.bg4)
                    .frame(height: 4)

                RoundedRectangle(cornerRadius: AgentTheme.radiusPill)
                    .fill(AgentTheme.accent)
                    .frame(width: max(0, min(geo.size.width * CGFloat(progress), geo.size.width)), height: 4)
            }
        }
        .frame(height: 4)
    }
}

// Custom Toggle
public struct AgentToggle: View {
    public let title: String
    @Binding public var isOn: Bool

    public init(title: String, isOn: Binding<Bool>) {
        self.title = title
        self._isOn = isOn
    }

    public var body: some View {
        HStack {
            Text(title)
                .font(.system(size: 13, weight: .medium))
                .foregroundColor(AgentTheme.text1)

            Spacer()

            Toggle("", isOn: $isOn)
                .labelsHidden()
                .tint(AgentTheme.accent)
        }
        .padding(.vertical, 2)
    }
}
