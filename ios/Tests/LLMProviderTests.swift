// ios/Tests/LLMProviderTests.swift
// Catalog, GGUF inspect, download, OpenAI-compatible provider, router.

import XCTest
@testable import AgentCoreIOS

final class LLMProviderTests: XCTestCase {

    func testCatalog_containsTinyThroughMedium() {
        let classes = Set(ModelCatalog.all.map(\.sizeClass))
        XCTAssertTrue(classes.contains(.tiny))
        XCTAssertTrue(classes.contains(.small))
        XCTAssertTrue(classes.contains(.medium))
        XCTAssertNotNil(ModelCatalog.spec(id: ModelCatalog.defaultModelId))
        XCTAssertEqual(ModelCatalog.all.count, 4)
    }

    func testGGUFHeader_readsArchitectureAndName() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let url = dir.appendingPathComponent("toy.gguf")
        try Self.writeMinimalGGUF(to: url, architecture: "qwen2", name: "toy-qwen")
        XCTAssertTrue(GGUFHeader.isGGUF(fileAt: url))
        let info = try GGUFHeader.inspect(fileAt: url)
        XCTAssertEqual(info.architecture, "qwen2")
        XCTAssertEqual(info.name, "toy-qwen")
        XCTAssertEqual(info.version, 3)
    }

    func testGGUFHeader_rejectsNonMagic() throws {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try Data("NOTG".utf8).write(to: url)
        defer { try? FileManager.default.removeItem(at: url) }
        XCTAssertFalse(GGUFHeader.isGGUF(fileAt: url))
        XCTAssertThrowsError(try GGUFHeader.inspect(fileAt: url))
    }

    func testDownload_fileURLInstallsAndInspects() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }

        let source = root.appendingPathComponent("src.gguf")
        try Self.writeMinimalGGUF(to: source, architecture: "llama", name: "fixture")

        let spec = LLMModelSpec(
            id: "fixture-tiny",
            displayName: "Fixture",
            family: "test",
            parameterLabel: "0B",
            sizeClass: .tiny,
            quantization: "F16",
            downloadURL: source,
            filename: "fixture.gguf",
            approximateBytes: 64,
            ollamaTag: "fixture"
        )
        let manager = ModelDownloadManager(root: root)
        let dest = try await manager.download(spec)
        XCTAssertTrue(FileManager.default.fileExists(atPath: dest.path))
        let info = try manager.inspect(spec)
        XCTAssertEqual(info.architecture, "llama")
        XCTAssertTrue(manager.isInstalled(spec))

        try manager.delete(spec)
        XCTAssertFalse(manager.isInstalled(spec))
    }

    func testDownload_rejectsDisallowedHost() async {
        let spec = LLMModelSpec(
            id: "bad",
            displayName: "Bad",
            family: "x",
            parameterLabel: "0B",
            sizeClass: .tiny,
            quantization: "Q4",
            downloadURL: URL(string: "https://evil.example/model.gguf")!,
            filename: "x.gguf",
            approximateBytes: 10,
            ollamaTag: "x"
        )
        let manager = ModelDownloadManager(root: FileManager.default.temporaryDirectory)
        do {
            _ = try await manager.download(spec)
            XCTFail("expected allow-list failure")
        } catch let error as LanguageModelError {
            if case .downloadFailed(let msg) = error {
                XCTAssertTrue(msg.contains("allow-list"), msg)
            } else {
                XCTFail("wrong error \(error)")
            }
        } catch {
            XCTFail("unexpected \(error)")
        }
    }

    func testOpenAICompatible_generateParsesChatCompletions() async throws {
        StubURLProtocol.handler = { request in
            XCTAssertTrue(request.url?.absoluteString.contains("chat/completions") == true)
            XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer test-key")
            let json = """
            {"choices":[{"message":{"role":"assistant","content":"pong"},"finish_reason":"stop"}]}
            """
            return (200, Data(json.utf8), "application/json")
        }
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubURLProtocol.self]
        let session = URLSession(configuration: config)
        let provider = OpenAICompatibleProvider(
            config: OpenAICompatibleConfig(
                providerId: "openai",
                baseURL: URL(string: "https://api.openai.com/v1")!,
                apiKey: "test-key",
                model: "gpt-4o-mini"
            ),
            session: session,
            isRemote: true
        )
        try await provider.load()
        let response = try await provider.generate(
            LanguageModelRequest(messages: [LanguageModelMessage(role: .user, content: "ping")])
        )
        XCTAssertEqual(response.text, "pong")
        XCTAssertEqual(response.finishReason, "stop")
        XCTAssertEqual(response.metadata["provider"], "openai")
        StubURLProtocol.handler = nil
    }

    func testOpenAICompatible_httpErrorSurfaces() async throws {
        StubURLProtocol.handler = { _ in
            (401, Data(#"{"error":"nope"}"#.utf8), "application/json")
        }
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubURLProtocol.self]
        let session = URLSession(configuration: config)
        let provider = OpenAICompatibleProvider(
            config: OpenAICompatibleConfig(
                providerId: "openai",
                baseURL: URL(string: "https://api.openai.com/v1")!,
                apiKey: "bad",
                model: "gpt-4o-mini"
            ),
            session: session
        )
        try await provider.load()
        do {
            _ = try await provider.generate(
                LanguageModelRequest(messages: [LanguageModelMessage(role: .user, content: "x")])
            )
            XCTFail("expected auth error")
        } catch let error as LanguageModelError {
            if case .providerUnavailable = error {
                // ok
            } else {
                XCTFail("wrong \(error)")
            }
        }
        StubURLProtocol.handler = nil
    }

    func testRouter_privacyModeBlocksCloud() async throws {
        let defaults = UserDefaults(suiteName: UUID().uuidString)!
        let store = LLMSettingsStore(defaults: defaults)
        store.save(LLMSettings(backend: .openai, onDeviceModelId: ModelCatalog.defaultModelId, remoteModel: "gpt-4o-mini", baseURL: "", privacyMode: true))
        store.setAPIKey("sk-test", for: .openai)
        let router = RoutingLanguageModelProvider(settingsStore: store)
        try await router.load()
        do {
            _ = try await router.generate(
                LanguageModelRequest(messages: [LanguageModelMessage(role: .user, content: "hi")])
            )
            XCTFail("privacy mode should block openai")
        } catch let error as LanguageModelError {
            if case .providerUnavailable(let msg) = error {
                XCTAssertTrue(msg.lowercased().contains("privacy"), msg)
            } else {
                XCTFail("wrong \(error)")
            }
        }
    }

    func testRouter_mockBackendWorks() async throws {
        let defaults = UserDefaults(suiteName: UUID().uuidString)!
        let store = LLMSettingsStore(defaults: defaults)
        store.save(LLMSettings(backend: .mock, onDeviceModelId: ModelCatalog.defaultModelId, remoteModel: "mock", baseURL: "", privacyMode: true))
        let router = RoutingLanguageModelProvider(settingsStore: store)
        try await router.load()
        let response = try await router.generate(
            LanguageModelRequest(messages: [LanguageModelMessage(role: .user, content: "hello")])
        )
        XCTAssertTrue(response.text.contains("hello") || response.text.contains("Mock"))
        let status = router.displayStatus()
        XCTAssertTrue(status.localOnly)
    }

    func testRuntime_healthUsesRouter() async {
        let defaults = UserDefaults(suiteName: UUID().uuidString)!
        let store = LLMSettingsStore(defaults: defaults)
        store.save(LLMSettings(backend: .onDevice, onDeviceModelId: ModelCatalog.defaultModelId, remoteModel: "", baseURL: "", privacyMode: true))
        let router = RoutingLanguageModelProvider(settingsStore: store)
        let runtime = AgentRuntime(languageModelProvider: router)
        let health = await runtime.health()
        XCTAssertTrue(health.isLocalOnly)
        XCTAssertTrue(health.providerName.contains("On-device"))
    }

    // MARK: - GGUF fixture

    static func writeMinimalGGUF(to url: URL, architecture: String, name: String) throws {
        var data = Data()
        data.append(contentsOf: Array("GGUF".utf8))
        data.append(u32(3))
        data.append(u64(0)) // tensors
        data.append(u64(2)) // kv
        appendString(&data, "general.architecture")
        data.append(u32(8))
        appendString(&data, architecture)
        appendString(&data, "general.name")
        data.append(u32(8))
        appendString(&data, name)
        try data.write(to: url)
    }

    private static func u32(_ v: UInt32) -> Data {
        var le = v.littleEndian
        return Data(bytes: &le, count: 4)
    }

    private static func u64(_ v: UInt64) -> Data {
        var le = v.littleEndian
        return Data(bytes: &le, count: 8)
    }

    private static func appendString(_ data: inout Data, _ s: String) {
        let bytes = Array(s.utf8)
        data.append(u64(UInt64(bytes.count)))
        data.append(contentsOf: bytes)
    }
}

final class StubURLProtocol: URLProtocol {
    static var handler: ((URLRequest) throws -> (Int, Data, String))?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        do {
            guard let handler = StubURLProtocol.handler else {
                throw LanguageModelError.generationFailed("no stub handler")
            }
            let (code, data, mime) = try handler(request)
            let response = HTTPURLResponse(
                url: request.url ?? URL(string: "https://example.invalid")!,
                statusCode: code,
                httpVersion: "HTTP/1.1",
                headerFields: ["Content-Type": mime]
            )!
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}
