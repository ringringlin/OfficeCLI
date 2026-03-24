#!/usr/bin/env python3
"""
Generate Styles/index.json from Styles/*/style.md.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional


STYLE_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
META_LINE_RE = re.compile(r"^\s*-\s*\*\*(.+?)\*\*:\s*(.+?)\s*$", re.MULTILINE)
SPLIT_COMMA_RE = re.compile(r"\s*[,;/、，；]\s*")
LEADING_NOISE_RE = re.compile(r"^[A-Za-z]?\d+[-\s_]*", re.ASCII)


def normalize_style_name(raw_title: str) -> str:
    if "—" in raw_title:
        left, right = [x.strip() for x in raw_title.split("—", 1)]
        candidate = right if right else left
    else:
        candidate = raw_title.strip()
    candidate = LEADING_NOISE_RE.sub("", candidate).strip()
    return candidate or raw_title.strip()


def parse_meta(style_text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for key, value in META_LINE_RE.findall(style_text):
        norm_key = key.strip().lower().replace(" ", "")
        result[norm_key] = value.strip()
    return result


def split_tags(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [x.strip() for x in SPLIT_COMMA_RE.split(value) if x.strip()]


def pick_build_script(style_dir: Path) -> Optional[str]:
    for candidate in ("build.sh", "build.py", "build.ps1", "build.json"):
        if (style_dir / candidate).exists():
            return candidate
    return None


def build_style_record(style_dir: Path, styles_root: Path) -> Dict[str, object]:
    style_id = style_dir.name
    palette = style_id.split("--", 1)[0] if "--" in style_id else "unknown"
    style_md = style_dir / "style.md"
    text = style_md.read_text(encoding="utf-8")

    heading_match = STYLE_HEADING_RE.search(text)
    heading = heading_match.group(1).strip() if heading_match else style_id
    meta = parse_meta(text)

    best_for_raw = (
        meta.get("bestfor")
        or meta.get("scene")
        or meta.get("scenario")
        or ""
    )
    mood_raw = meta.get("mood") or ""
    tone_raw = meta.get("tone") or meta.get("colortone") or ""

    build_script_name = pick_build_script(style_dir)
    pptx_files = sorted([p.name for p in style_dir.glob("*.pptx")])

    rel_prefix = style_dir.relative_to(styles_root.parent).as_posix()
    record: Dict[str, object] = {
        "id": style_id,
        "name": normalize_style_name(heading),
        "heading": heading,
        "palette": palette,
        "best_for": split_tags(best_for_raw),
        "best_for_text": best_for_raw,
        "mood": split_tags(mood_raw),
        "mood_text": mood_raw,
        "tone": tone_raw,
        "style_md": f"{rel_prefix}/style.md",
        "build_script": f"{rel_prefix}/{build_script_name}" if build_script_name else None,
        "pptx_files": [f"{rel_prefix}/{x}" for x in pptx_files],
    }
    return record


def generate_index(styles_root: Path) -> Dict[str, object]:
    style_dirs = sorted(
        [p for p in styles_root.iterdir() if p.is_dir() and (p / "style.md").exists()],
        key=lambda p: p.name,
    )
    styles = [build_style_record(style_dir, styles_root) for style_dir in style_dirs]

    grouped: Dict[str, int] = {}
    for style in styles:
        palette = str(style["palette"])
        grouped[palette] = grouped.get(palette, 0) + 1

    return {
        "schema_version": 1,
        "total_styles": len(styles),
        "palettes": grouped,
        "styles": styles,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Styles/index.json from style.md files.")
    parser.add_argument("--styles-dir", default="Styles", help="Styles root directory (default: Styles)")
    parser.add_argument("--output", default="Styles/index.json", help="Output json path (default: Styles/index.json)")
    parser.add_argument("--check", action="store_true", help="Check mode: fail if output is not up to date")
    args = parser.parse_args()

    repo_root = Path.cwd()
    styles_root = (repo_root / args.styles_dir).resolve()
    out_path = (repo_root / args.output).resolve()

    if not styles_root.exists():
        raise SystemExit(f"Styles directory not found: {styles_root}")

    payload = generate_index(styles_root)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"

    if args.check:
        if not out_path.exists():
            print(f"[FAIL] Missing generated file: {out_path}")
            return 1
        current = out_path.read_text(encoding="utf-8")
        if current != rendered:
            print(f"[FAIL] {out_path} is out of date. Run:")
            print("  python3 scripts/generate_style_index.py")
            return 1
        print(f"[OK] {out_path} is up to date.")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")
    print(f"[OK] Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
