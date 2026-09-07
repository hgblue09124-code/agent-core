// ios/AgentCoreIOS/UI/Home/WorkspacePresentation.swift
// iOS-boundary adapter: existing AgentRuntimeState / AgentRunResult → User Workspace view-model.
// Does not own Runtime, events, or storage.

import Foundation

enum WorkspacePresence: String, Equatable {
    case idle
    case thinking
    case toolStarted = "tool_started"
    case toolProgress = "tool_progress"
    case toolCompleted = "tool_completed"
    case resultReady = "result_ready"
    case error
}

struct WorkspaceMessage: Identifiable, Equatable {
    enum Role: Equatable {
        case user
        case agent
    }

    let id: UUID
    let role: Role
    let text: String
    let kicker: String?

    init(id: UUID = UUID(), role: Role, text: String, kicker: String? = nil) {
        self.id = id
        self.role = role
        self.text = text
        self.kicker = kicker
    }
}

struct WorkspaceSnapshot: Equatable {
    var presence: WorkspacePresence
    var activityHeadline: String
    var goal: String
    var progress: Double
    var steps: [ExecutionStepInfo]
    var showsProgress: Bool
    var resultPresent: Bool
    var resultOK: Bool
    var resultHeadline: String
    var resultBody: String
    var canRetry: Bool
    var canCancel: Bool
    var isWorking: Bool
    var agentReply: WorkspaceMessage?
}

enum WorkspacePresentation {
    static func presence(for state: AgentRuntimeState) -> WorkspacePresence {
        switch state.phase {
        case .idle:
            return .idle
        case .thinking, .planning:
            return .thinking
        case .executing:
            let completed = state.steps.filter { $0.status == .completed }.count
            if state.steps.isEmpty || completed == 0 {
                return .toolStarted
            }
            if completed >= state.steps.count && !state.steps.isEmpty {
                return .toolCompleted
            }
            return .toolProgress
        case .completed:
            return .resultReady
        case .failed, .cancelled:
            return .error
        }
    }

    static func map(state: AgentRuntimeState, lastResult: AgentRunResult?) -> WorkspaceSnapshot {
        let presence = presence(for: state)
        let isWorking = state.phase == .thinking || state.phase == .planning || state.phase == .executing
        let activeTitle = state.steps.first(where: { $0.status == .active })?.title

        let activity: String
        switch presence {
        case .idle:
            activity = "Ready for a task"
        case .thinking:
            activity = "Thinking…"
        case .toolStarted:
            activity = activeTitle ?? "Starting work…"
        case .toolProgress:
            activity = activeTitle ?? "Working…"
        case .toolCompleted:
            activity = "Finishing…"
        case .resultReady:
            activity = "Done"
        case .error:
            activity = state.error ?? lastResult?.errorMessage ?? "Something went wrong"
        }

        let resultOK = state.phase == .completed && (lastResult == nil || lastResult?.status == .success)
        let resultPresent = !isWorking && (state.phase == .completed || state.phase == .failed || state.phase == .cancelled)
        let resultHeadline: String
        let resultBody: String
        if state.phase == .failed || state.phase == .cancelled || lastResult?.status == .failed || lastResult?.status == .denied {
            resultHeadline = "Couldn't finish"
            resultBody = state.error ?? lastResult?.errorMessage ?? "The agent hit a problem."
        } else {
            resultHeadline = "Result"
            resultBody = lastResult?.output ?? "Task finished."
        }

        var reply: WorkspaceMessage?
        if resultPresent {
            let kicker = (resultOK && state.phase == .completed) ? "Result" : "Error"
            reply = WorkspaceMessage(role: .agent, text: resultBody, kicker: kicker)
        }

        let showsProgress = isWorking && (state.progress > 0 || !state.steps.isEmpty)

        return WorkspaceSnapshot(
            presence: presence,
            activityHeadline: activity,
            goal: state.currentGoal,
            progress: state.progress,
            steps: state.steps,
            showsProgress: showsProgress,
            resultPresent: resultPresent && !state.currentGoal.isEmpty,
            resultOK: resultOK,
            resultHeadline: resultHeadline,
            resultBody: resultBody,
            canRetry: (state.phase == .failed || state.phase == .cancelled) && !state.currentGoal.isEmpty,
            canCancel: isWorking,
            isWorking: isWorking,
            agentReply: reply
        )
    }
}
