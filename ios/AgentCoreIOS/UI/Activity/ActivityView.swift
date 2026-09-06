// ios/AgentCoreIOS/UI/Activity/ActivityView.swift
// Personal Agent Activity View — Filterable Timeline of Runs

import SwiftUI

struct ActivityView: View {
    @EnvironmentObject private var viewModel: AgentAppViewModel
    @State private var selectedFilter: ActivityFilter = .all

    init() {}

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: AgentSpacing.lg) {
                // Header
                Text("Activity")
                    .font(AgentFont.h1)
                    .foregroundColor(AgentColor.textPrimary)

                // Segmented Filter Control (All / Success / Failed)
                HStack(spacing: 3) {
                    filterButton(title: "All", filter: .all)
                    filterButton(title: "Success", filter: .success)
                    filterButton(title: "Failed", filter: .failed)
                }
                .padding(3)
                .background(AgentColor.background2)
                .overlay(
                    RoundedRectangle(cornerRadius: AgentRadius.segmented)
                        .stroke(AgentColor.hairline, lineWidth: AgentBorder.hairline)
                )
                .clipShape(RoundedRectangle(cornerRadius: AgentRadius.segmented))

                // Activity List Container Card
                VStack(spacing: 0) {
                    if filteredActivities.isEmpty {
                        VStack(spacing: 8) {
                            Image(systemName: "clock")
                                .font(.system(size: 24))
                                .foregroundColor(AgentColor.textMuted)

                            Text("No activity recorded for this filter.")
                                .font(AgentFont.secondary)
                                .foregroundColor(AgentColor.textMuted)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(AgentSpacing.xxl)
                    } else {
                        ForEach(filteredActivities) { record in
                            ActivityRowView(record: record)

                            if record.id != filteredActivities.last?.id {
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
            .padding(AgentSpacing.lg)
        }
        .background(AgentColor.background1.ignoresSafeArea())
        .onChange(of: selectedFilter) { _, newFilter in
            Task {
                await viewModel.loadActivity(filter: newFilter)
            }
        }
    }

    @ViewBuilder
    private func filterButton(title: String, filter: ActivityFilter) -> some View {
        Button(action: {
            selectedFilter = filter
        }) {
            Text(title)
                .font(AgentFont.caption)
                .fontWeight(.medium)
                .foregroundColor(selectedFilter == filter ? AgentColor.textPrimary : AgentColor.textMuted)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
                .background(selectedFilter == filter ? AgentColor.background4 : Color.clear)
                .clipShape(RoundedRectangle(cornerRadius: AgentRadius.tile))
        }
    }

    private var filteredActivities: [ActivityRecord] {
        viewModel.activities
    }
}
