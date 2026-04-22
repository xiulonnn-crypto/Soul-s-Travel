#!/usr/bin/env python3
"""CHANGELOG 版本自动更新脚本

由 `.githooks/pre-push` 调用，在推送前把 `[Unreleased]` 区块晋升为版本块。

用法：
    python3 bump_changelog.py [NEXT_VERSION]

    NEXT_VERSION  显式指定版本号（如 0.2.0），省略则按以下规则自动递增：
                  0.1.0 → 0.1.0-002 → 0.1.0-003 → ...
                  NEXT_VERSION=0.2.0 重置基础版本 → 0.2.0 → 0.2.0-002 → ...

面向 AI 协作者的规范（与 `CLAUDE.md` 的 CHANGELOG 章节保持一致）：
    · 每条 bullet 必须是 `- **粗体子标题**：1–3 句面向用户的描述`
    · 严禁代码标识符（文件名、函数名、库名、类名、配置键）与敏感技术栈信息
    · 版本头格式：`## [x.y.z] - YYYY-MM-DD - 一句话主题摘要`
      摘要为纯文本，不带粗体、不带全角冒号；本脚本自动剥离 `feat:` 等
      Conventional Commits 前缀，以免技术前缀泄漏到面向用户的标题里。

本脚本只做版本头迁移与清洗，不校验内容合规；内容合规由
`backend/tests/test_changelog_format.py` 的 linter 测试守护。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Optional, Tuple

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CHANGELOG_PATH = PROJECT_ROOT / "CHANGELOG.md"

_RE_UNRELEASED_HEADING = re.compile(
    r"## \[Unreleased\](?:\([^)]*\))?",
    re.IGNORECASE,
)

_RE_VERSION_HEADING = re.compile(
    r"## \[(\d+\.\d+\.\d+(?:-\d{3})?)\](?:\([^)]*\))?",
)

# 误写进 [Unreleased] 的 `> Theme: ...` 引用块；晋升时必须剥离，避免
# 遗留到新 released block 头顶造成摘要重复。
_RE_THEME_AFTER_UNRELEASED = re.compile(
    r"(## \[Unreleased\](?:\([^)]*\))?[ \t]*\n)"
    r"([ \t]*\n)+"
    r">[ \t]*Theme:[^\n]*\n"
    r"(?:[ \t]*\n)?",
    re.IGNORECASE,
)

# Conventional Commits 前缀：feat / fix / chore / docs / refactor / test /
# style / perf / build / ci / revert，可带 scope 与 `!` 破坏性标记。
_RE_CC_PREFIX = re.compile(
    r"^(?:feat|fix|chore|docs|refactor|test|style|perf|build|ci|revert)"
    r"(?:\([^)]+\))?"
    r"!?"
    r":\s*",
    re.IGNORECASE,
)


def read_changelog() -> str:
    return CHANGELOG_PATH.read_text(encoding="utf-8")


def write_changelog(content: str) -> None:
    CHANGELOG_PATH.write_text(content, encoding="utf-8")


def has_unreleased_content(content: str) -> bool:
    m = _RE_UNRELEASED_HEADING.search(content)
    if not m:
        return False

    after = content[m.end():]
    next_ver = _RE_VERSION_HEADING.search(after)
    section = after[: next_ver.start()] if next_ver else after

    lines = [ln.strip() for ln in section.splitlines() if ln.strip()]
    return bool(lines)


def get_latest_version(content: str) -> Optional[str]:
    matches = _RE_VERSION_HEADING.findall(content)
    return matches[0] if matches else None


def strip_theme_after_unreleased(content: str) -> str:
    """晋升前删除紧跟 `[Unreleased]` 的 `> Theme: ...` 引用块。"""
    m = _RE_THEME_AFTER_UNRELEASED.search(content)
    if not m:
        return content
    replacement = m.group(1) + "\n"
    return content[: m.start()] + replacement + content[m.end():]


def strip_commit_prefix(subject: str) -> str:
    """剥离 `feat:` / `fix(scope):` / `refactor!:` 等 Conventional Commits 前缀。"""
    return _RE_CC_PREFIX.sub("", subject, count=1)


def compute_next_version(latest: Optional[str], explicit: Optional[str]) -> str:
    if explicit:
        return explicit.lstrip("v")

    if latest is None:
        return "0.1.0"

    m = re.match(r"^(\d+\.\d+\.\d+)(?:-(\d+))?$", latest)
    if not m:
        return latest + "-002"

    base, suffix = m.group(1), m.group(2)
    return f"{base}-002" if suffix is None else f"{base}-{int(suffix) + 1:03d}"


def get_commit_summary() -> str:
    """取本次推送新增提交的一句话摘要，用于版本头主题。"""
    def _run(args):
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=5)
            return r.stdout.strip() if r.returncode == 0 else ""
        except Exception:
            return ""

    for remote_ref in ("origin/main", "origin/master"):
        out = _run(["git", "log", f"{remote_ref}..HEAD", "--oneline", "--no-decorate"])
        if out:
            lines = out.splitlines()
            summary = re.sub(r"^[a-f0-9]+ ", "", lines[0])
            if len(lines) > 1:
                summary += f"（共 {len(lines)} 个提交）"
            return summary

    out = _run(["git", "log", "--oneline", "-1", "--no-decorate"])
    return re.sub(r"^[a-f0-9]+ ", "", out) if out else "日常更新"


def build_unreleased_heading() -> str:
    return "## [Unreleased]"


def build_version_heading(new_ver: str, today: str, summary: Optional[str] = None) -> str:
    heading = f"## [{new_ver}] - {today}"
    if summary:
        heading += f" - {summary}"
    return heading


def bump(explicit_version: Optional[str] = None) -> Optional[Tuple[str, str]]:
    content = read_changelog()

    if not has_unreleased_content(content):
        print("[CHANGELOG] [Unreleased] 部分无内容，跳过版本更新")
        return None

    content = strip_theme_after_unreleased(content)

    prev_ver = get_latest_version(content)
    new_ver = compute_next_version(prev_ver, explicit_version)
    today = date.today().isoformat()
    if explicit_version:
        summary = None
    else:
        raw = get_commit_summary()
        summary = strip_commit_prefix(raw) if raw else raw

    unreleased_heading = build_unreleased_heading()
    version_heading = build_version_heading(new_ver, today, summary)

    old_unreleased = _RE_UNRELEASED_HEADING.search(content)
    if not old_unreleased:
        print("[CHANGELOG] 未找到 [Unreleased] 标题，跳过")
        return None

    new_block = f"{unreleased_heading}\n\n{version_heading}"
    content = content[: old_unreleased.start()] + new_block + content[old_unreleased.end():]

    write_changelog(content)

    msg = f"[CHANGELOG] 已更新 [{new_ver}] - {today}"
    if summary:
        msg += f"  |  {summary}"
    print(msg)

    return new_ver, summary


if __name__ == "__main__":
    explicit = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("NEXT_VERSION")
    )
    bump(explicit)
    sys.exit(0)
