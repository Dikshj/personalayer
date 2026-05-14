# Core ML Embedding Model

## Model
- **Name**: all-MiniLM-L6-v2
- **Source**: HuggingFace sentence-transformers
- **Output**: 384-dimensional float32 embeddings
- **Max sequence length**: 256 tokens

## Conversion

Run on macOS with Python:
```bash
pip install torch transformers sentence-transformers coremltools
python scripts/convert-coreml-model.py
```

## Integration

### macOS
Add `all-MiniLM-L6-v2.mlpackage` to the Xcode target as a bundle resource.

### iOS
Same model package works on iOS 16+ with Neural Engine fallback.

## Fallback

If the Core ML model is unavailable, the app falls back to `NLTagger` embedding (word frequency vectors) for graceful degradation.
