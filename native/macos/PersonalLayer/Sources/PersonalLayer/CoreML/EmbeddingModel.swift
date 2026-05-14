import CoreML
import Foundation
import NaturalLanguage

/// On-device embedding pipeline using Core ML.
/// Expects an all-MiniLM-L6-v2 model converted to Core ML (mlmodelc).
/// Falls back to NLTagger sentence embeddings if the model is missing.
final class EmbeddingModel {
    static let shared = EmbeddingModel()

    private var model: MLModel?
    private let vocab: [String: Int]
    private let embeddingSize = 384

    private init() {
        self.vocab = EmbeddingVocab.load()
        self.model = try? loadCoreMLModel()
    }

    private func loadCoreMLModel() throws -> MLModel {
        let config = MLModelConfiguration()
        config.computeUnits = .cpuAndNeuralEngine
        guard let url = Bundle.main.url(forResource: "all-MiniLM-L6-v2",
                                        withExtension: "mlmodelc",
                                        subdirectory: "Models") else {
            throw EmbeddingError.modelNotFound
        }
        return try MLModel(contentsOf: url, configuration: config)
    }

    /// Encode text into a 384-dimension float array.
    func encode(text: String) throws -> [Float] {
        if let model = model {
            return try coreMLEncode(text: text, model: model)
        } else {
            return try fallbackEncode(text: text)
        }
    }

    private func coreMLEncode(text: String, model: MLModel) throws -> [Float] {
        let input = try MLDictionaryFeatureProvider(dictionary: [
            "text": MLFeatureValue(string: text)
        ])
        let output = try model.prediction(from: input)
        guard let multiArray = output.featureValue(for: "embeddings")?.multiArrayValue else {
            throw EmbeddingError.invalidOutput
        }
        var floats: [Float] = []
        for i in 0..<multiArray.count {
            floats.append(multiArray[i].floatValue)
        }
        return floats
    }

    /// Cosine similarity between two embeddings.
    func cosineSimilarity(_ a: [Float], _ b: [Float]) -> Float {
        precondition(a.count == b.count)
        let dot = zip(a, b).map(*).reduce(0, +)
        let normA = sqrt(a.map { $0 * $0 }.reduce(0, +))
        let normB = sqrt(b.map { $0 * $0 }.reduce(0, +))
        guard normA > 0, normB > 0 else { return 0 }
        return dot / (normA * normB)
    }

    /// Fallback using NLTagger sentence embeddings (768-dim, truncated to 384).
    private func fallbackEncode(text: String) throws -> [Float] {
        let tagger = NLTagger(tagSchemes: [.lexicalClass])
        tagger.string = text
        guard let sentenceEmbedding = NLSentenceEmbedding.sentenceEmbedding(for: .english) else {
            throw EmbeddingError.fallbackUnavailable
        }
        sentenceEmbedding.encode(text)
        var vector = [Double](repeating: 0, count: 768)
        sentenceEmbedding.getVector(for: text, vector: &vector)
        return vector.prefix(384).map { Float($0) }
    }
}

enum EmbeddingError: Error {
    case modelNotFound
    case invalidOutput
    case fallbackUnavailable
}

/// Minimal vocabulary loader for tokenizer parity.
/// In production, ship a vocab.json from the HF model repo.
struct EmbeddingVocab {
    static func load() -> [String: Int] {
        [:] // Placeholder: load vocab.json at runtime
    }
}
