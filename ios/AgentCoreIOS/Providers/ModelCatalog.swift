// ios/AgentCoreIOS/Providers/ModelCatalog.swift
// Tiny → medium GGUF catalog, on-disk layout, and GGUF header inspection.
// Weights only — never downloads executable code.

import Foundation

public enum LLMSizeClass: String, Codable, Sendable, CaseIterable {
    case tiny
    case small
    case medium
}

public struct LLMModelSpec: Codable, Sendable, Equatable, Identifiable {
    public let id: String
    public let displayName: String
    public let family: String
    public let parameterLabel: String
    public let sizeClass: LLMSizeClass
    public let quantization: String
    public let downloadURL: URL
    public let filename: String
    public let approximateBytes: Int64
    public let sha256: String?
    public let ollamaTag: String

    public init(
        id: String,
        displayName: String,
        family: String,
        parameterLabel: String,
        sizeClass: LLMSizeClass,
        quantization: String,
        downloadURL: URL,
        filename: String,
        approximateBytes: Int64,
        sha256: String? = nil,
        ollamaTag: String
    ) {
        self.id = id
        self.displayName = displayName
        self.family = family
        self.parameterLabel = parameterLabel
        self.sizeClass = sizeClass
        self.quantization = quantization
        self.downloadURL = downloadURL
        self.filename = filename
        self.approximateBytes = approximateBytes
        self.sha256 = sha256
        self.ollamaTag = ollamaTag
    }

    public var sizeLabel: String {
        let mb = Double(approximateBytes) / 1_000_000.0
        if mb >= 1000 {
            return String(format: "%.1f GB", mb / 1000.0)
        }
        return String(format: "%.0f MB", mb)
    }
}

public struct GGUFInfo: Sendable, Equatable {
    public let architecture: String
    public let name: String
    public let version: UInt32
    public let tensorCount: UInt64

    public init(architecture: String, name: String, version: UInt32, tensorCount: UInt64) {
        self.architecture = architecture
        self.name = name
        self.version = version
        self.tensorCount = tensorCount
    }
}

public enum GGUFError: Error, Sendable, Equatable {
    case notGGUF
    case truncated
    case unsupportedVersion(UInt32)
}

/// Built-in catalog of on-device-friendly instruct GGUF weights (Q4_K_M).
public enum ModelCatalog {
    public static let defaultModelId = "qwen25-0.5b-q4"

    public static let all: [LLMModelSpec] = [
        LLMModelSpec(
            id: "qwen25-0.5b-q4",
            displayName: "Qwen2.5 0.5B Instruct",
            family: "Qwen2.5",
            parameterLabel: "0.5B",
            sizeClass: .tiny,
            quantization: "Q4_K_M",
            downloadURL: URL(string: "https://huggingface.co/bartowski/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf")!,
            filename: "Qwen2.5-0.5B-Instruct-Q4_K_M.gguf",
            approximateBytes: 397_808_192,
            sha256: "6eb923e7d26e9cea28811e1a8e852009b21242fb157b26149d3b188f3a8c8653",
            ollamaTag: "qwen2.5:0.5b"
        ),
        LLMModelSpec(
            id: "llama32-1b-q4",
            displayName: "Llama 3.2 1B Instruct",
            family: "Llama-3.2",
            parameterLabel: "1B",
            sizeClass: .tiny,
            quantization: "Q4_K_M",
            downloadURL: URL(string: "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf")!,
            filename: "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
            approximateBytes: 771_000_000,
            ollamaTag: "llama3.2:1b"
        ),
        LLMModelSpec(
            id: "llama32-3b-q4",
            displayName: "Llama 3.2 3B Instruct",
            family: "Llama-3.2",
            parameterLabel: "3B",
            sizeClass: .small,
            quantization: "Q4_K_M",
            downloadURL: URL(string: "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf")!,
            filename: "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
            approximateBytes: 2_020_000_000,
            ollamaTag: "llama3.2:3b"
        ),
        LLMModelSpec(
            id: "phi35-mini-q4",
            displayName: "Phi-3.5 Mini Instruct",
            family: "Phi-3.5",
            parameterLabel: "3.8B",
            sizeClass: .medium,
            quantization: "Q4_K_M",
            downloadURL: URL(string: "https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf")!,
            filename: "Phi-3.5-mini-instruct-Q4_K_M.gguf",
            approximateBytes: 2_400_000_000,
            ollamaTag: "phi3.5:3.8b"
        ),
    ]

    public static func spec(id: String) -> LLMModelSpec? {
        all.first { $0.id == id }
    }

    public static func modelsDir(base: URL? = nil) -> URL {
        let root = base ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
            .appendingPathComponent("AgentCore", isDirectory: true)
        return root.appendingPathComponent("models", isDirectory: true)
    }

    public static func localURL(for spec: LLMModelSpec, base: URL? = nil) -> URL {
        modelsDir(base: base).appendingPathComponent(spec.filename)
    }
}

public enum GGUFHeader {
    public static func inspect(fileAt url: URL) throws -> GGUFInfo {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        let prefix = handle.readData(ofLength: 24)
        guard prefix.count >= 24 else { throw GGUFError.truncated }
        guard prefix.prefix(4) == Data("GGUF".utf8) else { throw GGUFError.notGGUF }
        let version = readU32(prefix, 4)
        guard version >= 1 && version <= 3 else { throw GGUFError.unsupportedVersion(version) }
        let nTensors = readU64(prefix, 8)
        let nKV = readU64(prefix, 16)

        var architecture = ""
        var name = ""
        for _ in 0..<min(nKV, 64) {
            guard let key = readString(handle) else { break }
            guard let typeRaw = readU32(handle) else { break }
            if typeRaw == 8 { // STRING
                let value = readString(handle) ?? ""
                if key == "general.architecture" { architecture = value }
                if key == "general.name" { name = value }
            } else {
                skipValue(handle, type: typeRaw)
            }
        }
        return GGUFInfo(architecture: architecture, name: name, version: version, tensorCount: nTensors)
    }

    public static func isGGUF(fileAt url: URL) -> Bool {
        guard let handle = try? FileHandle(forReadingFrom: url) else { return false }
        defer { try? handle.close() }
        return handle.readData(ofLength: 4) == Data("GGUF".utf8)
    }

    private static func readU32(_ data: Data, _ offset: Int) -> UInt32 {
        let bytes = [UInt8](data.subdata(in: offset..<(offset + 4)))
        return UInt32(bytes[0]) | UInt32(bytes[1]) << 8 | UInt32(bytes[2]) << 16 | UInt32(bytes[3]) << 24
    }

    private static func readU64(_ data: Data, _ offset: Int) -> UInt64 {
        var v: UInt64 = 0
        let bytes = [UInt8](data.subdata(in: offset..<(offset + 8)))
        for i in 0..<8 { v |= UInt64(bytes[i]) << (8 * i) }
        return v
    }

    private static func readU32(_ handle: FileHandle) -> UInt32? {
        let data = handle.readData(ofLength: 4)
        guard data.count == 4 else { return nil }
        return readU32(data, 0)
    }

    private static func readU64(_ handle: FileHandle) -> UInt64? {
        let data = handle.readData(ofLength: 8)
        guard data.count == 8 else { return nil }
        return readU64(data, 0)
    }

    private static func readString(_ handle: FileHandle) -> String? {
        guard let len = readU64(handle), len < 4096 else { return nil }
        let data = handle.readData(ofLength: Int(len))
        guard data.count == Int(len) else { return nil }
        return String(data: data, encoding: .utf8) ?? ""
    }

    private static func skipValue(_ handle: FileHandle, type: UInt32) {
        switch type {
        case 0, 1: _ = handle.readData(ofLength: 1)
        case 2, 3: _ = handle.readData(ofLength: 2)
        case 4, 5, 6: _ = handle.readData(ofLength: 4)
        case 7: _ = handle.readData(ofLength: 1)
        case 8: _ = readString(handle)
        case 10, 11, 12: _ = handle.readData(ofLength: 8)
        case 9:
            guard let elemType = readU32(handle), let count = readU64(handle) else { return }
            if elemType == 8 {
                for _ in 0..<min(count, 256) { _ = readString(handle) }
            } else {
                let width: Int
                switch elemType {
                case 0, 1, 7: width = 1
                case 2, 3: width = 2
                case 4, 5, 6: width = 4
                default: width = 8
                }
                let n = min(Int(count), 4096) * width
                _ = handle.readData(ofLength: n)
            }
        default:
            break
        }
    }
}
