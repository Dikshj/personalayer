// signal-extractor.js
// Shared by all LLM content scripts.
// Extracts minimal signals from prompt text. Raw text never sent to backend.

const LANGUAGES = [
  "python","javascript","typescript","rust","go","java","kotlin",
  "swift","ruby","cpp","c#","php","scala","bash","sql","html","css","dart",
];

const FRAMEWORKS = [
  "react","nextjs","vue","angular","svelte","fastapi","django","flask",
  "express","rails","pytorch","tensorflow","langchain","openai","anthropic",
  "docker","kubernetes","postgresql","sqlite","redis","mongodb","tailwind",
  "mcp","claude","cursor","prisma","supabase","graphql",
];

const TASK_PATTERNS = {
  debugging: /\b(bug|error|fix|crash|fail|broken|traceback|exception|not working)\b/i,
  building:  /\b(build|create|implement|add feature|write|generate|make)\b/i,
  learning:  /\b(how (do|does|to)|explain|what is|what are|learn|understand|why)\b/i,
  reviewing: /\b(review|refactor|optimize|improve|clean up|better way)\b/i,
  deploying: /\b(deploy|production|ci.?cd|pipeline|serverless|release)\b/i,
};

const DOMAIN_PATTERNS = {
  ai_ml:    /\b(llm|ai\b|ml\b|model|embedding|vector|agent|fine.?tun|rag)\b/i,
  web:      /\b(api|frontend|backend|http|webhook|rest|graphql|endpoint)\b/i,
  data:     /\b(database|query|pipeline|etl|analytics|dashboard|sql)\b/i,
  devops:   /\b(docker|kubernetes|ci.?cd|deploy|infra|terraform|cloud)\b/i,
  security: /\b(auth|oauth|token|encrypt|security|vulnerability|permission)\b/i,
};

function extractSignals(text) {
  if (!text || text.length < 10) return null;

  const t = text.toLowerCase();

  const langs = LANGUAGES.filter(l => new RegExp(`\\b${l}\\b`).test(t));
  const tools = FRAMEWORKS.filter(f => new RegExp(`\\b${f.replace('.','\\.')}\\b`).test(t));

  let task = "general";
  for (const [name, pat] of Object.entries(TASK_PATTERNS)) {
    if (pat.test(text)) { task = name; break; }
  }

  let domain = "general";
  for (const [name, pat] of Object.entries(DOMAIN_PATTERNS)) {
    if (pat.test(text)) { domain = name; break; }
  }

  const parts = [];
  if (task !== "general")   parts.push(`task:${task}`);
  if (domain !== "general") parts.push(`domain:${domain}`);
  if (langs.length)         parts.push(`langs:${langs.slice(0,4).join(",")}`);
  if (tools.length)         parts.push(`tools:${tools.slice(0,6).join(",")}`);

  return parts.length ? parts.join(" | ") : null;
}

// Export for content scripts (loaded via manifest before LLM scripts)
window.__plExtractSignals = extractSignals;
