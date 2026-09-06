// ios/AgentCoreIOS/UI/Vault/VaultView.swift
// Personal Agent Vault View — Memory & Context Storage

import SwiftUI

public struct VaultView: View {
    @EnvironmentObject private var viewModel: AgentAppViewModel
    @State private var searchQuery: String = ""

    public init() {}

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: AgentSpacing.lg) {
                // Header & Private Chip
                HStack {
                    Text("Vault")
                        .font(AgentFont.h1)
                        .foregroundColor(AgentColor.textPrimary)

                    Spacer()

                    PrivacyChipView(label: "Private", isLocal: true)
                }

                // Search Memory Input Pill
                HStack(spacing: 10) {
                    Image(systemName: "magnifyingglass")
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(AgentColor.textMuted)

                    TextField("Search memory", text: $searchQuery)
                        .font(AgentFont.body)
                        .foregroundColor(AgentColor.textPrimary)
                        .accentColor(AgentColor.accent)

                    if !searchQuery.isEmpty {
                        Button(action: { searchQuery = "" }) {
                            Image(systemName: "xmark.circle.fill")
                                .font(.system(size: 16))
                                .foregroundColor(AgentColor.textMuted)
                        }
                    }
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(AgentColor.background2)
                .overlay(
                    RoundedRectangle(cornerRadius: AgentRadius.button)
                        .stroke(AgentColor.hairlineStrong, lineWidth: AgentBorder.hairlineStrong)
                )
                .clipShape(RoundedRectangle(cornerRadius: AgentRadius.button))

                // 2-Column Category Grid
                HStack(spacing: AgentSpacing.md) {
                    CategoryCard(
                        title: "Documents",
                        itemCount: documentsCount,
                        iconName: "folder.fill"
                    )

                    CategoryCard(
                        title: "Notes",
                        itemCount: notesCount,
                        iconName: "doc.fill"
                    )
                }

                // Remembered Context Card
                RememberedContextCard(summary: rememberedContextSummary)

                // Stored Memories List
                VStack(alignment: .leading, spacing: AgentSpacing.sm) {
                    Text("Stored Memories (\(filteredMemories.count))")
                        .font(AgentFont.caption)
                        .foregroundColor(AgentColor.textMuted)

                    VStack(alignment: .leading, spacing: 0) {
                        if filteredMemories.isEmpty {
                            Text("No memories found.")
                                .font(AgentFont.secondary)
                                .foregroundColor(AgentColor.textMuted)
                                .padding(AgentSpacing.lg)
                        } else {
                            ForEach(filteredMemories) { memory in
                                VStack(alignment: .leading, spacing: 4) {
                                    HStack {
                                        Text("[\(memory.key)]")
                                            .font(AgentFont.caption)
                                            .fontWeight(.bold)
                                            .foregroundColor(AgentColor.accent)

                                        Spacer()

                                        if memory.isEncrypted {
                                            Image(systemName: "lock.fill")
                                                .font(.system(size: 10))
                                                .foregroundColor(AgentColor.success)
                                        }
                                    }

                                    Text(memory.value)
                                        .font(AgentFont.body)
                                        .foregroundColor(AgentColor.textPrimary)
                                }
                                .padding(.vertical, 10)

                                if memory.id != filteredMemories.last?.id {
                                    Divider()
                                        .background(AgentColor.hairline)
                                }
                            }
                        }
                    }
                    .padding(.horizontal, AgentSpacing.md)
                    .padding(.vertical, AgentSpacing.xs)
                    .background(AgentColor.background2)
                    .overlay(
                        RoundedRectangle(cornerRadius: AgentRadius.card)
                            .stroke(AgentColor.hairline, lineWidth: AgentBorder.hairline)
                    )
                    .clipShape(RoundedRectangle(cornerRadius: AgentRadius.card))
                }
            }
            .padding(AgentSpacing.lg)
        }
        .background(AgentColor.background1.ignoresSafeArea())
        .onAppear {
            Task {
                await viewModel.loadVaultSummary()
            }
        }
    }

    private var filteredMemories: [MemoryItem] {
        if searchQuery.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return viewModel.memories
        }
        let q = searchQuery.lowercased()
        return viewModel.memories.filter {
            $0.key.lowercased().contains(q) || $0.value.lowercased().contains(q)
        }
    }

    private var documentsCount: Int {
        if let summary = viewModel.vaultSummary {
            return summary.categories.first(where: { $0.category == .documents })?.itemCount ?? 0
        }
        return viewModel.memories.filter { $0.key.contains("doc") || $0.key.contains("file") }.count
    }

    private var notesCount: Int {
        if let summary = viewModel.vaultSummary {
            return summary.categories.first(where: { $0.category == .userPreference || $0.category == .customContext })?.itemCount ?? viewModel.memories.count
        }
        return viewModel.memories.count
    }

    private var rememberedContextSummary: String {
        let prefs = viewModel.memories.map { "\($0.key): \($0.value)" }
        if prefs.isEmpty {
            return "No personal context saved yet."
        }
        return prefs.prefix(3).joined(separator: ", ")
    }
}
