// ios/AgentCoreIOS/Views/MainTabView.swift
// 5-Tab Navigation Bar — Personal Agent iOS

import SwiftUI

public struct MainTabView: View {
    @StateObject private var viewModel = AgentAppViewModel()

    public init() {}

    public var body: some View {
        ZStack(alignment: .bottom) {
            // Main View Area
            Group {
                switch viewModel.selectedTab {
                case 0:
                    HomeView(viewModel: viewModel)
                case 1:
                    ExecuteView(viewModel: viewModel)
                case 2:
                    ActivityView(viewModel: viewModel)
                case 3:
                    VaultView(viewModel: viewModel)
                case 4:
                    ConnectionsView(viewModel: viewModel)
                case 5:
                    SettingsView(viewModel: viewModel)
                default:
                    HomeView(viewModel: viewModel)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            // Custom Tab Bar matching Claude Design Tokens
            HStack(spacing: 0) {
                TabButton(title: "Home", icon: "house.fill", index: 0, selectedIndex: $viewModel.selectedTab)
                TabButton(title: "Agent", icon: "bolt.fill", index: 1, selectedIndex: $viewModel.selectedTab)
                TabButton(title: "Activity", icon: "waveform.path.ecg", index: 2, selectedIndex: $viewModel.selectedTab)
                TabButton(title: "Vault", icon: "lock.square.stack.fill", index: 3, selectedIndex: $viewModel.selectedTab)
                TabButton(title: "Settings", icon: "gearshape.fill", index: 5, selectedIndex: $viewModel.selectedTab)
            }
            .padding(.top, 8)
            .padding(.bottom, 12)
            .background(AgentTheme.bg2.ignoresSafeArea(edges: .bottom))
            .overlay(
                Rectangle()
                    .frame(height: 1)
                    .foregroundColor(AgentTheme.hair),
                alignment: .top
            )
        }
        .preferredColorScheme(.dark)
    }
}

struct TabButton: View {
    let title: String
    let icon: String
    let index: Int
    @Binding var selectedIndex: Int

    var body: some View {
        Button(action: {
            withAnimation(.easeInOut(duration: 0.15)) {
                selectedIndex = index
            }
        }) {
            VStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.system(size: 18))
                    .foregroundColor(selectedIndex == index ? AgentTheme.accent : AgentTheme.text3)

                Text(title)
                    .font(.system(size: 10, weight: selectedIndex == index ? .semibold : .regular))
                    .foregroundColor(selectedIndex == index ? AgentTheme.text1 : AgentTheme.text3)
            }
            .frame(maxWidth: .infinity)
        }
    }
}
