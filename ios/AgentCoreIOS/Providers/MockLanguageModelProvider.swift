// ios/AgentCoreIOS/Providers/MockLanguageModelProvider.swift
// Deterministic Mock Language Model Provider — Step 1 (testing only)
// Never used as a production inference path for real models.

import Foundation

/// Deterministic mock provider for unit / integration tests.
/// Supports load / generate / stream / unload and cooperative cancellation.
public final class MockLanguageModelProvider: LanguageModelProvider, @unchecked Sendable {
    public let providerId: String = "MockLanguageModelProvider"

    private let lock = NSLock()
    private var _isLoaded: Bool = false
    private var _shouldFailLoad: Bool = false
    private var _fixedResponseText: String
    private var _streamChunks: [String]
    private var _streamDelayNanoseconds: UInt64

    public var isLoaded: Bool {
        lock.lock()
        defer { lock.unlock() }
        return _isLoaded
    }

    /// Creates a mock with deterministic output.
    /// - Parameters:
    ///   - fixedResponseText: Text returned by `generate`.
    ///   - streamChunks: Chunks yielded by `stream` (defaults to splitting fixedResponseText by spaces).
    ///   - streamDelayNanoseconds: Artificial delay between chunks to allow cancellation tests.
    public init(
        fixedResponseText: String = "Mock response for testing.",
        streamChunks: [String]? = nil,
        streamDelayNanoseconds: UInt64 = 5_000_000 // 5 ms
    ) {
        self._fixedResponseText = fixedResponseText
        if let chunks = streamChunks, !chunks.isEmpty {
            self._streamChunks = chunks
        } else {
            // Split into word-like chunks for realistic streaming tests.
            let parts = fixedResponseText.split(separator: " ", omittingEmptySubsequences: false).map(String.init)
            self._streamChunks = parts.isEmpty ? [fixedResponseText] : parts
        }
        self._streamDelayNanoseconds = streamDelayNanoseconds
    }

    /// Test helper: force `load()` to fail.
    public func setShouldFailLoad(_ value: Bool) {
        lock.lock()
        _shouldFailLoad = value
        lock.unlock()
    }

    public func load() async throws {
        try Task.checkCancellation()
        lock.lock()
        let fail = _shouldFailLoad
        let already = _isLoaded
        lock.unlock()

        if fail {
            throw LanguageModelError.providerUnavailable("Mock load forced to fail")
        }
        if already {
            // Idempotent: already loaded is fine for mock.
            return
        }

        // Simulate a tiny amount of work.
        try await Task.sleep(nanoseconds: 1_000_000)
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
        guard isLoaded else {
            throw LanguageModelError.notLoaded
        }
        if request.messages.isEmpty && (request.systemPrompt == nil || request.systemPrompt?.isEmpty == true) {
            throw LanguageModelError.invalidRequest("Request must contain at least one message or a system prompt")
        }

        // Deterministic: incorporate last user message for traceability in tests.
        let lastUser = request.messages.last(where: { $0.role == .user })?.content ?? ""
        let text: String
        if lastUser.isEmpty {
            text = _fixedResponseText
        } else {
            text = "\(_fixedResponseText) [echo: \(lastUser)]"
        }

        try Task.checkCancellation()

        return LanguageModelResponse(
            text: text,
            finishReason: "stop",
            metadata: [
                "provider": providerId,
                "mock": "true"
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
                    if request.messages.isEmpty && (request.systemPrompt == nil || request.systemPrompt?.isEmpty == true) {
                        continuation.finish(throwing: LanguageModelError.invalidRequest("Request must contain at least one message or a system prompt"))
                        return
                    }

                    let chunks = self._streamChunks
                    let delay = self._streamDelayNanoseconds

                    for (index, part) in chunks.enumerated() {
                        try Task.checkCancellation()
                        if delay > 0 {
                            try await Task.sleep(nanoseconds: delay)
                        }
                        try Task.checkCancellation()

                        let isLast = index == chunks.count - 1
                        let chunkText = isLast ? part : part + " "
                        continuation.yield(
                            LanguageModelStreamChunk(
                                text: chunkText,
                                isFinal: isLast,
                                metadata: ["provider": self.providerId, "index": "\(index)"]
                            )
                        )
                    }
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
}
