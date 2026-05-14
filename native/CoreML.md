# Core ML Embedding Model

## Model
- **Name**: all-MiniLM-L6-v2
- **Source**: HuggingFace sentence-transformers
- **Output**: 384-dimensional float32 embeddings
- **Max sequence length**: 256 tokens
- **Compute**: CPU + GPU + Neural Engine (via `ComputeUnit.ALL`)

## Conversion

### Prerequisites
```bash
pip install torch transformers sentence-transformers coremltools
```

### Generate
```bash
python scripts/convert-coreml-model.py
```

This produces:
- `native/macos/PersonalLayer/Resources/all-MiniLM-L6-v2.mlpackage`
- `native/ios/PersonalLayer/Resources/all-MiniLM-L6-v2.mlpackage`
- `native/macos/PersonalLayer/Resources/vocab.json`

### Xcode Integration
1. Open `native/macos/PersonalLayer` in Xcode (or iOS equivalent)
2. Drag the `.mlpackage` into the project navigator
3. Ensure "Copy items if needed" is checked
4. Select the file → File Inspector → Target Membership → check the app target
5. The model will compile to `.mlmodelc` at build time

### Runtime Usage
```swift
let model = try MLModel(contentsOf: Bundle.main.url(forResource: "all-MiniLM-L6-v2", withExtension: "mlmodelc")!)
let prediction = try model.prediction(from: inputProvider)
```

## Fallback
If the Core ML model is unavailable (e.g., first launch before model download), the app falls back to `NLTagger` embedding (word frequency vectors) for graceful degradation.
