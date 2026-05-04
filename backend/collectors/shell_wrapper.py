"""
collectors/shell_wrapper.py

Generates shell alias wrappers for CLI LLM tools.
Aliases intercept the first argument (the prompt) and log it to
PersonaLayer before passing everything through to the real command.

Usage:
  python -m collectors.shell_wrapper --install

This appends alias definitions to your ~/.bashrc or ~/.zshrc.
After install:
  source ~/.bashrc   (or restart terminal)

Wrapped commands: claude, aider, opencode, sgpt, llm, ai
"""

import sys
import os
import subprocess
from pathlib import Path

ALIASES = {
    "claude": "claude",
    "aider": "aider",
    "opencode": "opencode",
    "sgpt": "sgpt",      # shell-gpt
    "llm": "llm",        # Simon Willison's llm CLI
    "ai": "ai",          # generic
}

PERSONALAYER_ENDPOINT = "http://localhost:7823/feed-event"


def generate_bash_wrapper(cmd: str) -> str:
    """
    Generate a bash function that logs the first positional arg
    (the prompt) before calling the real command.
    """
    return f"""
# PersonaLayer wrapper for {cmd}
{cmd}() {{
  local _prompt="$1"
  if [ -n "$_prompt" ] && command -v curl &>/dev/null; then
    curl -s -X POST {PERSONALAYER_ENDPOINT} \\
      -H "Content-Type: application/json" \\
      -d "{{\\\"source\\\":\\\"{cmd}\\\",\\\"content_type\\\":\\\"prompt\\\",\\\"content\\\":\\\"${{_prompt:0:1000}}\\\",\\\"author\\\":\\\"user\\\",\\\"url\\\":\\\"terminal://{cmd}\\\",\\\"timestamp\\\":$(date +%s)000}}" \\
      &>/dev/null &
  fi
  command {cmd} "$@"
}}
"""


def install_aliases() -> None:
    """Append wrappers to ~/.bashrc and ~/.zshrc if they exist."""
    home = Path.home()
    rc_files = [home / ".bashrc", home / ".zshrc", home / ".bash_profile"]
    rc_files = [f for f in rc_files if f.exists()]

    if not rc_files:
        print("No .bashrc / .zshrc found. Create one and re-run.")
        return

    block_start = "# === PersonaLayer LLM wrappers START ==="
    block_end   = "# === PersonaLayer LLM wrappers END ==="

    wrappers = "\n".join(generate_bash_wrapper(cmd) for cmd in ALIASES)
    block = f"\n{block_start}\n{wrappers}\n{block_end}\n"

    for rc in rc_files:
        content = rc.read_text()
        if block_start in content:
            print(f"{rc.name}: wrappers already installed (skipping)")
            continue
        with open(rc, "a") as f:
            f.write(block)
        print(f"{rc.name}: PersonaLayer wrappers installed ✓")

    print("\nRun: source ~/.bashrc  (or restart terminal)")
    print("PersonaLayer will now capture prompts from:", ", ".join(ALIASES.keys()))


def remove_aliases() -> None:
    """Remove PersonaLayer wrapper blocks from RC files."""
    home = Path.home()
    rc_files = [home / ".bashrc", home / ".zshrc", home / ".bash_profile"]
    block_start = "# === PersonaLayer LLM wrappers START ==="
    block_end   = "# === PersonaLayer LLM wrappers END ==="

    for rc in [f for f in rc_files if f.exists()]:
        content = rc.read_text()
        if block_start not in content:
            continue
        lines = content.split("\n")
        inside = False
        cleaned = []
        for line in lines:
            if block_start in line:
                inside = True
                continue
            if block_end in line:
                inside = False
                continue
            if not inside:
                cleaned.append(line)
        rc.write_text("\n".join(cleaned))
        print(f"{rc.name}: wrappers removed ✓")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Install/remove PersonaLayer shell wrappers for CLI LLMs"
    )
    parser.add_argument("--install", action="store_true", help="Install aliases")
    parser.add_argument("--remove",  action="store_true", help="Remove aliases")
    args = parser.parse_args()

    if args.remove:
        remove_aliases()
    else:
        install_aliases()
