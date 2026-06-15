from __future__ import annotations

import re
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import database
from database import insert_control_center_audit
from pcl.embeddings import cosine_similarity, deserialize_embedding, embed_label, serialize_embedding


DEFAULT_MEMORY_SCOPES = [
    "profile",
    "preferences",
    "people",
    "projects",
    "daily-log",
    "scratchpad",
    "voice",
    "priorities",
    "boundaries",
    "decision-style",
    "work-style",
    "disliked-behaviors",
]

_SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def list_memory_files(user_id: str = "local_user") -> list[dict]:
    base = memory_user_dir(user_id)
    ensure_default_memory_files(user_id)
    files = []
    for path in sorted(base.glob("*.md")):
        scope = path.stem
        stat = path.stat()
        files.append({
            "scope": scope,
            "path": str(path),
            "bytes": stat.st_size,
            "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })
    return files


def read_memory_file(user_id: str, scope: str) -> dict:
    path = memory_file_path(user_id, scope)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_default_content(scope), encoding="utf-8")
    stat = path.stat()
    return {
        "user_id": user_id,
        "scope": normalize_scope(scope),
        "content": path.read_text(encoding="utf-8"),
        "bytes": stat.st_size,
        "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


def write_memory_file(
    user_id: str,
    scope: str,
    content: str,
    source: str = "manual",
    reason: str = "",
) -> dict:
    path = memory_file_path(user_id, scope)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = prune_memory_content(content)
    path.write_text(content, encoding="utf-8")
    memory = read_memory_file(user_id, scope)
    rebuild_memory_index(user_id, scope)
    insert_control_center_audit(
        user_id=user_id,
        action="memory_written",
        target_type="markdown_memory",
        target_id=memory["scope"],
        details={"source": source, "reason": reason, "bytes": memory["bytes"]},
    )
    return memory


def append_memory_entry(
    user_id: str,
    scope: str,
    entry: str,
    heading: Optional[str] = None,
    source: str = "manual",
    reason: str = "",
) -> dict:
    entry = entry.strip()
    memory = read_memory_file(user_id, scope)
    current = memory["content"].rstrip()
    if _memory_contains_entry(current, entry):
        insert_control_center_audit(
            user_id=user_id,
            action="memory_deduped",
            target_type="markdown_memory",
            target_id=memory["scope"],
            details={"source": source, "reason": reason},
        )
        return memory
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    title = heading.strip() if heading else timestamp
    if heading and _section_exists(current, title):
        next_content = _replace_section(current, title, entry)
    else:
        next_content = f"{current}\n\n## {title}\n\n{entry}\n"
    return write_memory_file(user_id, scope, next_content, source=source, reason=reason)


def delete_memory_file(user_id: str, scope: str, reason: str = "") -> dict:
    path = memory_file_path(user_id, scope)
    normalized_scope = normalize_scope(scope)
    existed = path.exists()
    if existed:
        path.unlink()
    delete_memory_index(user_id, normalized_scope)
    insert_control_center_audit(
        user_id=user_id,
        action="memory_forgotten",
        target_type="markdown_memory",
        target_id=normalized_scope,
        details={"reason": reason, "existed": existed},
    )
    return {"user_id": user_id, "scope": normalized_scope, "deleted": existed}


def search_memory(
    user_id: str,
    query: str,
    scopes: Optional[list[str]] = None,
    limit: int = 10,
) -> dict:
    tokens = {token for token in re.findall(r"[a-z0-9]+", query.lower()) if len(token) > 1}
    if not tokens:
        return {"user_id": user_id, "query": query, "mode": "hybrid", "results": []}
    query_embedding = embed_label(query)
    indexed = search_memory_index(user_id, query, scopes=scopes, limit=limit)
    if indexed["results"]:
        return indexed
    selected_scopes = scopes or [item["scope"] for item in list_memory_files(user_id)]
    results = []
    for scope in selected_scopes:
        memory = read_memory_file(user_id, scope)
        lines = memory["content"].splitlines()
        for index, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            line_tokens = set(re.findall(r"[a-z0-9]+", line.lower()))
            overlap = tokens & line_tokens
            semantic_score = cosine_similarity(query_embedding, embed_label(line))
            keyword_score = len(overlap)
            combined = keyword_score + semantic_score
            if keyword_score or semantic_score >= 0.18:
                results.append({
                    "scope": memory["scope"],
                    "line": index,
                    "text": line,
                    "score": round(combined, 4),
                    "keyword_score": keyword_score,
                    "semantic_score": round(semantic_score, 4),
                    "quality": memory_quality(user_id, memory["scope"], updated_at=memory["updated_at"]),
                })

    results.sort(key=lambda item: (-item["score"], item["scope"], item["line"]))
    return {
        "user_id": user_id,
        "query": query,
        "mode": "hybrid",
        "results": results[: max(1, min(limit, 50))],
    }


def decay_memory_confidence(user_id: str, scopes: Optional[list[str]] = None) -> dict:
    selected_scopes = scopes or [item["scope"] for item in list_memory_files(user_id)]
    scores = []
    for scope in selected_scopes:
        memory = read_memory_file(user_id, scope)
        quality = memory_quality(user_id, memory["scope"], updated_at=memory["updated_at"])
        decayed_score = round(quality["confidence"] * quality["freshness"], 4)
        scores.append(database.upsert_memory_quality_score(
            user_id=user_id,
            scope=memory["scope"],
            confidence=quality["confidence"],
            freshness=quality["freshness"],
            source_count=quality["source_count"],
            score=decayed_score,
        ))
    insert_control_center_audit(
        user_id=user_id,
        action="memory_confidence_decayed",
        target_type="markdown_memory",
        target_id=",".join(selected_scopes[:20]),
        details={"scopes": selected_scopes, "count": len(scores)},
    )
    return {"user_id": user_id, "scores": scores}


def ensure_default_memory_files(user_id: str = "local_user") -> dict:
    created = []
    for scope in DEFAULT_MEMORY_SCOPES:
        path = memory_file_path(user_id, scope)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_default_content(scope), encoding="utf-8")
            created.append(scope)
    return {"user_id": user_id, "created": created, "total": len(DEFAULT_MEMORY_SCOPES)}


def rebuild_memory_index(user_id: str, scope: Optional[str] = None) -> dict:
    scopes = [normalize_scope(scope)] if scope else [item["scope"] for item in list_memory_files(user_id)]
    indexed = 0
    with database.get_connection() as conn:
        for current_scope in scopes:
            conn.execute(
                "DELETE FROM memory_search_index WHERE user_id = ? AND scope = ?",
                (user_id, current_scope),
            )
            memory = read_memory_file(user_id, current_scope)
            for line_number, line in enumerate(memory["content"].splitlines(), start=1):
                text = line.strip()
                if not text or text.startswith("#"):
                    continue
                tokens = sorted(_line_tokens(text))
                conn.execute(
                    """INSERT OR REPLACE INTO memory_search_index
                       (id, user_id, scope, line_number, text, tokens, embedding)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid.uuid4()),
                        user_id,
                        current_scope,
                        line_number,
                        text,
                        json.dumps(tokens),
                        serialize_embedding(embed_label(text)),
                    ),
                )
                indexed += 1
        conn.commit()
    return {"user_id": user_id, "scopes": scopes, "indexed": indexed}


def delete_memory_index(user_id: str, scope: str) -> int:
    with database.get_connection() as conn:
        deleted = conn.execute(
            "DELETE FROM memory_search_index WHERE user_id = ? AND scope = ?",
            (user_id, scope),
        ).rowcount
        conn.commit()
    return deleted


def search_memory_index(
    user_id: str,
    query: str,
    scopes: Optional[list[str]] = None,
    limit: int = 10,
) -> dict:
    query_tokens = _line_tokens(query)
    query_embedding = embed_label(query)
    params: list[object] = [user_id]
    where = "WHERE user_id = ?"
    if scopes:
        normalized = [normalize_scope(scope) for scope in scopes]
        placeholders = ",".join("?" for _ in normalized)
        where += f" AND scope IN ({placeholders})"
        params.extend(normalized)
    with database.get_connection() as conn:
        rows = conn.execute(
            f"""SELECT * FROM memory_search_index
                {where}
                ORDER BY updated_at DESC
                LIMIT 1000""",
            params,
        ).fetchall()
    results = []
    for row in rows:
        row_tokens = set(json.loads(row["tokens"] or "[]"))
        keyword_score = len(query_tokens & row_tokens)
        semantic_score = cosine_similarity(query_embedding, deserialize_embedding(row["embedding"]))
        score = keyword_score + semantic_score
        if keyword_score or semantic_score >= 0.18:
            results.append({
                "scope": row["scope"],
                "line": row["line_number"],
                "text": row["text"],
                "score": round(score, 4),
                "keyword_score": keyword_score,
                "semantic_score": round(semantic_score, 4),
                "quality": memory_quality(user_id, row["scope"], updated_at=row["updated_at"]),
            })
    results.sort(key=lambda item: (-item["score"], item["scope"], item["line"]))
    return {
        "user_id": user_id,
        "query": query,
        "mode": "indexed_hybrid",
        "results": results[: max(1, min(limit, 50))],
    }


def memory_quality(user_id: str, scope: str, updated_at: str = "") -> dict:
    source_count = 0
    sources: set[str] = set()
    normalized_scope = normalize_scope(scope)
    try:
        with database.get_connection() as conn:
            rows = conn.execute(
                """SELECT details FROM control_center_audit
                   WHERE user_id = ? AND target_type = 'markdown_memory' AND target_id = ?
                   ORDER BY created_at DESC
                   LIMIT 100""",
                (user_id, normalized_scope),
            ).fetchall()
        for row in rows:
            details = json.loads(row["details"] or "{}")
            source = str(details.get("source") or "").strip()
            if source:
                sources.add(source)
    except Exception:
        sources = set()
    source_count = len(sources)
    age_days = _age_days(updated_at)
    freshness = max(0.0, min(1.0, 1.0 - (age_days / 90.0)))
    confidence = min(1.0, 0.45 + (0.1 * min(source_count, 4)) + (0.2 * freshness))
    return {
        "confidence": round(confidence, 3),
        "freshness": round(freshness, 3),
        "age_days": round(age_days, 2),
        "source_count": source_count,
        "sources": sorted(sources)[:8],
    }


def prune_memory_file(user_id: str, scope: str) -> dict:
    memory = read_memory_file(user_id, scope)
    pruned = prune_memory_content(memory["content"])
    removed = len(memory["content"].splitlines()) - len(pruned.splitlines())
    if pruned != memory["content"]:
        write_memory_file(user_id, scope, pruned, source="pruning", reason="remove duplicate or outdated memory")
    return {"user_id": user_id, "scope": normalize_scope(scope), "removed_lines": max(0, removed)}


def prune_memory_content(content: str) -> str:
    lines = content.splitlines()
    output = []
    seen_facts = set()
    previous_blank = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if not previous_blank:
                output.append("")
            previous_blank = True
            continue
        previous_blank = False
        if _is_outdated_line(stripped):
            continue
        if stripped.startswith("#"):
            output.append(line.rstrip())
            continue
        key = _fact_key(stripped)
        if key in seen_facts:
            continue
        seen_facts.add(key)
        output.append(line.rstrip())
    return "\n".join(output).rstrip() + "\n"


def memory_user_dir(user_id: str) -> Path:
    safe_user_id = _safe_segment(user_id, label="user_id")
    return database.DATA_DIR / "memory" / safe_user_id


def memory_file_path(user_id: str, scope: str) -> Path:
    return memory_user_dir(user_id) / f"{normalize_scope(scope)}.md"


def normalize_scope(scope: str) -> str:
    return _safe_segment(scope, label="scope")


def _safe_segment(value: str, label: str) -> str:
    normalized = (value or "").strip().lower().replace(" ", "-")
    # Map characters outside the safe set (e.g. the ':' in Supabase user ids
    # like "supabase:<uuid>") to '-' so any authenticated user maps to a valid,
    # collision-free filesystem segment.
    normalized = re.sub(r"[^a-z0-9_-]", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    normalized = normalized[:64]
    if not _SAFE_NAME.fullmatch(normalized):
        raise ValueError(f"invalid_{label}")
    return normalized


def _default_content(scope: str) -> str:
    title = normalize_scope(scope).replace("-", " ").title()
    return f"# {title}\n\nNo confirmed memory yet.\n"


def _memory_contains_entry(content: str, entry: str) -> bool:
    return _fact_key(entry) in {_fact_key(line) for line in content.splitlines() if line.strip() and not line.startswith("#")}


def _section_exists(content: str, heading: str) -> bool:
    return f"## {heading.strip()}" in content


def _replace_section(content: str, heading: str, entry: str) -> str:
    lines = content.splitlines()
    marker = f"## {heading.strip()}"
    output = []
    index = 0
    replaced = False
    while index < len(lines):
        if lines[index].strip() == marker:
            output.append(lines[index])
            output.append("")
            output.extend(entry.strip().splitlines())
            replaced = True
            index += 1
            while index < len(lines) and not lines[index].startswith("## "):
                index += 1
            continue
        output.append(lines[index])
        index += 1
    if not replaced:
        output.extend(["", marker, "", entry.strip()])
    return "\n".join(output).rstrip() + "\n"


def _line_tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 1}


def _fact_key(value: str) -> str:
    tokens = sorted(_line_tokens(value))
    return " ".join(tokens)


def _age_days(updated_at: str) -> float:
    if not updated_at:
        return 90.0
    try:
        raw = updated_at.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 86400)
    except Exception:
        return 90.0


def _is_outdated_line(value: str) -> bool:
    lower = value.lower()
    return any(marker in lower for marker in [
        "not relevant anymore",
        "no longer relevant",
        "obsolete",
        "outdated",
        "deprecated memory",
    ])
