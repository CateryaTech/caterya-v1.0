"""Pack the whole repository into ONE markdown file (path header + fenced code per file) for copy-paste.

    python scripts/bundle_markdown.py > caterya-v1.0_ALL_FILES.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".caterya", "build", "dist", ".venv"}
SKIP_FILES = {"LICENSE"}            # Apache-2.0 text: use GitHub's license picker or https://www.apache.org/licenses/LICENSE-2.0.txt
LANG = {".py": "python", ".md": "markdown", ".json": "json", ".toml": "toml", ".yml": "yaml", ".yaml": "yaml",
        ".html": "html", ".cff": "yaml", ".ini": "ini"}


def files() -> list[Path]:
    out = []
    for p in sorted(ROOT.rglob("*")):
        rel = p.relative_to(ROOT)
        if p.is_file() and not (set(rel.parts) & SKIP_DIRS) and not any(x.endswith(".egg-info") for x in rel.parts) \
                and rel.name not in SKIP_FILES and not rel.name.endswith(".pyc"):
            out.append(p)
    return out


def main() -> None:
    fs = files()
    w = sys.stdout.write
    w("# CATERYA AI ASSURANCE INFRASTRUCTURE — complete repository (copy-paste edition)\n\n")
    w("Repository `cateryatech/caterya-v1.0`. Each section below is one file: create the path shown and paste the content of the code block.\n"
      "Missing from this document: `LICENSE` (Apache-2.0 — add it with GitHub's license picker).\n\n## File index\n\n")
    for i, p in enumerate(fs, 1):
        w(f"{i}. `{p.relative_to(ROOT)}`\n")
    for p in fs:
        text = p.read_text(encoding="utf-8")
        fence = "`" * max(4, max((len(m) for m in re.findall(r"`+", text)), default=0) + 1)
        w(f"\n---\n\n### `{p.relative_to(ROOT)}`\n\n{fence}{LANG.get(p.suffix, '')}\n{text.rstrip(chr(10))}\n{fence}\n")


if __name__ == "__main__":
    main()
