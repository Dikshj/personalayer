import hashlib
import math
import re
import struct


DIMENSION = 384


def embed_label(label: str) -> list[float]:
    vector = [0.0] * DIMENSION
    tokens = _tokens(label)
    for token in tokens:
        _add_hash(vector, token, 1.0)
    for index in range(max(0, len(tokens) - 1)):
        _add_hash(vector, f"{tokens[index]} {tokens[index + 1]}", 0.7)
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def serialize_embedding(values: list[float]) -> bytes:
    if len(values) != DIMENSION:
        raise ValueError("embedding_dimension_mismatch")
    return struct.pack(f"<{DIMENSION}f", *values)


def deserialize_embedding(blob: bytes | None) -> list[float]:
    if not blob:
        return []
    return list(struct.unpack(f"<{DIMENSION}f", blob))


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def _tokens(label: str) -> list[str]:
    raw = re.sub(r"[^a-z0-9]+", " ", str(label).lower())
    return [_normalize_token(token) for token in raw.split() if token]


def _normalize_token(token: str) -> str:
    if token.endswith("ies") and len(token) > 5:
        return f"{token[:-3]}y"
    if token.endswith("s") and not token.endswith("ss") and len(token) > 4:
        return token[:-1]
    return token


def _add_hash(vector: list[float], token: str, weight: float) -> None:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    index = int.from_bytes(digest[:2], "big") % DIMENSION
    sign = 1.0 if digest[2] % 2 == 0 else -1.0
    vector[index] += sign * weight
