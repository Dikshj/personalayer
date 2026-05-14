#!/usr/bin/env python3
"""
Convert Hugging Face all-MiniLM-L6-v2 to Core ML (mlmodelc).
Requires: transformers, sentence-transformers, coremltools, torch

Usage:
    python scripts/convert-coreml-model.py
    # Output: native/ios/PersonalLayer/Resources/Models/all-MiniLM-L6-v2.mlmodelc
"""
import sys
import os
import json

try:
    from sentence_transformers import SentenceTransformer
    import coremltools as ct
    import torch
    import numpy as np
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install: pip install sentence-transformers coremltools torch transformers")
    sys.exit(1)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "native", "ios", "PersonalLayer", "Resources", "Models")
OUTPUT_NAME = "all-MiniLM-L6-v2"

def main():
    print(f"Loading {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    
    # Wrap the PyTorch model for tracing
    class Wrapper(torch.nn.Module):
        def __init__(self, st_model):
            super().__init__()
            self.st_model = st_model
        
        def forward(self, input_ids, attention_mask):
            # SentenceTransformer uses AutoModel for encoding
            outputs = self.st_model[0].auto_model(input_ids=input_ids, attention_mask=attention_mask)
            # Mean pooling
            token_embeddings = outputs.last_hidden_state
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
            sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            embeddings = sum_embeddings / sum_mask
            # Normalize
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
            return embeddings

    wrapper = Wrapper(model)
    wrapper.eval()

    # Tokenizer for example input
    tokenizer = model.tokenizer
    example_text = "This is an example sentence for tracing."
    encoded = tokenizer(example_text, padding="max_length", truncation=True, max_length=128, return_tensors="pt")
    input_ids = encoded["input_ids"]
    attention_mask = encoded["attention_mask"]

    print("Tracing model...")
    with torch.no_grad():
        traced = torch.jit.trace(wrapper, (input_ids, attention_mask))

    print("Converting to Core ML...")
    mlmodel = ct.convert(
        traced,
        inputs=[
            ct.TensorType(name="input_ids", shape=input_ids.shape, dtype=int),
            ct.TensorType(name="attention_mask", shape=attention_mask.shape, dtype=int)
        ],
        outputs=[ct.TensorType(name="embeddings")],
        minimum_deployment_target=ct.target.iOS16,
        compute_units=ct.ComputeUnit.ALL
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"{OUTPUT_NAME}.mlpackage")
    mlmodel.save(output_path)
    print(f"Saved Core ML package to: {output_path}")
    
    # Also compile to mlmodelc for runtime loading
    compiled_path = os.path.join(OUTPUT_DIR, f"{OUTPUT_NAME}.mlmodelc")
    os.system(f'xcrun coremlc compile "{output_path}" "{compiled_path}"')
    print(f"Compiled model to: {compiled_path}")
    
    # Save tokenizer vocab for runtime tokenization
    vocab_path = os.path.join(OUTPUT_DIR, "vocab.json")
    with open(vocab_path, "w") as f:
        json.dump(tokenizer.get_vocab(), f)
    print(f"Saved vocab to: {vocab_path}")

if __name__ == "__main__":
    main()
