// ios/AgentCoreIOS/Providers/RoutingLanguageModelProvider.swift
// Settings + router: on-device GGUF / Apple Intelligence / OpenAI / OpenRouter / xAI / Ollama / custom.

import Foundation
import Security

public enum LLMBackend: String, Codable, CaseIterable, Sendable, Identifiable {
    case onDevice = "on_device"
    case openai
    case openrouter
    case xai
    case ollama
    case custom
    case mock

    public var id: String { rawValue }

    public var displayName: String {
        switch self {
        case .onDevice: return "On-device"
        case .openai: return "OpenAI"
        case .openrouter: return "OpenRouter"
        case .xai: return "xAI"
        case .ollama: return "Ollama / llama.cpp"
        case .custom: return "Custom endpoint"
        case .mock: return "Mock (tests)"
        }
    }

    public var isRemoteCloud: Bool {
        switch self {
        case .openai, .openrouter, .xai, .custom: return true
        case .onDevice, .ollama, .mock: return false
        }
    }

    public var defaultModel: String {
        switch self {
        case .onDevice: return ModelCatalog.defaultModelId
        case .openai: return "gpt-4o-mini"
        case .openrouter: return "openai/gpt-4o-mini"
        case .xai: return "grok-3-mini"
        case .ollama: return "qwen2.5:0.5b"
        case .custom: return "local-model"
        case .mock: return "mock"
        }
    }

    public var defaultBaseURL: String {
        switch self {
        case .openai: return "https://api.openai.com/v1"
        case .openrouter: return "https://openrouter.ai/api/v1"
        case .xai: return "https://api.x.ai/v1"
        case .ollama: return "http://127.0.0.1:11434/v1"
        case .custom: return "http://127.0.0.1:8080/v1"
        case .onDevice, .mock: return ""
        }
    }
}

public struct LLMSettings: Codable, Equatable, Sendable {
    public var backend: LLMBackend
    public var onDeviceModelId: String
    public var remoteModel: String
    public var baseURL: String
    public var privacyMode: Bool

    public static let `default` = LLMSettings(
        backend: .onDevice,
        onDeviceModelId: ModelCatalog.defaultModelId,
        remoteModel: LLMBackend.onDevice.defaultModel,
        baseURL: "",
        privacyMode: true
    )
}

public final class LLMSettingsStore: @unchecked Sendable {
    public static let shared = LLMSettingsStore()
    private let defaults: UserDefaults
    private let key = "agentcore.llm.settings.v1"
    private let lock = NSLock()

    public init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    public func load() -> LLMSettings {
        lock.lock(); defer { lock.unlock() }
        guard let data = defaults.data(forKey: key),
              let decoded = try? JSONDecoder().decode(LLMSettings.self, from: data) else {
            return .default
        }
        return decoded
    }

    public func save(_ settings: LLMSettings) {
        lock.lock(); defer { lock.unlock() }
        if let data = try? JSONEncoder().encode(settings) {
            defaults.set(data, forKey: key)
        }
    }

    public func apiKey(for backend: LLMBackend) -> String {
        KeychainStore.get(account: "agentcore.llm.\(backend.rawValue)") ?? ""
    }

    public func setAPIKey(_ value: String, for backend: LLMBackend) {
        if value.isEmpty {
            KeychainStore.delete(account: "agentcore.llm.\(backend.rawValue)")
        } else {
            KeychainStore.set(value, account: "agentcore.llm.\(backend.rawValue)")
        }
    }
}

enum KeychainStore {
    static func set(_ value: String, account: String) {
        let data = Data(value.utf8)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "com.agentcore.AgentCoreIOS",
            kSecAttrAccount as String: account
        ]
        SecItemDelete(query as CFDictionary)
        var add = query
        add[kSecValueData as String] = data
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(add as CFDictionary, nil)
    }

    static func get(account: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "com.agentcore.AgentCoreIOS",
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var out: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &out)
        guard status == errSecSuccess, let data = out as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func delete(account: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "com.agentcore.AgentCoreIOS",
            kSecAttrAccount as String: account
        ]
        SecItemDelete(query as CFDictionary)
    }
}

/// Routes generate/stream to the selected backend. App injects this into AgentRuntime.
public final class RoutingLanguageModelProvider: LanguageModelProvider, @unchecked Sendable {
    public static let shared = RoutingLanguageModelProvider()

    public let providerId = "RoutingLanguageModelProvider"
    private let lock = NSLock()
    private var _isLoaded = false
    private let settingsStore: LLMSettingsStore
    private let downloads: ModelDownloadManager
    private let session: URLSession
    private var mock: MockLanguageModelProvider

    public var isLoaded: Bool {
        lock.lock(); defer { lock.unlock() }
        return _isLoaded
    }

    public var isRemote: Bool {
        let s = settingsStore.load()
        if s.privacyMode { return false }
        return s.backend.isRemoteCloud
    }

    public init(
        settingsStore: LLMSettingsStore = .shared,
        downloads: ModelDownloadManager? = nil,
        session: URLSession = .shared
    ) {
        self.settingsStore = settingsStore
        self.downloads = downloads ?? ModelDownloadManager.shared
        self.session = session
        self.mock = MockLanguageModelProvider(fixedResponseText: "Mock provider response.")
    }

    public func load() async throws {
        try Task.checkCancellation()
        let settings = settingsStore.load()
        if settings.backend == .onDevice {
            if let spec = ModelCatalog.spec(id: settings.onDeviceModelId),
               downloads.isInstalled(spec) {
                _ = try? downloads.inspect(spec)
            }
        }
        try await mock.load()
        lock.lock()
        _isLoaded = true
        lock.unlock()
    }

    public func unload() async {
        await mock.unload()
        lock.lock()
        _isLoaded = false
        lock.unlock()
    }

    public func generate(_ request: LanguageModelRequest) async throws -> LanguageModelResponse {
        try Task.checkCancellation()
        guard isLoaded else { throw LanguageModelError.notLoaded }
        let backend = try await resolveBackend()
        return try await backend.generate(request)
    }

    public func stream(_ request: LanguageModelRequest) -> AsyncThrowingStream<LanguageModelStreamChunk, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    try Task.checkCancellation()
                    guard self.isLoaded else {
                        continuation.finish(throwing: LanguageModelError.notLoaded)
                        return
                    }
                    let backend = try await self.resolveBackend()
                    for try await chunk in backend.stream(request) {
                        try Task.checkCancellation()
                        continuation.yield(chunk)
                    }
                    continuation.finish()
                } catch is CancellationError {
                    continuation.finish(throwing: LanguageModelError.cancelled)
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { @Sendable _ in task.cancel() }
        }
    }

    public func displayStatus() -> (name: String, status: String, localOnly: Bool) {
        let s = settingsStore.load()
        let localOnly = s.privacyMode || !s.backend.isRemoteCloud
        switch s.backend {
        case .onDevice:
            let spec = ModelCatalog.spec(id: s.onDeviceModelId)
            let installed = spec.map { downloads.isInstalled($0) } ?? false
            let name = spec.map { "On-device · \($0.displayName)" } ?? "On-device"
            return (name, installed ? "REAL_LOCAL_MODEL" : "WEIGHTS_NOT_LOADED", true)
        case .mock:
            return ("Mock", "DETERMINISTIC_TEST", true)
        default:
            let label = "\(s.backend.displayName) · \(s.remoteModel.isEmpty ? s.backend.defaultModel : s.remoteModel)"
            return (label, s.backend.isRemoteCloud ? "REMOTE_PROVIDER" : "LOCAL_SERVER", localOnly)
        }
    }

    private func resolveBackend() async throws -> LanguageModelProvider {
        let s = settingsStore.load()
        if s.privacyMode && s.backend.isRemoteCloud {
            throw LanguageModelError.providerUnavailable("Privacy mode blocks cloud providers. Switch backend to On-device or Ollama.")
        }
        switch s.backend {
        case .mock:
            if !mock.isLoaded { try await mock.load() }
            return mock
        case .onDevice:
            return try await makeOnDevice(settings: s)
        case .openai, .openrouter, .xai, .ollama, .custom:
            return try await makeRemote(settings: s)
        }
    }

    private func makeRemote(settings: LLMSettings) async throws -> OpenAICompatibleProvider {
        let backend = settings.backend
        let baseRaw = settings.baseURL.isEmpty ? backend.defaultBaseURL : settings.baseURL
        guard let url = URL(string: baseRaw) else {
            throw LanguageModelError.invalidRequest("Invalid base URL")
        }
        var headers: [String: String] = [:]
        if backend == .openrouter {
            headers["HTTP-Referer"] = "https://github.com/hgblue09124-code/agent-core"
            headers["X-Title"] = "Agent-Core iOS"
        }
        let key = settingsStore.apiKey(for: backend)
        if backend.isRemoteCloud && key.isEmpty {
            throw LanguageModelError.providerUnavailable("\(backend.displayName) API key is missing")
        }
        let model = settings.remoteModel.isEmpty ? backend.defaultModel : settings.remoteModel
        let provider = OpenAICompatibleProvider(
            config: OpenAICompatibleConfig(
                providerId: backend.rawValue,
                baseURL: url,
                apiKey: key,
                model: model,
                extraHeaders: headers
            ),
            session: session,
            isRemote: backend.isRemoteCloud
        )
        try await provider.load()
        return provider
    }

    private func makeOnDevice(settings: LLMSettings) async throws -> LanguageModelProvider {
        guard let spec = ModelCatalog.spec(id: settings.onDeviceModelId), downloads.isInstalled(spec) else {
            throw LanguageModelError.notLoaded
        }
        _ = try? downloads.inspect(spec)
        let host = settings.baseURL.isEmpty ? LLMBackend.ollama.defaultBaseURL : settings.baseURL
        guard let url = URL(string: host) else {
            throw LanguageModelError.providerUnavailable(
                "Downloaded \(spec.displayName). Start Ollama/llama.cpp locally or set a server URL in Settings."
            )
        }
        let provider = OpenAICompatibleProvider(
            config: OpenAICompatibleConfig(
                providerId: "on_device:\(spec.id)",
                baseURL: url,
                apiKey: settingsStore.apiKey(for: .ollama),
                model: spec.ollamaTag
            ),
            session: session,
            isRemote: false
        )
        try await provider.load()
        return provider
    }
}
