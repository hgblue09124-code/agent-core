// ios/Tests/LanguageModelProviderTests.swift
// Unit tests for LanguageModelProvider abstraction, Mock, DI, and runtime bridge (Step 1)

import XCTest
@testable import AgentCoreIOS

final class LanguageModelProviderTests: XCTestCase {

    // MARK: - Provider Lifecycle

    func testLifecycle_loadUnload() async throws {
        let provider = MockLanguageModelProvider()
        XCTAssertFalse(provider.isLoaded)

        try await provider.load()
        XCTAssertTrue(provider.isLoaded)

        // Idempotent second load
        try await provider.load()
        XCTAssertTrue(provider.isLoaded)

        await provider.unload()
        XCTAssertFalse(provider.isLoaded)

        // Unload when already unloaded is safe
        await provider.unload()
        XCTAssertFalse(provider.isLoaded)
    }

    func testLifecycle_generateRequiresLoad() async {
        let provider = MockLanguageModelProvider()
        let request = LanguageModelRequest(
            messages: [LanguageModelMessage(role: .user, content: "hello")]
        )
        do {
            _ = try await provider.generate(request)
            XCTFail("Expected notLoaded error")
        } catch let error as LanguageModelError {
            XCTAssertEqual(error, .notLoaded)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    // MARK: - Generate

    func testGenerate_deterministicResponse() async throws {
        let provider = MockLanguageModelProvider(fixedResponseText: "Deterministic mock answer.")
        try await provider.load()

        let request = LanguageModelRequest(
            systemPrompt: "You are a test assistant.",
            messages: [LanguageModelMessage(role: .user, content: "ping")]
        )
        let response = try await provider.generate(request)

        XCTAssertTrue(response.text.contains("Deterministic mock answer."))
        XCTAssertTrue(response.text.contains("[echo: ping]"))
        XCTAssertEqual(response.finishReason, "stop")
        XCTAssertEqual(response.metadata["provider"], "MockLanguageModelProvider")
        XCTAssertEqual(response.metadata["mock"], "true")
    }

    func testGenerate_invalidEmptyRequest() async throws {
        let provider = MockLanguageModelProvider()
        try await provider.load()
        let request = LanguageModelRequest(messages: [])
        do {
            _ = try await provider.generate(request)
            XCTFail("Expected invalidRequest")
        } catch let error as LanguageModelError {
            if case .invalidRequest = error {
                // ok
            } else {
                XCTFail("Wrong error: \(error)")
            }
        }
    }

    // MARK: - Streaming

    func testStream_emitsChunksThenCompletes() async throws {
        let chunks = ["Hello", "world", "from", "mock"]
        let provider = MockLanguageModelProvider(
            fixedResponseText: "unused",
            streamChunks: chunks,
            streamDelayNanoseconds: 1_000_000
        )
        try await provider.load()

        let request = LanguageModelRequest(
            messages: [LanguageModelMessage(role: .user, content: "stream me")]
        )

        var received: [String] = []
        var sawFinal = false
        for try await chunk in provider.stream(request) {
            received.append(chunk.text.trimmingCharacters(in: .whitespaces))
            if chunk.isFinal {
                sawFinal = true
            }
        }

        XCTAssertEqual(received.count, chunks.count)
        XCTAssertEqual(received, chunks)
        XCTAssertTrue(sawFinal)
    }

    // MARK: - Cancellation (must prove producer stops while work is in-flight)

    /// End-to-end stream cancellation:
    /// 1. Start a long stream (many slow chunks).
    /// 2. Wait until the producer has actually emitted chunks (stream is running).
    /// 3. Cancel the consumer Task while more work remains.
    /// 4. Assert the producer observed cancellation, stopped early, and left no active tasks.
    func testStream_cancellationStopsProducerWhileInFlight() async throws {
        let totalChunks = 40
        let provider = MockLanguageModelProvider(
            fixedResponseText: "unused",
            streamChunks: (0..<totalChunks).map { "c\($0)" },
            streamDelayNanoseconds: 40_000_000 // 40ms → full stream ~1.6s
        )
        try await provider.load()
        provider.resetInstrumentation()

        let request = LanguageModelRequest(
            messages: [LanguageModelMessage(role: .user, content: "cancel me mid-stream")]
        )

        let stream = provider.stream(request)
        let consumer = Task { () throws -> Int in
            var count = 0
            for try await _ in stream {
                count += 1
            }
            return count
        }

        // Wait until producer is clearly in-flight (at least 2 chunks emitted).
        var sawInFlight = false
        for _ in 0..<50 {
            if provider.emittedChunkCount >= 2 {
                sawInFlight = true
                break
            }
            try await Task.sleep(nanoseconds: 20_000_000)
        }
        XCTAssertTrue(sawInFlight, "Producer never started emitting; cannot validate mid-flight cancellation")
        XCTAssertGreaterThan(provider.activeStreamTasks, 0, "Expected an active stream producer task before cancel")

        let emittedBeforeCancel = provider.emittedChunkCount
        consumer.cancel()

        var sawCancelError = false
        do {
            let n = try await consumer.value
            // If the task returns normally, it must have stopped early due to termination —
            // still require producer observed cancellation and incomplete emission.
            XCTAssertLessThan(n, totalChunks, "Consumer completed all chunks; cancellation did not take effect")
        } catch is CancellationError {
            sawCancelError = true
        } catch let error as LanguageModelError where error == .cancelled {
            sawCancelError = true
        } catch {
            XCTFail("Unexpected error after cancel: \(error)")
        }

        // Allow producer onTermination + task cleanup to settle.
        for _ in 0..<30 {
            if provider.activeStreamTasks == 0 { break }
            try await Task.sleep(nanoseconds: 20_000_000)
        }

        XCTAssertTrue(
            provider.didObserveCancellation || sawCancelError,
            "Producer did not observe cancellation and consumer did not surface a cancel error"
        )
        XCTAssertEqual(provider.activeStreamTasks, 0, "Stream producer task still running after cancellation")
        XCTAssertLessThan(
            provider.emittedChunkCount,
            totalChunks,
            "Producer emitted all \(totalChunks) chunks after cancel — cancellation bridge is broken"
        )
        // Should not keep producing many more chunks after cancel was requested.
        XCTAssertLessThanOrEqual(
            provider.emittedChunkCount,
            emittedBeforeCancel + 3,
            "Producer continued emitting long after cancel (emittedBefore=\(emittedBeforeCancel), after=\(provider.emittedChunkCount))"
        )
    }

    /// Runtime stream bridge must propagate cancellation to the underlying provider.
    func testRuntimeStreamBridge_cancellationPropagatesToProvider() async throws {
        let totalChunks = 30
        let mock = MockLanguageModelProvider(
            fixedResponseText: "unused",
            streamChunks: (0..<totalChunks).map { "r\($0)" },
            streamDelayNanoseconds: 40_000_000
        )
        let runtime = AgentRuntime(languageModelProvider: mock)
        mock.resetInstrumentation()

        let request = LanguageModelRequest(
            messages: [LanguageModelMessage(role: .user, content: "runtime cancel")]
        )

        let stream = runtime.streamWithLanguageModel(request)
        let consumer = Task { () throws -> Int in
            var count = 0
            for try await _ in stream {
                count += 1
            }
            return count
        }

        var sawInFlight = false
        for _ in 0..<50 {
            if mock.emittedChunkCount >= 2 {
                sawInFlight = true
                break
            }
            try await Task.sleep(nanoseconds: 20_000_000)
        }
        XCTAssertTrue(sawInFlight, "Runtime stream never became active")

        consumer.cancel()

        do {
            let n = try await consumer.value
            XCTAssertLessThan(n, totalChunks)
        } catch is CancellationError {
            // ok
        } catch let error as LanguageModelError where error == .cancelled {
            // ok
        }

        for _ in 0..<30 {
            if mock.activeStreamTasks == 0 { break }
            try await Task.sleep(nanoseconds: 20_000_000)
        }

        XCTAssertEqual(mock.activeStreamTasks, 0)
        XCTAssertLessThan(mock.emittedChunkCount, totalChunks)
        XCTAssertTrue(mock.didObserveCancellation || mock.emittedChunkCount < totalChunks)
    }

    func testGenerate_cancellationWhileDelayed() async throws {
        let provider = MockLanguageModelProvider(
            fixedResponseText: "slow",
            generateDelayNanoseconds: 500_000_000 // 500ms
        )
        try await provider.load()
        provider.resetInstrumentation()

        let request = LanguageModelRequest(
            messages: [LanguageModelMessage(role: .user, content: "x")]
        )

        let task = Task {
            try await provider.generate(request)
        }
        // Let generate enter its delay window.
        try await Task.sleep(nanoseconds: 30_000_000)
        task.cancel()

        do {
            _ = try await task.value
            XCTFail("Expected generate to be cancelled")
        } catch is CancellationError {
            // ok
        } catch let error as LanguageModelError where error == .cancelled {
            // ok
        }

        XCTAssertTrue(provider.didObserveCancellation, "generate did not observe cancellation during delay")
    }

    // MARK: - Dependency Injection into AgentRuntime

    func testDI_runtimeUsesInjectedProvider() async throws {
        let mock = MockLanguageModelProvider(fixedResponseText: "Injected provider response.")
        let runtime = AgentRuntime(languageModelProvider: mock)

        XCTAssertTrue(runtime.hasLanguageModelProvider)
        XCTAssertEqual(runtime.languageModelProviderId, "MockLanguageModelProvider")

        try await runtime.loadLanguageModel()
        XCTAssertTrue(mock.isLoaded)

        let request = LanguageModelRequest(
            messages: [LanguageModelMessage(role: .user, content: "runtime-bridge")]
        )
        let response = try await runtime.generateWithLanguageModel(request)
        XCTAssertTrue(response.text.contains("Injected provider response."))
        XCTAssertTrue(response.text.contains("[echo: runtime-bridge]"))

        await runtime.unloadLanguageModel()
        XCTAssertFalse(mock.isLoaded)
    }

    func testDI_runtimeWithoutProviderThrows() async {
        let runtime = AgentRuntime()
        XCTAssertFalse(runtime.hasLanguageModelProvider)
        XCTAssertNil(runtime.languageModelProviderId)

        do {
            try await runtime.loadLanguageModel()
            XCTFail("Expected providerUnavailable")
        } catch let error as LanguageModelError {
            if case .providerUnavailable = error {
                // ok
            } else {
                XCTFail("Wrong error \(error)")
            }
        } catch {
            XCTFail("Unexpected \(error)")
        }
    }

    func testDI_runtimeStreamBridge() async throws {
        let mock = MockLanguageModelProvider(
            fixedResponseText: "stream via runtime",
            streamChunks: ["stream", "via", "runtime"],
            streamDelayNanoseconds: 1_000_000
        )
        let runtime = AgentRuntime(languageModelProvider: mock)

        let request = LanguageModelRequest(
            messages: [LanguageModelMessage(role: .user, content: "go")]
        )

        var parts: [String] = []
        for try await chunk in runtime.streamWithLanguageModel(request) {
            parts.append(chunk.text.trimmingCharacters(in: .whitespaces))
        }
        XCTAssertEqual(parts, ["stream", "via", "runtime"])
        XCTAssertTrue(mock.isLoaded)
    }

    // MARK: - Runtime interaction path (AgentRuntime → Mock → response)

    func testRuntimeInteraction_fullPath() async throws {
        let mock = MockLanguageModelProvider(fixedResponseText: "Step1 OK")
        let temp = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: temp, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: temp) }

        let runtime = AgentRuntime(
            memoryStore: LocalMemoryStore(storageDir: temp.appendingPathComponent("mem")),
            experienceStore: LocalExperienceStore(storageDir: temp.appendingPathComponent("exp")),
            checkpointStore: LocalCheckpointStore(storageDir: temp.appendingPathComponent("runs")),
            vaultStore: LocalVaultStore(storageDir: temp.appendingPathComponent("vault")),
            languageModelProvider: mock
        )

        let runResult = await runtime.run(goal: "Read status only", userApproved: true)
        XCTAssertEqual(runResult.status, .success)

        let lmResponse = try await runtime.generateWithLanguageModel(
            LanguageModelRequest(messages: [
                LanguageModelMessage(role: .system, content: "sys"),
                LanguageModelMessage(role: .user, content: "user-q")
            ])
        )
        XCTAssertTrue(lmResponse.text.contains("Step1 OK"))
        XCTAssertTrue(lmResponse.text.contains("user-q"))
    }
}
