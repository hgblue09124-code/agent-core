// ios/AgentCoreIOS/Providers/LanguageModelProvider.swift
// Language Model Provider Abstraction — Step 1
// Clean contract for future tiny local LLM integration.
// AgentRuntime depends only on this protocol, never on concrete inference stacks.

import Foundation

// MARK: - Message Role

public enum LanguageModelRole: String, Codable, Sendable, Equatable {
    case system
    case user
    case assistant
}

// MARK: - Message

public struct LanguageModelMessage: Codable, Sendable, Equatable {
    public let role: LanguageModelRole
    public let content: String

    public init(role: LanguageModelRole, content: String) {
        self.role = role
        self.content = content
    }
}

// MARK: - Generation Parameters

public struct LanguageModelGenerationParameters: Codable, Sendable, Equatable {
    public var temperature: Double?
    public var maxTokens: Int?
    public var topP: Double?
    public var stopSequences: [String]?

    public init(
        temperature: Double? = nil,
        maxTokens: Int? = nil,
        topP: Double? = nil,
        stopSequences: [String]? = nil
    ) {
        self.temperature = temperature
        self.maxTokens = maxTokens
        self.topP = topP
        self.stopSequences = stopSequences
    }

    public static let `default` = LanguageModelGenerationParameters()
}

// MARK: - Request

public struct LanguageModelRequest: Codable, Sendable, Equatable {
    /// Optional system prompt. Prefer this over embedding a system message when the provider supports it.
    public var systemPrompt: String?
    public var messages: [LanguageModelMessage]
    public var parameters: LanguageModelGenerationParameters

    public init(
        systemPrompt: String? = nil,
        messages: [LanguageModelMessage],
        parameters: LanguageModelGenerationParameters = .default
    ) {
        self.systemPrompt = systemPrompt
        self.messages = messages
        self.parameters = parameters
    }
}

// MARK: - Response

public struct LanguageModelResponse: Codable, Sendable, Equatable {
    public let text: String
    public let finishReason: String?
    public let metadata: [String: String]

    public init(
        text: String,
        finishReason: String? = nil,
        metadata: [String: String] = [:]
    ) {
        self.text = text
        self.finishReason = finishReason
        self.metadata = metadata
    }
}

// MARK: - Stream Chunk

public struct LanguageModelStreamChunk: Codable, Sendable, Equatable {
    public let text: String
    public let isFinal: Bool
    public let metadata: [String: String]

    public init(
        text: String,
        isFinal: Bool = false,
        metadata: [String: String] = [:]
    ) {
        self.text = text
        self.isFinal = isFinal
        self.metadata = metadata
    }
}

// MARK: - Errors

public enum LanguageModelError: Error, Sendable, Equatable {
    case notLoaded
    case alreadyLoaded
    case cancelled
    case generationFailed(String)
    case invalidRequest(String)
    case providerUnavailable(String)
    case downloadFailed(String)
    case invalidModelFile(String)
}

extension LanguageModelError: LocalizedError {
    public var errorDescription: String? {
        switch self {
        case .notLoaded:
            return "Language model provider is not loaded. Call load() first."
        case .alreadyLoaded:
            return "Language model provider is already loaded."
        case .cancelled:
            return "Language model generation was cancelled."
        case .generationFailed(let message):
            return "Language model generation failed: \(message)"
        case .invalidRequest(let message):
            return "Invalid language model request: \(message)"
        case .providerUnavailable(let message):
            return "Language model provider unavailable: \(message)"
        case .downloadFailed(let message):
            return "Model download failed: \(message)"
        case .invalidModelFile(let message):
            return "Invalid model file: \(message)"
        }
    }
}

// MARK: - Provider Protocol

/// Abstraction over any language-model backend (mock, tiny local LLM, etc.).
/// AgentRuntime depends only on this protocol.
public protocol LanguageModelProvider: Sendable {
    /// Human-readable identifier (for diagnostics). Must not hard-code concrete model names into runtime contracts.
    var providerId: String { get }

    /// Whether the underlying model resources are currently loaded.
    var isLoaded: Bool { get }

    /// Cloud/network provider vs on-device or local server.
    var isRemote: Bool { get }

    /// Load model resources. Idempotent implementations may treat a second load as a no-op or throw `.alreadyLoaded`.
    func load() async throws

    /// Unload model resources and free memory. Safe to call when already unloaded.
    func unload() async

    /// One-shot generation.
    func generate(_ request: LanguageModelRequest) async throws -> LanguageModelResponse

    /// Streaming generation. Callers must respect Task cancellation; providers should stop promptly when cancelled.
    func stream(_ request: LanguageModelRequest) -> AsyncThrowingStream<LanguageModelStreamChunk, Error>
}

extension LanguageModelProvider {
    public var isRemote: Bool { false }
}
