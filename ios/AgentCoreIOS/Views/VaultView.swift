// ios/AgentCoreIOS/Views/VaultView.swift
// Memory / Vault Screen — Personal Agent iOS

import SwiftUI

public struct VaultView: View {
    @ObservedObject public var viewModel: AgentAppViewModel

    public init(viewModel: AgentAppViewModel) {
        self.viewModel = viewModel
    }

    public var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // Header Bar
                HStack {
                    Text("Vault")
                        .font(.system(size: 20, weight: .bold))
                        .foregroundColor(AgentTheme.text1)

                    Spacer()

                    LocalIndicator(label: "Private", isShield: true)
                }
                .padding(.top, 8)

                // Search Bar
                HStack(spacing: 8) {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(AgentTheme.text3)
                    TextField("Search memory...", text: $viewModel.searchQuery)
                        .font(.system(size: 13))
                        .foregroundColor(AgentTheme.text1)
                        .onChange(of: viewModel.searchQuery) { _ in
                            Task { await viewModel.refreshData() }
                        }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(AgentTheme.bg3)
                .cornerRadius(AgentTheme.radiusM)

                // Vault Categories Grid
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                    ForEach(viewModel.vaultCategories) { cat in
                        VStack(alignment: .leading, spacing: 6) {
                            Image(systemName: cat.icon)
                                .font(.system(size: 16))
                                .foregroundColor(AgentTheme.text2)

                            Text(cat.name)
                                .font(.system(size: 13, weight: .medium))
                                .foregroundColor(AgentTheme.text1)

                            Text("\(cat.count) items")
                                .font(.system(size: 11))
                                .foregroundColor(AgentTheme.text3)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .agentCard(padding: 12)
                    }
                }

                // Context Remembered List Card
                VStack(alignment: .leading, spacing: 12) {
                    Text("REMEMBERED CONTEXT (\(viewModel.memories.count))")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(AgentTheme.text3)

                    if viewModel.memories.isEmpty {
                        Text("No memory items stored yet.")
                            .font(.system(size: 12))
                            .foregroundColor(AgentTheme.text3)
                            .padding(.vertical, 8)
                    } else {
                        VStack(spacing: 10) {
                            ForEach(viewModel.memories, id: \.key) { mem in
                                HStack {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(mem.key)
                                            .font(.system(size: 12.5, weight: .semibold))
                                            .foregroundColor(AgentTheme.text1)
                                        Text(mem.value)
                                            .font(.system(size: 11.5))
                                            .foregroundColor(AgentTheme.text2)
                                    }

                                    Spacer()

                                    Button(action: {
                                        Task { await viewModel.deleteMemory(key: mem.key) }
                                    }) {
                                        Image(systemName: "trash")
                                            .font(.system(size: 12))
                                            .foregroundColor(AgentTheme.text3)
                                    }
                                }

                                if mem.key != viewModel.memories.last?.key {
                                    Divider()
                                        .background(AgentTheme.hair)
                                }
                            }
                        }
                    }
                }
                .agentCard(padding: 14)
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .background(AgentTheme.bg1.ignoresSafeArea())
    }
}
