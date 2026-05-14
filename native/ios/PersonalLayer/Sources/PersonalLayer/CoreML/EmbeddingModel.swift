import CoreML
import Foundation
import NaturalLanguage

final class EmbeddingModel {
    static let shared = EmbeddingModel()
    private var model: MLModel?

    private init() {
        self.model = try? loadCoreMLModel()
    }

    private func loadCoreMLModel() throws -> MLModel {
        let config = MLModelConfiguration()
        config.computeUnits = .cpuAndNeuralEngine
        guard let url = Bundle.module.url(forResource: "all-MiniLM-L6-v2",
                                          withExtension: "mlmodelc") else {
            throw EmbeddingError.modelNotFound
        }
        return try MLModel(contentsOf: url, configuration: config)
    }
    func encode(text: String) throws -> [Float] {
        if let model = model { return try coreMLEncode(text: text, model: model) }
        return try fallbackEncode(text: text)
    }

    private func coreMLEncode(text: String, model: MLModel) throws -> [Float] {
        let input = try MLDictionaryFeatureProvider(dictionary: ["text": MLFeatureValue(string: text)])
        let output = try model.prediction(from: input)
        guard let multiArray = output.featureValue(for: "embeddings")?.multiArrayValue else {
            throw EmbeddingError.invalidOutput
        }
        return (0..<multiArray.count).map { multiArray[$0].floatValue }
    }

    func cosineSimilarity(_ a: [Float], _ b: [Float]) -> Float {
        let dot = zip(a, b).map(*).reduce(0, +)
        let na = sqrt(a.map { $0 * $0 }.reduce(0, +))
        let nb = sqrt(b.map { $0 * $0 }.reduce(0, +))
        guard na > 0, nb > 0 else { return 0 }
        return dot / (na * nb)
    }

    private func fallbackEncode(text: String) throws -> [Float] {
        let tagger = NLTagger(tagSchemes: [.lexicalClass])
        tagger.string = text
        guard let se = NLSentenceEmbedding.sentenceEmbedding(for: .english) else {
            throw EmbeddingError.fallbackUnavailable
        }
        se.encode(text)
        var vector = [Double](repeating: 0, count: 768)
        se.getVector(for: text, vector: &vector)
        return vector.prefix(384).map { Float($0) }
    }
}

enum EmbeddingError: Error {
    case modelNotFound
    case invalidOutput
    case fallbackUnavailable
}
