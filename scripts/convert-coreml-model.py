#!/usr/bin/env python3
"""
Convert sentence-transformers/all-MiniLM-L6-v2 to Core ML .mlpackage.

Usage:
    python scripts/convert-coreml-model.py

Requirements:
    pip install transformers torch coremltools

Output:
    native/ios/PersonalLayer/Resources/all-MiniLM-L6-v2.mlpackage
"""

import json
import os
import sys
from pathlib import Path

try:
    import coremltools as ct
    import torch
    from transformers import AutoModel, AutoTokenizer
except ImportError as exc:
    print(f"Missing dependency: {exc}")
    print("Run: pip install transformers torch coremltools")
    sys.exit(1)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MAX_LENGTH = 256
PROJECT_ROOT = Path(__file__).parent.parent


def export_vocab(tokenizer, dest_dir: Path):
    vocab = tokenizer.get_vocab()
    vocab_path = dest_dir / "vocab.json"
    with open(vocab_path, "w") as f:
        json.dump(vocab, f)
    print(f"[export] Vocab -> {vocab_path}")


def convert():
    print(f"[convert] Loading {MODEL_NAME}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME)
    model.eval()

    # Export vocab for Swift tokenizer
    export_vocab(tokenizer, PROJECT_ROOT / "native" / "ios" / "PersonalLayer" / "Resources")

    # Dummy input for tracing
    dummy_text = "This is a sample sentence for tracing the model."
    inputs = tokenizer(dummy_text, return_tensors="pt", padding="max_length", max_length=MAX_LENGTH, truncation=True)
    input_ids = inputs["input_ids"]
    attention_mask = inputs["attention_mask"]

    # Trace model
    print("[convert] Tracing model...")
    traced = torch.jit.trace(lambda ids, mask: model(ids, attention_mask=mask).last_hidden_state.mean(dim=1),
                             (input_ids, attention_mask))

    # Convert to Core ML
    print("[convert] Converting to Core ML...")
    mlmodel = ct.convert(
        traced,
        inputs=[
            ct.TensorType(name="input_ids", shape=input_ids.shape, dtype=int),
            ct.TensorType(name="attention_mask", shape=attention_mask.shape, dtype=int),
        ],
        outputs=[ct.TensorType(name="embeddings")],
        compute_units=ct.ComputeUnit.ALL,
        minimum_deployment_target=ct.target.iOS16,
    )

    dest = PROJECT_ROOT / "native" / "ios" / "PersonalLayer" / "Resources" / "all-MiniLM-L6-v2.mlpackage"
    mlmodel.save(str(dest))
    print(f"[convert] Saved -> {dest}")

    print("[convert] Done.")


if __name__ == "__main__":
    convert()
