// ios/AgentCoreIOS/UI/Components/ConnectionRowView.swift
// Personal Agent Connection Row View Component

import SwiftUI

struct ConnectionRowView: View {
    let connection: ConnectionStatus

    init(connection: ConnectionStatus, onToggle: (() -> Void)? = nil) {
        self.connection = connection
    }

    private var iconName: String {
        switch connection.kind {
        case .local: return "cpu"
        case .remote: return "network"
        }
    }

    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: AgentRadius.tile)
                    .fill(connection.kind == .local ? AgentColor.successDim : AgentColor.background3)
                    .frame(width: 32, height: 32)

                Image(systemName: iconName)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(connection.kind == .local ? AgentColor.success : AgentColor.textSecondary)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(connection.name)
                    .font(AgentFont.body)
                    .foregroundColor(AgentColor.textPrimary)

                Text(subtext)
                    .font(AgentFont.captionSmall)
                    .foregroundColor(AgentColor.textMuted)
            }

            Spacer()

            if connection.kind == .local {
                PrivacyChipView(label: "Local", isLocal: true)
            } else {
                if connection.state == .remoteConfigured {
                    PrivacyChipView(label: "Remote", isLocal: false)
                } else {
                    Text("Not configured")
                        .font(AgentFont.captionSmall)
                        .fontWeight(.medium)
                        .foregroundColor(AgentColor.textMuted)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(AgentColor.background3)
                        .cornerRadius(6)
                }
            }
        }
        .padding(.vertical, 8)
    }

    private var subtext: String {
        switch connection.kind {
        case .local:
            return "On-device · always available"
        case .remote:
            switch connection.state {
            case .localActive:
                return "On-device · active"
            case .remoteConfigured:
                return "Connected · remote"
            case .remoteNotConfigured:
                return "Not configured · requires GITHUB_TOKEN"
            }
        }
    }
}
