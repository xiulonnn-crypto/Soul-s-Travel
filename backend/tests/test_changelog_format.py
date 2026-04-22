"""CHANGELOG.md 面向用户的书写规范守护。

这份 linter 把 `CLAUDE.md` 里记录的 CHANGELOG 四条铁律的可机械化部分
固化下来，防止 0.1.0-002 那种「开发者日志化」的改动悄悄回潮：

1. **粗体子标题**：除 `[Unreleased]` 外，每个版本块里所有 `- ` 起手的
   bullet 行必须形如 `- **子标题**：正文`（中文或 ASCII 冒号均可）。
2. **无代码文件标识符**：bullet 里禁止出现反引号包裹的 `*.py`、
   `*.jsx`、`*.tsx`、`*.vue`、`*.ts`、`*.js`、`*.json` 等代码文件名。
3. **无函数调用签名**：bullet 里禁止出现反引号包裹的 `func(...)` 样式
   的函数/方法签名。
4. **版本头规范**：`## [x.y.z] - YYYY-MM-DD [- 主题摘要]`；主题摘要若
   存在，不得残留粗体 `**…**`（防止把 bullet 的 `**子标题**：…` 半句话
   误粘到标题里）。允许使用全角冒号等普通标点作为句内分隔。

非机械化的部分（库名、内部变量名、敏感测试数量等）由人工/AI review
依据 CLAUDE.md 的 CHANGELOG 章节把关，linter 不介入。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHANGELOG_PATH = ROOT / "CHANGELOG.md"

_RE_VERSION_HEADING = re.compile(
    r"^## \[(?P<ver>[^\]]+)\](?:\([^)]*\))?(?P<rest>.*)$",
)

_RE_BULLET_WITH_BOLD_TITLE = re.compile(
    r"^-\s+\*\*[^*\n]+\*\*\s*[：:]",
)

# 反引号内含禁用的代码文件扩展名
_RE_BANNED_CODE_FILE = re.compile(
    r"`[^`\n]*\.(?:py|pyi|jsx|tsx|vue|ts|js|mjs|cjs|json|toml|yaml|yml)(?:[:#][^`]*)?`",
)

# 反引号内含 `func(...)` 形式的函数/方法签名
_RE_BANNED_FUNC_CALL = re.compile(
    r"`[^`\n]*[A-Za-z_]\w*\([^`\n]*\)[^`\n]*`",
)


def _load_changelog() -> str:
    assert CHANGELOG_PATH.exists(), f"CHANGELOG.md 不存在：{CHANGELOG_PATH}"
    return CHANGELOG_PATH.read_text(encoding="utf-8")


def _iter_release_blocks(content: str):
    """切分出每个 `## [version]` 块，跳过 `[Unreleased]`。

    逐块 yield (version, heading_line, body) 三元组；body 不含自身标题行，
    到下一个 `## [` 或文档底部锚点（`[Unreleased]:`）为止。
    """
    lines = content.splitlines()
    current_ver: str | None = None
    current_heading: str | None = None
    current_body: list[str] = []

    for line in lines:
        m = _RE_VERSION_HEADING.match(line)
        # 底部链接锚点区（`[Unreleased]: https://...`）也以 `## ` 之外的形式出现，
        # 无需特殊处理：_RE_VERSION_HEADING 不会匹配。
        if m:
            if current_ver is not None and current_ver.lower() != "unreleased":
                yield current_ver, current_heading, "\n".join(current_body)
            current_ver = m.group("ver").strip()
            current_heading = line
            current_body = []
        else:
            if current_ver is not None:
                current_body.append(line)

    if current_ver is not None and current_ver.lower() != "unreleased":
        yield current_ver, current_heading, "\n".join(current_body)


def _iter_bullets(body: str):
    """产出 body 中所有 `- ` 起手的 bullet 行（保留前导 `- `）。

    仅取顶层 bullet：缩进 bullet 归属上一条，通常是延续性描述，不单独
    校验子标题（它们由父 bullet 承载子标题）。
    """
    for line in body.splitlines():
        if line.startswith("- "):
            yield line


@pytest.fixture(scope="module")
def release_blocks():
    content = _load_changelog()
    return list(_iter_release_blocks(content))


def test_changelog_has_at_least_one_release(release_blocks):
    assert release_blocks, "CHANGELOG.md 应至少包含一个已发布版本块"


def test_every_released_bullet_has_bold_subtitle(release_blocks):
    violations: list[str] = []
    for ver, _heading, body in release_blocks:
        for bullet in _iter_bullets(body):
            if not _RE_BULLET_WITH_BOLD_TITLE.match(bullet):
                violations.append(f"[{ver}] {bullet}")

    assert not violations, (
        "以下 bullet 缺少 `- **粗体子标题**：...` 起手格式：\n  "
        + "\n  ".join(violations)
    )


def test_no_banned_code_file_identifiers_in_released_bullets(release_blocks):
    violations: list[str] = []
    for ver, _heading, body in release_blocks:
        for bullet in _iter_bullets(body):
            for m in _RE_BANNED_CODE_FILE.finditer(bullet):
                violations.append(f"[{ver}] {m.group(0)}  ← 整行：{bullet}")

    assert not violations, (
        "CHANGELOG bullet 中禁止出现反引号包裹的代码文件名，"
        "应改写为面向用户的功能描述：\n  "
        + "\n  ".join(violations)
    )


def test_no_banned_func_call_signatures_in_released_bullets(release_blocks):
    violations: list[str] = []
    for ver, _heading, body in release_blocks:
        for bullet in _iter_bullets(body):
            for m in _RE_BANNED_FUNC_CALL.finditer(bullet):
                violations.append(f"[{ver}] {m.group(0)}  ← 整行：{bullet}")

    assert not violations, (
        "CHANGELOG bullet 中禁止出现反引号包裹的函数/方法签名："
        "\n  " + "\n  ".join(violations)
    )


def test_version_heading_summary_is_plain_text(release_blocks):
    """版本头摘要不得残留粗体或全角冒号（防止把 bullet 半句话误当摘要）。"""
    violations: list[str] = []
    for ver, heading, _body in release_blocks:
        m = _RE_VERSION_HEADING.match(heading)
        rest = m.group("rest") if m else ""
        # rest 形如 ` - 2026-04-22 - 主题摘要`；剥离日期段后剩下摘要
        after_date = re.sub(r"^\s*-\s*\d{4}-\d{2}-\d{2}\s*", "", rest)
        summary = after_date.lstrip("-").strip()
        if not summary:
            continue
        if "**" in summary:
            violations.append(f"[{ver}] 标题摘要残留粗体：{summary!r}")

    assert not violations, (
        "版本头主题摘要不得残留 bullet 的粗体子标题 `**…**`，"
        "应为纯文本摘要：\n  "
        + "\n  ".join(violations)
    )
