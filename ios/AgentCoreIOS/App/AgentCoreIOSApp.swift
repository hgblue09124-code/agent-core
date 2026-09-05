// ios/AgentCoreIOS/App/AgentCoreIOSApp.swift
// SwiftUI Main Entry Point — Personal Agent Local

import SwiftUI

@main
struct AgentCoreIOSApp: App {
    var body: some Scene {
        WindowGroup {
            MainTabView()
        }
    }
}

public struct DiagnosticMainView: View {
    public init() {}
    public var body: some View {
        MainTabView()
    }
}
