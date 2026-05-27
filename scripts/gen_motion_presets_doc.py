#!/usr/bin/env python3
"""
从 common/motion_presets.py 自动生成 docs/project/motion.md 中的“微动预设列表”片段。

用法：
  python scripts/gen_motion_presets_doc.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


START = "<!-- MOTION_PRESETS_START -->"
END = "<!-- MOTION_PRESETS_END -->"


def _fmt(value):
    if value is None:
        return ""
    if isinstance(value, float):
        # 保持文档可读性：最多 3 位小数，去掉尾随 0
        s = f"{value:.3f}".rstrip("0").rstrip(".")
        return s
    return str(value)


def build_snippet() -> str:
    from common.motion_presets import MOTION_PRESETS, MOTION_PRESET_ALIASES  # type: ignore

    lines: list[str] = []
    lines.append("")
    lines.append("> 本段由 `scripts/gen_motion_presets_doc.py` 自动生成，请勿手改。")
    lines.append("")
    lines.append("| preset | 中文 | linear | lateral | angular | duration | angle_deg | pause_after |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|")

    for key in sorted(MOTION_PRESETS.keys()):
        item = MOTION_PRESETS[key] or {}
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{key}`",
                    _fmt(item.get("label") or ""),
                    _fmt(item.get("linear")),
                    _fmt(item.get("lateral")),
                    _fmt(item.get("angular")),
                    _fmt(item.get("duration")),
                    _fmt(item.get("angle_deg")),
                    _fmt(item.get("pause_after")),
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("**常用中文别名（节选）**")
    lines.append("")
    # 只展示一部分更常用的，避免太长；需要完整别名可直接看源码
    hot = [
        "走一步",
        "快走一步",
        "半步",
        "后退一步",
        "左移一步",
        "右移一步",
        "左转15°",
        "右转15°",
        "左转90°",
        "右转90°",
    ]
    for name in hot:
        target = MOTION_PRESET_ALIASES.get(name)
        if target:
            lines.append(f"- `{name}` → `{target}`")

    lines.append("")
    return "\n".join(lines)


def update_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise SystemExit(f"未找到标记区：{START} / {END} in {path}")
    before, rest = text.split(START, 1)
    _, after = rest.split(END, 1)
    snippet = build_snippet()
    next_text = before + START + snippet + END + after
    if next_text == text:
        return False
    path.write_text(next_text, encoding="utf-8")
    return True


def main():
    target = ROOT / "docs" / "project" / "motion.md"
    changed = update_file(target)
    print("updated" if changed else "no change", target)


if __name__ == "__main__":
    main()

