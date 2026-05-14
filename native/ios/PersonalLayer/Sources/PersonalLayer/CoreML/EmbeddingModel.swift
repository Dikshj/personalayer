import CoreML
import Foundation

/// all-MiniLM-L6-v2 embedding model via Core ML.
/// Expects a .mlpackage in the app bundle (converted via scripts/convert-coreml-model.py).
/// Produces 384-dimensional float32 embeddings.
final class EmbeddingModel {
    static let shared = EmbeddingModel()
    private var model: MLModel?
    private var vocab: [String: Int] = [:]

    private init() {
        do {
            self.model = try loadCoreMLModel()
            self.vocab = try loadVocab()
        } catch {
            print("[EmbeddingModel] Failed to load model: \(error). " +
                  "Run 'python scripts/convert-coreml-model.py' on macOS to generate the .mlpackage.")
        }
    }

    private func loadCoreMLModel() throws -> MLModel {
        let config = MLModelConfiguration()
        config.computeUnits = .all

        // Try .mlpackage first (modern format)
        if let url = Bundle.main.url(forResource: "all-MiniLM-L6-v2", withExtension: "mlpackage") {
            return try MLModel(contentsOf: url, configuration: config)
        }
        // Fallback to .mlmodelc (compiled model)
        if let url = Bundle.main.url(forResource: "all-MiniLM-L6-v2", withExtension: "mlmodelc") {
            return try MLModel(contentsOf: url, configuration: config)
        }
        throw EmbeddingError.modelNotFound
    }

    private func loadVocab() throws -> [String: Int] {
        guard let url = Bundle.main.url(forResource: "vocab", withExtension: "json") else {
            return [:]
        }
        let data = try Data(contentsOf: url)
        return (try JSONSerialization.jsonObject(with: data) as? [String: Int]) ?? [:]
    }

    /// Encode text into a 384-dimensional embedding vector.
    func encode(text: String) throws -> [Float] {
        guard let model = model else {
            throw EmbeddingError.modelNotLoaded
        }
        return try coreMLEncode(text: text, model: model)
    }

    private func coreMLEncode(text: String, model: MLModel) throws -> [Float] {
        // Tokenize using loaded vocab (WordPiece style)
        let inputIds = tokenize(text: text, maxLength: 256)
        let attentionMask = inputIds.map { $0 > 0 ? 1 : 0 }

        // Create MLMultiArray inputs
        let inputIdsArray = try MLMultiArray(shape: [1, 256], dataType: .int32)
        let attentionMaskArray = try MLMultiArray(shape: [1, 256], dataType: .int32)
        for i in 0..<256 {
            inputIdsArray[[0, i] as [NSNumber]] = NSNumber(value: inputIds[i])
            attentionMaskArray[[0, i] as [NSNumber]] = NSNumber(value: attentionMask[i])
        }

        let input = try MLDictionaryFeatureProvider(dictionary: [
            "input_ids": MLFeatureValue(multiArray: inputIdsArray),
            "attention_mask": MLFeatureValue(multiArray: attentionMaskArray)
        ])

        let output = try model.prediction(from: input)
        guard let multiArray = output.featureValue(for: "embeddings")?.multiArrayValue else {
            throw EmbeddingError.invalidOutput
        }

        var embedding: [Float] = []
        for i in 0..<multiArray.count {
            embedding.append(multiArray[i].floatValue)
        }
        return embedding
    }

    /// Simple WordPiece-style tokenization.
    private func tokenize(text: String, maxLength: Int) -> [Int] {
        let tokens = ["[CLS]"] + text.lowercased().components(separatedBy: .alphanumerics.inverted).filter { !$0.isEmpty } + ["[SEP]"]
        var inputIds: [Int] = []
        for token in tokens {
            if let id = vocab[token] {
                inputIds.append(id)
            } else {
                // Unknown token — try subword splitting
                var remaining = token
                while !remaining.isEmpty {
                    let prefix = vocab.keys.first { remaining.hasPrefix($0) }
                    if let p = prefix, let id = vocab[p] {
                        inputIds.append(id)
                        remaining = String(remaining.dropFirst(p.count))
                    } else {
                        inputIds.append(vocab["[UNK]"] ?? 100)
                        break
                    }
                }
            }
            if inputIds.count >= maxLength - 1 { break }
        }
        // Pad
        while inputIds.count < maxLength {
            inputIds.append(vocab["[PAD]"] ?? 0)
        }
        return Array(inputIds.prefix(maxLength))
    }

    /// Cosine similarity between two embeddings.
    func cosineSimilarity(_ a: [Float], _ b: [Float]) -> Float {
        let dot = zip(a, b).map(*).reduce(0, +)
        let na = sqrt(a.map { $0 * $0 }.reduce(0, +))
        let nb = sqrt(b.map { $0 * $0 }.reduce(0, +))
        guard na > 0, nb > 0 else { return 0 }
        return dot / (na * nb)
    }
}

enum EmbeddingError: Error {
    case modelNotFound
    case modelNotLoaded
    case invalidOutput
    case vocabMissing
}
