// ios/AgentCoreIOS/UI/Components/ActivityRowView.swift
// Personal Agent Activity Row View Component

import SwiftUI

public struct ActivityRowView: View {
    public let record: ActivityRecord

    public init(record: ActivityRecord) {
        self.record = record
    }

    private var isSuccess: Bool {
        record.state == "COMPLETED" || record.state == "SUCCESS"
    }

    private var isFailed: Bool {
        record.state == "FAILED" || record.state == "DENIED"
    }

    private var tileBackgroundColor: Color {
        if isSuccess { return AgentColor.successDim }
        if isFailed { return AgentColor.dangerDim }
        return AgentColor.background3
    }

    private var tileForegroundColor: Color {
        if isSuccess { return AgentColor.success }
        if isFailed { return AgentColor.danger }
        return AgentColor.textSecondary
    }

    private var iconName: String {
        if isSuccess { return "checkmark" }
        if isFailed { return "xmark" }
        return "clock"
    }

    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: AgentRadius.tile)
                    .fill(tileBackgroundColor)
                    .frame(width: 32, height: 32)

                Image(systemName: iconName)
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(tileForegroundColor)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(record.task)
                    .font(AgentFont.body)
                    .foregroundColor(AgentColor.textPrimary)
                    .lineLimit(1)

                Text("\(record.timestamp) · \(record.duration) · \(record.resultOrError)")
                    .font(AgentFont.captionSmall)
                    .foregroundColor(AgentColor.textMuted)
                    .lineLimit(1)
            }

            Spacer()
        }
        .padding(.vertical, 8)
    }
}
