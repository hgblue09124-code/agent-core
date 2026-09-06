// ios/AgentCoreIOS/UI/Components/InputPillView.swift
// Personal Agent Input Pill Composer Component

import SwiftUI

struct InputPillView: View {
    @Binding var text: String
    let placeholder: String
    let onSubmit: () -> Void

    init(
        text: Binding<String>,
        placeholder: String = "Ask your agent to do something…",
        onSubmit: @escaping () -> Void
    ) {
        self._text = text
        self.placeholder = placeholder
        self.onSubmit = onSubmit
    }

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "mic.fill")
                .font(.system(size: 16, weight: .medium))
                .foregroundColor(AgentColor.textMuted)

            TextField(placeholder, text: $text)
                .font(AgentFont.body)
                .foregroundColor(AgentColor.textPrimary)
                .accentColor(AgentColor.accent)
                .onSubmit {
                    if !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        onSubmit()
                    }
                }

            Button(action: {
                if !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    onSubmit()
                }
            }) {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 22, weight: .semibold))
                    .foregroundColor(
                        text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                        ? AgentColor.textMuted
                        : AgentColor.accent
                    )
            }
            .disabled(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 13)
        .frame(height: 52)
        .background(AgentColor.background2)
        .overlay(
            RoundedRectangle(cornerRadius: AgentRadius.button)
                .stroke(AgentColor.hairlineStrong, lineWidth: AgentBorder.hairlineStrong)
        )
        .clipShape(RoundedRectangle(cornerRadius: AgentRadius.button))
    }
}
