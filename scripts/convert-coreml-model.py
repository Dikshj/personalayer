#!/usr/bin/env python3
"""Convert HuggingFace all-MiniLM-L6-v2 to Core ML.

Requirements:
    pip install torch transformers sentence-transformers coremltools

Usage:
    python scripts/convert-coreml-model.py

Output:
    native/macos/PersonalLayer/Resources/all-MiniLM-L6-v2.mlmodelc/
    native/ios/PersonalLayer/Resources/all-MiniLM-L6-v2.mlmodelc/

The model produces 384-dimensional float32 embeddings.
"""
import sys
import os
import json

def main():
    try:
        import torch
        import coremltools as ct
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install: pip install torch transformers sentence-transformers coremltools")
        sys.exit(1)

    model_name = "all-MiniLM-L6-v2"
    print(f"Loading {model_name}...")
    model = SentenceTransformer(model_name)
    model.eval()

    # Example input
    example_input = "This is a test sentence for embedding."
    max_length = 256

    # Trace the model
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(f"sentence-transformers/{model_name}")
    inputs = tokenizer(example_input, return_tensors="pt", truncation=True, padding="max_length", max_length=max_length)

    class TracableModel(torch.nn.Module):
        def __init__(self, model):
            super().__init__()
            self.model = model
        def forward(self, input_ids, attention_mask):
            out = self.model({"input_ids": input_ids, "attention_mask": attention_mask})
            return out["sentence_embedding"]

    traced = torch.jit.trace(TracableModel(model), (inputs["input_ids"], inputs["attention_mask"]))

    # Convert to Core ML
    print("Converting to Core ML...")
    mlmodel = ct.convert(
        traced,
        inputs=[
            ct.TensorType(name="input_ids", shape=(1, max_length), dtype=int),
            ct.TensorType(name="attention_mask", shape=(1, max_length), dtype=int)
        ],
        compute_units=ct.ComputeUnit.ALL,
        minimum_deployment_target=ct.target.iOS16
    )

    # Save to both macOS and iOS resource directories
    for platform in ["macos", "ios"]:
        out_dir = f"native/{platform}/PersonalLayer/Resources"
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "all-MiniLM-L6-v2.mlpackage")
        mlmodel.save(out_path)
        print(f"Saved to {out_path}")

    # Write vocab reference
    vocab_path = "native/macos/PersonalLayer/Resources/vocab.json"
    vocab = tokenizer.get_vocab()
    with open(vocab_path, "w") as f:
        json.dump(vocab, f)
    print(f"Saved vocab to {vocab_path}")

    # Verify output dimension
    test_emb = model.encode(example_input)
    assert len(test_emb) == 384, f"Expected 384 dims, got {len(test_emb)}"
    print(f"Verification passed: output dimension = {len(test_emb)}")
    print("Done. Add the .mlpackage files to your Xcode target as bundle resources.")

if __name__ == "__main__":
    main()
