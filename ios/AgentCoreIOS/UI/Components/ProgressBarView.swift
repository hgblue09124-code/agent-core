// ios/AgentCoreIOS/UI/Components/ProgressBarView.swift
// Personal Agent Progress Bar Component

import SwiftUI

public struct ProgressBarView: View {
    public let progress: Double // 0.0 to 1.0
    public let fillColor: Color

    public init(progress: Double, fillColor: Color = AgentColor.accent) {
        self.progress = max(0.0, min(1.0, progress))
        self.fillColor = fillColor
    }

    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 4)
                    .fill(AgentColor.background4)
                    .frame(height: 4)

                RoundedRectangle(cornerRadius: 4)
                    .fill(fillColor)
                    .frame(width: geometry.size.width * CGFloat(progress), height: 4)
            }
        }
        .frame(height: 4)
    }
}
