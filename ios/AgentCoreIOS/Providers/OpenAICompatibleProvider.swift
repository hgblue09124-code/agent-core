// ios/AgentCoreIOS/Providers/OpenAICompatibleProvider.swift
// OpenAI-compatible Chat Completions (OpenAI, OpenRouter, xAI, Ollama, llama-server).

import Foundation

public struct OpenAICompatibleConfig: Sendable, Equatable {
    public var providerId: String
    public var baseURL: URL
    public var apiKey: String
    public var model: String
    public var extraHeaders: [String: String]

    public init(
        providerId: String,
        baseURL: URL,
        apiKey: String = "",
        model: String,
        extraHeaders: [String: String] = [:]
    ) {
        self.providerId = providerId
        self.baseURL = baseURL
        self.apiKey = apiKey
        self.model = model
        self.extraHeaders = extraHeaders
    }
}

public final class OpenAICompatibleProvider: LanguageModelProvider, @unchecked Sendable {
    public let providerId: String
    public var isRemote: Bool

    private let lock = NSLock()
    private var _isLoaded = false
    private var config: OpenAICompatibleConfig
    private let session: URLSession

    public var isLoaded: Bool {
        lock.lock(); defer { lock.unlock() }
        return _isLoaded
    }

    public init(config: OpenAICompatibleConfig, session: URLSession = .shared, isRemote: Bool = true) {
        self.config = config
        self.providerId = config.providerId
        self.session = session
        self.isRemote = isRemote
    }

    public func updateConfig(_ config: OpenAICompatibleConfig) {
        lock.lock()
        self.config = config
        lock.unlock()
    }

    public func load() async throws {
        try Task.checkCancellation()
        lock.lock()
        _isLoaded = true
        lock.unlock()
    }

    public func unload() async {
        lock.lock()
        _isLoaded = false
        lock.unlock()
    }

    public func generate(_ request: LanguageModelRequest) async throws -> LanguageModelResponse {
        try Task.checkCancellation()
        guard isLoaded else { throw LanguageModelError.notLoaded }
        try validate(request)
        let cfg = currentConfig()
        let body = try encodeBody(request: request, cfg: cfg, stream: false)
        var urlRequest = try makeURLRequest(cfg: cfg, stream: false)
        urlRequest.httpBody = body

        let (data, response) = try await session.data(for: urlRequest)
        try Task.checkCancellation()
        try throwIfHTTPError(response, data: data)

        let decoded = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let text = Self.extractText(decoded) ?? ""
        let finish = Self.extractFinish(decoded) ?? "stop"
        return LanguageModelResponse(
            text: text,
            finishReason: finish,
            metadata: [
                "provider": providerId,
                "model": cfg.model,
                "remote": isRemote ? "true" : "false"
            ]
        )
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
                    try self.validate(request)
                    let cfg = self.currentConfig()
                    let body = try self.encodeBody(request: request, cfg: cfg, stream: true)
                    var urlRequest = try self.makeURLRequest(cfg: cfg, stream: true)
                    urlRequest.httpBody = body

                    let (bytes, response) = try await self.session.bytes(for: urlRequest)
                    if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
                        throw LanguageModelError.generationFailed("HTTP \(http.statusCode)")
                    }

                    var index = 0
                    for try await line in bytes.lines {
                        try Task.checkCancellation()
                        let trimmed = line.trimmingCharacters(in: .whitespaces)
                        if trimmed.isEmpty { continue }
                        if trimmed.hasPrefix("data:") {
                            let payload = trimmed.dropFirst(5).trimmingCharacters(in: .whitespaces)
                            if payload == "[DONE]" {
                                continuation.yield(LanguageModelStreamChunk(
                                    text: "",
                                    isFinal: true,
                                    metadata: ["provider": self.providerId, "index": "\(index)"]
                                ))
                                continuation.finish()
                                return
                            }
                            if let data = payload.data(using: .utf8),
                               let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                               let piece = Self.extractDelta(obj), !piece.isEmpty {
                                continuation.yield(LanguageModelStreamChunk(
                                    text: piece,
                                    isFinal: false,
                                    metadata: ["provider": self.providerId, "index": "\(index)"]
                                ))
                                index += 1
                            }
                        }
                    }
                    continuation.yield(LanguageModelStreamChunk(
                        text: "",
                        isFinal: true,
                        metadata: ["provider": self.providerId, "index": "\(index)"]
                    ))
                    continuation.finish()
                } catch is CancellationError {
                    continuation.finish(throwing: LanguageModelError.cancelled)
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { @Sendable _ in
                task.cancel()
            }
        }
    }

    private func currentConfig() -> OpenAICompatibleConfig {
        lock.lock(); defer { lock.unlock() }
        return config
    }

    private func validate(_ request: LanguageModelRequest) throws {
        if request.messages.isEmpty && (request.systemPrompt == nil || request.systemPrompt?.isEmpty == true) {
            throw LanguageModelError.invalidRequest("Request must contain at least one message or a system prompt")
        }
    }

    private func makeURLRequest(cfg: OpenAICompatibleConfig, stream: Bool) throws -> URLRequest {
        let url = cfg.baseURL.appendingPathComponent("chat/completions")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("Agent-Core-iOS/0.2.0", forHTTPHeaderField: "User-Agent")
        if stream {
            req.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        }
        if !cfg.apiKey.isEmpty {
            req.setValue("Bearer \(cfg.apiKey)", forHTTPHeaderField: "Authorization")
        }
        for (k, v) in cfg.extraHeaders {
            req.setValue(v, forHTTPHeaderField: k)
        }
        req.timeoutInterval = 120
        return req
    }

    private func encodeBody(request: LanguageModelRequest, cfg: OpenAICompatibleConfig, stream: Bool) throws -> Data {
        var messages: [[String: String]] = []
        if let system = request.systemPrompt, !system.isEmpty {
            messages.append(["role": "system", "content": system])
        }
        for m in request.messages {
            messages.append(["role": m.role.rawValue, "content": m.content])
        }
        var payload: [String: Any] = [
            "model": cfg.model,
            "messages": messages,
            "stream": stream
        ]
        if let temperature = request.parameters.temperature {
            payload["temperature"] = temperature
        }
        if let maxTokens = request.parameters.maxTokens {
            payload["max_tokens"] = maxTokens
        }
        if let topP = request.parameters.topP {
            payload["top_p"] = topP
        }
        if let stop = request.parameters.stopSequences, !stop.isEmpty {
            payload["stop"] = stop
        }
        return try JSONSerialization.data(withJSONObject: payload)
    }

    private func throwIfHTTPError(_ response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else { return }
        if (200...299).contains(http.statusCode) { return }
        let snippet = String(data: data, encoding: .utf8)?.prefix(240) ?? ""
        if http.statusCode == 401 || http.statusCode == 403 {
            throw LanguageModelError.providerUnavailable("Provider rejected credentials (HTTP \(http.statusCode))")
        }
        throw LanguageModelError.generationFailed("HTTP \(http.statusCode) \(snippet)")
    }

    static func extractText(_ obj: [String: Any]?) -> String? {
        guard let obj else { return nil }
        if let choices = obj["choices"] as? [[String: Any]], let first = choices.first {
            if let msg = first["message"] as? [String: Any], let content = msg["content"] as? String {
                return content
            }
            if let text = first["text"] as? String { return text }
        }
        if let message = obj["message"] as? [String: Any], let content = message["content"] as? String {
            return content
        }
        return nil
    }

    static func extractFinish(_ obj: [String: Any]?) -> String? {
        guard let choices = obj?["choices"] as? [[String: Any]], let first = choices.first else { return nil }
        return first["finish_reason"] as? String
    }

    static func extractDelta(_ obj: [String: Any]) -> String? {
        if let choices = obj["choices"] as? [[String: Any]], let first = choices.first {
            if let delta = first["delta"] as? [String: Any], let content = delta["content"] as? String {
                return content
            }
            if let text = first["text"] as? String { return text }
        }
        return nil
    }
}
