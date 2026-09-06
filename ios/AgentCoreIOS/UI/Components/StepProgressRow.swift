// ios/AgentCoreIOS/UI/Components/StepProgressRow.swift
// Personal Agent Execution Step Progress Row

import SwiftUI

enum ExecutionStepStatus {
    case completed
    case active
    case pending
    case failed
}

struct StepProgressRow: View {
    let title: String
    let status: ExecutionStepStatus

    init(title: String, status: ExecutionStepStatus) {
        self.title = title
        self.status = status
    }

    var body: some View {
        HStack(spacing: 10) {
            switch status {
            case .completed:
                Image(systemName: "checkmark")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(AgentColor.success)
                    .frame(width: 14, height: 14)
            case .active:
                AgentOrbView(status: .thinking, size: .mini14)
            case .pending:
                Circle()
                    .fill(AgentColor.textMuted)
                    .frame(width: 6, height: 6)
                    .frame(width: 14, height: 14)
            case .failed:
                Image(systemName: "xmark")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(AgentColor.danger)
                    .frame(width: 14, height: 14)
            }

            Text(title)
                .font(status == .active ? AgentFont.body : AgentFont.secondary)
                .foregroundColor(status == .active ? AgentColor.textPrimary : AgentColor.textSecondary)

            Spacer()
        }
        .padding(.vertical, 4)
    }
}
