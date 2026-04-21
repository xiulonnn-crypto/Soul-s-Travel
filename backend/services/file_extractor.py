"""File text extraction: PDF (pymupdf4llm primary + pdfplumber/pdfminer.six
fallback) and DOCX / XLSX / PPTX / HTML via optional converters.

PDF primary: https://github.com/pymupdf/PyMuPDF (pymupdf4llm), AGPL-3.0.
  Clean PUA-char handling, no char-doubling, native Markdown emit.
  BUT its layout analyzer does not reconstruct the 穷游 overview-page table
  (where numbered `1. 景点名` anchors live), so we blend in pdfplumber's
  page-0 output as a supplement.

PDF fallback: pdfplumber hybrid (table-region detection) + pdfminer.six
  full-document extraction. Strategy ported from Microsoft markitdown's
  PdfConverter (MIT License). Retained as a pure fallback for PDFs that
  pymupdf4llm cannot open or produces empty output for.
"""

import io
import os
import re
from typing import Optional

import pdfminer.high_level
import pdfplumber

try:
    import pymupdf
    import pymupdf4llm

    _PYMUPDF_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised when optional dep absent
    _PYMUPDF_AVAILABLE = False

SUPPORTED_DOC_EXTS = {'.pdf', '.docx', '.xlsx', '.pptx', '.html', '.htm', '.csv'}


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes for parse_text() consumption.

    Strategy:
      1. Primary: pymupdf4llm (markdown) + pdfplumber page-0 overview,
         both funneled through markdown_to_plain. Produces cleaner
         detail/expense text (no doubled chars) while keeping the
         overview-table numbered-attraction anchors the parser needs.
      2. Fallback: pdfplumber hybrid -> pdfminer.six full extract.
    """
    if _PYMUPDF_AVAILABLE:
        try:
            text = _extract_via_pymupdf4llm(pdf_bytes)
            if text and _has_expected_anchors(text):
                return text
        except Exception:
            pass  # fall through to legacy path

    buf = io.BytesIO(pdf_bytes)
    try:
        raw = _hybrid_extract(buf)
    except Exception:
        buf.seek(0)
        raw = pdfminer.high_level.extract_text(buf)
    return markdown_to_plain(raw)


# ---------------------------------------------------------------------------
# pymupdf4llm primary path
# ---------------------------------------------------------------------------

_DAY_MARKER_RE = re.compile(r'\n(\d{2})\s+星期[一二三四五六日天]')


def _has_expected_anchors(text: str) -> bool:
    """Parse_text relies on day markers of the form '\\nNN 星期X' or
    '\\nNN\\n星期X' appearing in the overview section. Confirm at least one
    day marker is present before trusting the new-path output."""
    if _DAY_MARKER_RE.search(text):
        return True
    # Also accept the doubled/newline variant
    return bool(re.search(r'\n(\d{2})\n\s*星期[一二三四五六日天]', text))


def _extract_via_pymupdf4llm(pdf_bytes: bytes) -> str:
    """Primary path: pymupdf4llm markdown + pdfplumber page-0 overview,
    joined and flattened via markdown_to_plain.

    The overview supplement is prepended because its numbered '1. 景点名'
    rows are the anchor source for `_extract_activities` and the DAY
    headers are the anchor source for `_split_by_day`. pymupdf4llm alone
    doesn't reconstruct those anchors from the overview table.
    """
    # Full-document pass via pymupdf4llm (clean PUA / no doubled chars)
    doc = pymupdf.open(stream=pdf_bytes, filetype='pdf')
    try:
        pm_md = pymupdf4llm.to_markdown(doc, show_progress=False)
    finally:
        doc.close()
    pm_md = _adapt_pymupdf4llm_output(pm_md)

    # Overview page supplement (pdfplumber sees the overview table structure
    # that pymupdf4llm misses — numbered attractions + cross-day day markers).
    overview = _extract_overview_via_pdfplumber(pdf_bytes)

    combined = (overview + '\n\n' + pm_md) if overview else pm_md
    return markdown_to_plain(combined)


def _adapt_pymupdf4llm_output(md: str) -> str:
    """Post-process pymupdf4llm markdown so parse_text's anchors match.

    Fixes observed on 穷游 PDFs:
      - Stray space in expense headers (`第4 天` -> `第4天`).
      - Stray spaces around ¥ and the parenthesized total.
      - Markdown hotel links `[Name](url)` -> `Name`.
    """
    # Remove markdown link syntax while keeping anchor text.
    md = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', md)
    # `第4 天` -> `第4天` (pymupdf sometimes inserts a space between digit and 天)
    md = re.sub(r'第(\d+)\s+天', r'第\1天', md)
    return md


def _extract_overview_via_pdfplumber(pdf_bytes: bytes) -> str:
    """Extract ONLY page 0 (overview) of the PDF via pdfplumber. Returns
    markdown-ish text compatible with markdown_to_plain. Returns '' on any
    failure — caller falls back to pymupdf4llm output alone."""
    buf = io.BytesIO(pdf_bytes)
    try:
        with pdfplumber.open(buf) as pdf:
            if not pdf.pages:
                return ''
            page = pdf.pages[0]
            page_content = _extract_form_content(page)
            if page_content is not None and page_content.strip():
                return page_content
            text = page.extract_text() or ''
            return text.strip()
    except Exception:
        return ''


def extract_text_from_pdf_raw(pdf_bytes: bytes) -> str:
    """Extract text preserving markdown table structure (for direct table parsing)."""
    buf = io.BytesIO(pdf_bytes)
    try:
        return _hybrid_extract(buf)
    except Exception:
        buf.seek(0)
        return pdfminer.high_level.extract_text(buf)


def _hybrid_extract(buf: io.BytesIO) -> str:
    """Per-page hybrid: table pages via pdfplumber words, text pages via pdfminer."""
    chunks = []
    form_page_count = 0

    with pdfplumber.open(buf) as pdf:
        for page in pdf.pages:
            page_content = _extract_form_content(page)
            if page_content is not None:
                form_page_count += 1
                if page_content.strip():
                    chunks.append(page_content)
            else:
                text = page.extract_text()
                if text and text.strip():
                    chunks.append(text.strip())
            page.close()

    if form_page_count == 0:
        buf.seek(0)
        return pdfminer.high_level.extract_text(buf)

    return "\n\n".join(chunks).strip()


# ---------------------------------------------------------------------------
# Form / table detection (ported from markitdown _pdf_converter.py)
# ---------------------------------------------------------------------------

def _extract_form_content(page) -> Optional[str]:
    """Detect form/table layout by word positions; return text with markdown
    tables for structured regions, or None if page is plain text."""
    words = page.extract_words(keep_blank_chars=True, x_tolerance=3, y_tolerance=3)
    if not words:
        return None

    y_tol = 5
    rows_by_y = {}
    for w in words:
        y_key = round(w["top"] / y_tol) * y_tol
        rows_by_y.setdefault(y_key, []).append(w)

    sorted_y = sorted(rows_by_y.keys())
    page_width = page.width if hasattr(page, "width") else 612

    row_info = []
    for y_key in sorted_y:
        row_words = sorted(rows_by_y[y_key], key=lambda w: w["x0"])
        if not row_words:
            continue
        first_x0 = row_words[0]["x0"]
        last_x1 = row_words[-1]["x1"]
        line_width = last_x1 - first_x0
        combined = " ".join(w["text"] for w in row_words)

        x_groups = []
        for x in sorted(w["x0"] for w in row_words):
            if not x_groups or x - x_groups[-1] > 50:
                x_groups.append(x)

        is_para = line_width > page_width * 0.55 and len(combined) > 60
        row_info.append({
            "y_key": y_key, "words": row_words, "text": combined,
            "x_groups": x_groups, "is_paragraph": is_para,
            "num_columns": len(x_groups),
        })

    all_table_x = []
    for info in row_info:
        if info["num_columns"] >= 3 and not info["is_paragraph"]:
            all_table_x.extend(info["x_groups"])
    if not all_table_x:
        return None

    all_table_x.sort()
    gaps = [all_table_x[i + 1] - all_table_x[i]
            for i in range(len(all_table_x) - 1)
            if all_table_x[i + 1] - all_table_x[i] > 5]

    if gaps and len(gaps) >= 3:
        sorted_gaps = sorted(gaps)
        idx70 = int(len(sorted_gaps) * 0.70)
        adaptive_tol = max(25, min(50, sorted_gaps[idx70]))
    else:
        adaptive_tol = 35

    global_cols = []
    for x in all_table_x:
        if not global_cols or x - global_cols[-1] > adaptive_tol:
            global_cols.append(x)

    if len(global_cols) <= 1:
        return None

    content_width = global_cols[-1] - global_cols[0]
    avg_col_w = content_width / len(global_cols)
    if avg_col_w < 30:
        return None
    cols_per_inch = len(global_cols) / (content_width / 72)
    if cols_per_inch > 10:
        return None
    adaptive_max = max(15, int(20 * (page_width / 612)))
    if len(global_cols) > adaptive_max:
        return None

    num_cols = len(global_cols)
    for info in row_info:
        if info["is_paragraph"]:
            info["is_table_row"] = False
            continue
        aligned = set()
        for w in info["words"]:
            for ci, cx in enumerate(global_cols):
                if abs(w["x0"] - cx) < 40:
                    aligned.add(ci)
                    break
        info["is_table_row"] = len(aligned) >= 2

    table_regions = []
    i = 0
    while i < len(row_info):
        if row_info[i]["is_table_row"]:
            start = i
            while i < len(row_info) and row_info[i]["is_table_row"]:
                i += 1
            table_regions.append((start, i))
        else:
            i += 1

    total_table_rows = sum(e - s for s, e in table_regions)
    if len(row_info) > 0 and total_table_rows / len(row_info) < 0.2:
        return None

    def _cells(info):
        cells = [""] * num_cols
        for w in info["words"]:
            col = num_cols - 1
            for ci in range(num_cols - 1):
                if w["x0"] < global_cols[ci + 1] - 20:
                    col = ci
                    break
            cells[col] = (cells[col] + " " + w["text"]).strip() if cells[col] else w["text"]
        return cells

    lines = []
    idx = 0
    while idx < len(row_info):
        region = None
        for s, e in table_regions:
            if idx == s:
                region = (s, e)
                break
        if region:
            s, e = region
            table = [_cells(row_info[j]) for j in range(s, e)]
            lines.append(_to_markdown_table(table))
            idx = e
        else:
            in_table = any(s < idx < e for s, e in table_regions)
            if not in_table:
                lines.append(row_info[idx]["text"])
            idx += 1

    return "\n".join(lines)


def _to_markdown_table(table: list) -> str:
    if not table:
        return ""
    table = [[c or "" for c in row] for row in table]
    table = [row for row in table if any(c.strip() for c in row)]
    if not table:
        return ""
    col_widths = [max(len(str(c)) for c in col) for col in zip(*table)]
    col_widths = [max(w, 3) for w in col_widths]

    def fmt(row):
        return "| " + " | ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(row)) + " |"

    header, *rows = table
    md = [fmt(header)]
    md.append("| " + " | ".join("-" * w for w in col_widths) + " |")
    for row in rows:
        md.append(fmt(row))
    return "\n".join(md)


# ---------------------------------------------------------------------------
# Markdown → plain text (compatibility layer for existing parse_text engine)
# ---------------------------------------------------------------------------

_MD_TABLE_ROW = re.compile(r'^\|(.+)\|$')
_MD_TABLE_SEP = re.compile(r'^\|[\s\-|]+\|$')
_MD_HEADING = re.compile(r'^#{1,6}\s+')


def parse_markdown_tables(md_text: str) -> list:
    """Extract structured tables from markdown text.
    Returns list of tables, each table is a list of dicts (column_name → value)."""
    tables = []
    lines = md_text.split('\n')
    i = 0
    while i < len(lines):
        if _MD_TABLE_ROW.match(lines[i]) and i + 1 < len(lines) and _MD_TABLE_SEP.match(lines[i + 1]):
            headers = [c.strip() for c in lines[i].strip('|').split('|')]
            i += 2  # skip header + separator
            rows = []
            while i < len(lines) and _MD_TABLE_ROW.match(lines[i]) and not _MD_TABLE_SEP.match(lines[i]):
                cells = [c.strip() for c in lines[i].strip('|').split('|')]
                row = {}
                for j, h in enumerate(headers):
                    row[h] = cells[j] if j < len(cells) else ''
                rows.append(row)
                i += 1
            if rows:
                tables.append(rows)
        else:
            i += 1
    return tables


def markdown_to_plain(md_text: str) -> str:
    """Strip markdown formatting to produce plain text compatible with
    the existing parse_text() regex engine."""
    lines = md_text.split('\n')
    out = []
    for line in lines:
        if _MD_TABLE_SEP.match(line):
            continue
        if _MD_TABLE_ROW.match(line):
            cells = [c.strip() for c in line.strip('|').split('|')]
            out.append('  '.join(c for c in cells if c))
            continue
        line = _MD_HEADING.sub('', line)
        out.append(line)
    return '\n'.join(out)


# ---------------------------------------------------------------------------
# Multi-format extraction (DOCX / XLSX / PPTX / HTML / CSV)
# ---------------------------------------------------------------------------

def extract_text_from_file(file_bytes: bytes, extension: str) -> str:
    """Extract plain text from a supported document format."""
    ext = extension.lower()
    if ext == '.pdf':
        return extract_text_from_pdf(file_bytes)
    if ext == '.docx':
        return _extract_docx(file_bytes)
    if ext == '.xlsx':
        return _extract_xlsx(file_bytes)
    if ext == '.pptx':
        return _extract_pptx(file_bytes)
    if ext in ('.html', '.htm'):
        return _extract_html(file_bytes)
    if ext == '.csv':
        return file_bytes.decode('utf-8', errors='replace')
    raise ValueError(f"不支持的文件类型: {ext}")


def _extract_docx(data: bytes) -> str:
    try:
        import mammoth
    except ImportError:
        raise RuntimeError("需要安装 mammoth 才能解析 DOCX 文件: pip3 install mammoth")
    result = mammoth.convert_to_markdown(io.BytesIO(data))
    return markdown_to_plain(result.value)


def _extract_xlsx(data: bytes) -> str:
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("需要安装 openpyxl 才能解析 XLSX 文件: pip3 install openpyxl")
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    lines = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) if c is not None else '' for c in row]
            if any(c.strip() for c in cells):
                lines.append('  '.join(cells))
    wb.close()
    return '\n'.join(lines)


def _extract_pptx(data: bytes) -> str:
    try:
        from pptx import Presentation
    except ImportError:
        raise RuntimeError("需要安装 python-pptx 才能解析 PPTX 文件: pip3 install python-pptx")
    prs = Presentation(io.BytesIO(data))
    lines = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        lines.append(text)
    return '\n'.join(lines)


def _extract_html(data: bytes) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise RuntimeError("需要安装 beautifulsoup4 才能解析 HTML 文件: pip3 install beautifulsoup4")
    soup = BeautifulSoup(data, 'html.parser')
    for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
        tag.decompose()
    return soup.get_text(separator='\n', strip=True)
