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

    // MARK: - Cancellation

    func testStream_cancellationPropagates() async throws {
        let provider = MockLanguageModelProvider(
            fixedResponseText: "a b c d e f g h i j k l m n o p",
            streamDelayNanoseconds: 30_000_000
        )
        try await provider.load()

        let request = LanguageModelRequest(
            messages: [LanguageModelMessage(role: .user, content: "cancel me")]
        )

        let stream = provider.stream(request)
        let task = Task {
            var count = 0
            for try await _ in stream {
                count += 1
                if count >= 1 {
                    break
                }
            }
            return count
        }

        try await Task.sleep(nanoseconds: 40_000_000)
        task.cancel()

        do {
            _ = try await task.value
        } catch let error as LanguageModelError {
            XCTAssertEqual(error, .cancelled)
        } catch is CancellationError {
            // acceptable
        }
    }

    func testGenerate_cancellation() async throws {
        let provider = MockLanguageModelProvider(fixedResponseText: "slow")
        try await provider.load()
        let request = LanguageModelRequest(
            messages: [LanguageModelMessage(role: .user, content: "x")]
        )

        let task = Task {
            try await provider.generate(request)
        }
        task.cancel()
        do {
            _ = try await task.value
        } catch is CancellationError {
            // ok
        } catch let error as LanguageModelError where error == .cancelled {
            // ok
        }
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
