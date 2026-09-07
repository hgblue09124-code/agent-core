// ios/AgentCoreIOS/Providers/MockLanguageModelProvider.swift
// Deterministic Mock Language Model Provider — Step 1 (testing only)
// Never used as a production inference path for real models.

import Foundation

/// Deterministic mock provider for unit / integration tests.
/// Supports load / generate / stream / unload and cooperative cancellation.
///
/// Cancellation instrumentation (test-only counters) lets unit tests prove that
/// producer work actually stops when the consumer/runtime cancels the stream.
public final class MockLanguageModelProvider: LanguageModelProvider, @unchecked Sendable {
    public let providerId: String = "MockLanguageModelProvider"

    private let lock = NSLock()
    private var _isLoaded: Bool = false
    private var _shouldFailLoad: Bool = false
    private var _fixedResponseText: String
    private var _streamChunks: [String]
    private var _streamDelayNanoseconds: UInt64
    private var _generateDelayNanoseconds: UInt64

    // MARK: - Cancellation / activity instrumentation (visible to tests)

    private var _emittedChunkCount: Int = 0
    private var _didObserveCancellation: Bool = false
    private var _activeStreamTasks: Int = 0
    private var _completedStreamTasks: Int = 0

    public var isLoaded: Bool {
        lock.lock()
        defer { lock.unlock() }
        return _isLoaded
    }

    /// Number of stream chunks successfully yielded since last reset / init.
    public var emittedChunkCount: Int {
        lock.lock()
        defer { lock.unlock() }
        return _emittedChunkCount
    }

    /// True if any stream or generate path observed Task cancellation.
    public var didObserveCancellation: Bool {
        lock.lock()
        defer { lock.unlock() }
        return _didObserveCancellation
    }

    /// Number of in-flight stream producer tasks.
    public var activeStreamTasks: Int {
        lock.lock()
        defer { lock.unlock() }
        return _activeStreamTasks
    }

    public var completedStreamTasks: Int {
        lock.lock()
        defer { lock.unlock() }
        return _completedStreamTasks
    }

    /// Creates a mock with deterministic output.
    /// - Parameters:
    ///   - fixedResponseText: Text returned by `generate`.
    ///   - streamChunks: Chunks yielded by `stream` (defaults to splitting fixedResponseText by spaces).
    ///   - streamDelayNanoseconds: Artificial delay between chunks to allow cancellation tests.
    ///   - generateDelayNanoseconds: Artificial delay inside `generate` (for cancellation tests).
    public init(
        fixedResponseText: String = "Mock response for testing.",
        streamChunks: [String]? = nil,
        streamDelayNanoseconds: UInt64 = 5_000_000, // 5 ms
        generateDelayNanoseconds: UInt64 = 0
    ) {
        self._fixedResponseText = fixedResponseText
        if let chunks = streamChunks, !chunks.isEmpty {
            self._streamChunks = chunks
        } else {
            let parts = fixedResponseText.split(separator: " ", omittingEmptySubsequences: false).map(String.init)
            self._streamChunks = parts.isEmpty ? [fixedResponseText] : parts
        }
        self._streamDelayNanoseconds = streamDelayNanoseconds
        self._generateDelayNanoseconds = generateDelayNanoseconds
    }

    /// Test helper: force `load()` to fail.
    public func setShouldFailLoad(_ value: Bool) {
        lock.lock()
        _shouldFailLoad = value
        lock.unlock()
    }

    /// Reset cancellation/activity counters (does not change load state).
    public func resetInstrumentation() {
        lock.lock()
        _emittedChunkCount = 0
        _didObserveCancellation = false
        _activeStreamTasks = 0
        _completedStreamTasks = 0
        lock.unlock()
    }

    private func markCancellationObserved() {
        lock.lock()
        _didObserveCancellation = true
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
            return
        }

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

        let delay = _generateDelayNanoseconds
        if delay > 0 {
            do {
                try await Task.sleep(nanoseconds: delay)
            } catch is CancellationError {
                markCancellationObserved()
                throw LanguageModelError.cancelled
            }
        }

        do {
            try Task.checkCancellation()
        } catch is CancellationError {
            markCancellationObserved()
            throw LanguageModelError.cancelled
        }

        let lastUser = request.messages.last(where: { $0.role == .user })?.content ?? ""
        let text: String
        if lastUser.isEmpty || _fixedResponseText != "Mock response for testing." {
            text = _fixedResponseText
        } else {
            text = "\(_fixedResponseText) [echo: \(lastUser)]"
        }

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
                self.lock.lock()
                self._activeStreamTasks += 1
                self.lock.unlock()
                defer {
                    self.lock.lock()
                    self._activeStreamTasks = max(0, self._activeStreamTasks - 1)
                    self._completedStreamTasks += 1
                    self.lock.unlock()
                }

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
                        self.lock.lock()
                        self._emittedChunkCount += 1
                        self.lock.unlock()
                    }
                    continuation.finish()
                } catch is CancellationError {
                    self.markCancellationObserved()
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
