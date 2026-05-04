"""
signal_extractor.py

Local on-device extraction of minimal persona signals from raw text.
Raw text is NEVER stored. Only extracted signals are saved.

Extracts:
  - Programming languages mentioned
  - Frameworks / tools / libraries
  - Task category (debugging, building, learning, reviewing, deploying)
  - Domain (web, mobile, data, devops, ai/ml, security)

All regex-based — no LLM call, no network, runs in microseconds.
"""

import re
from collections import Counter


# ── Tech keyword dictionaries ──

LANGUAGES = {
    "python", "javascript", "typescript", "rust", "go", "java", "kotlin",
    "swift", "ruby", "c++", "cpp", "c#", "csharp", "php", "scala", "r",
    "sql", "bash", "shell", "powershell", "html", "css", "dart", "elixir",
    "haskell", "lua", "julia", "zig",
}

FRAMEWORKS = {
    # web
    "react", "nextjs", "next.js", "vue", "angular", "svelte", "fastapi",
    "django", "flask", "express", "rails", "laravel", "spring", "nuxt",
    "remix", "astro", "tailwind",
    # data / ml
    "pytorch", "tensorflow", "keras", "sklearn", "scikit-learn", "pandas",
    "numpy", "huggingface", "langchain", "llamaindex", "openai", "anthropic",
    # infra
    "docker", "kubernetes", "k8s", "terraform", "ansible", "nginx",
    "postgresql", "postgres", "mysql", "sqlite", "redis", "mongodb",
    "supabase", "prisma",
    # tools
    "git", "github", "graphql", "rest", "grpc", "kafka", "celery",
    "airflow", "dbt", "spark", "mcp", "claude", "cursor", "vscode",
}

TASK_PATTERNS = {
    "debugging":  [r"\bbug\b", r"\berror\b", r"\bfix\b", r"\bcrash\b",
                   r"\bfailing\b", r"\btraceback\b", r"\bexception\b",
                   r"\bnot working\b", r"\bbroken\b"],
    "building":   [r"\bbuild\b", r"\bcreate\b", r"\bimplement\b", r"\badd\b",
                   r"\bfeature\b", r"\bwrite\b", r"\bgenerate\b", r"\bmake\b"],
    "learning":   [r"\bhow (do|does|to)\b", r"\bexplain\b", r"\bwhat is\b",
                   r"\bwhat are\b", r"\blearn\b", r"\bunderstand\b", r"\bwhy\b"],
    "reviewing":  [r"\breview\b", r"\brefactor\b", r"\boptimize\b",
                   r"\bimprove\b", r"\bclean\b", r"\bbetter way\b"],
    "deploying":  [r"\bdeploy\b", r"\bproduction\b", r"\bci/cd\b", r"\bpipeline\b",
                   r"\bdocker\b", r"\bkubernetes\b", r"\bserverless\b"],
}

DOMAINS = {
    "ai_ml":     [r"\bllm\b", r"\bai\b", r"\bml\b", r"\bmodel\b", r"\bembedding\b",
                  r"\bvector\b", r"\bagent\b", r"\bprompt\b", r"\bfine.?tun"],
    "web":       [r"\bapi\b", r"\bfrontend\b", r"\bbackend\b", r"\bhttp\b",
                  r"\bwebhook\b", r"\brest\b", r"\bgraphql\b"],
    "data":      [r"\bdatabase\b", r"\bquery\b", r"\bpipeline\b", r"\betl\b",
                  r"\banalytics\b", r"\bdashboard\b", r"\bsql\b"],
    "devops":    [r"\bdocker\b", r"\bkubernetes\b", r"\bci/cd\b", r"\bdeploy\b",
                  r"\binfra\b", r"\bterraform\b", r"\bcloud\b"],
    "security":  [r"\bauth\b", r"\boauth\b", r"\btoken\b", r"\bencrypt\b",
                  r"\bsecurity\b", r"\bvulnerability\b", r"\bpermission\b"],
}


def extract_signals(text: str) -> dict:
    """
    Given raw text (prompt / code / content), extract minimal persona signals.
    Returns a dict. Raw text is not stored anywhere.
    """
    if not text:
        return {}

    t = text.lower()

    # Languages
    found_langs = [lang for lang in LANGUAGES if re.search(rf"\b{re.escape(lang)}\b", t)]

    # Frameworks
    found_frameworks = [fw for fw in FRAMEWORKS if re.search(rf"\b{re.escape(fw)}\b", t)]

    # Task category
    task_scores: Counter = Counter()
    for task, patterns in TASK_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, t, re.IGNORECASE):
                task_scores[task] += 1
    top_task = task_scores.most_common(1)[0][0] if task_scores else "general"

    # Domain
    domain_scores: Counter = Counter()
    for domain, patterns in DOMAINS.items():
        for pat in patterns:
            if re.search(pat, t, re.IGNORECASE):
                domain_scores[domain] += 1
    top_domain = domain_scores.most_common(1)[0][0] if domain_scores else "general"

    signals = {
        "languages":   found_langs[:5],
        "frameworks":  found_frameworks[:8],
        "task":        top_task,
        "domain":      top_domain,
    }

    # Only return non-empty signals
    return {k: v for k, v in signals.items() if v and v != "general"}


def signals_to_content(signals: dict, source: str) -> str:
    """Format extracted signals as a short readable string for storage."""
    parts = []
    if signals.get("task"):
        parts.append(f"task:{signals['task']}")
    if signals.get("domain"):
        parts.append(f"domain:{signals['domain']}")
    if signals.get("languages"):
        parts.append("langs:" + ",".join(signals["languages"]))
    if signals.get("frameworks"):
        parts.append("tools:" + ",".join(signals["frameworks"]))
    return f"[{source}] " + " | ".join(parts) if parts else ""
