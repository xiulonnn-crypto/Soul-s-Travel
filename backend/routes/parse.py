import os

from flask import Blueprint, request, jsonify
from services.ai_parser import parse_text
from services.file_extractor import extract_text_from_file, SUPPORTED_DOC_EXTS

parse_bp = Blueprint("parse", __name__)

_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
_MIME_MAP = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
    '.webp': 'image/webp', '.gif': 'image/gif', '.bmp': 'image/bmp',
}


def _is_image(filename: str) -> bool:
    return any(filename.lower().endswith(ext) for ext in _IMAGE_EXTS)


@parse_bp.route("/api/parse", methods=["POST"])
def parse_trip():
    text = None

    if "file" in request.files:
        file = request.files["file"]
        fname = file.filename or ''

        if _is_image(fname):
            from services.image_parser import parse_image
            img_bytes = file.read()
            ext = '.' + fname.rsplit('.', 1)[-1].lower()
            mime = _MIME_MAP.get(ext, 'image/jpeg')
            try:
                result = parse_image(img_bytes, mime)
                return jsonify(result)
            except RuntimeError as e:
                return jsonify({"error": str(e)}), 400
            except Exception as e:
                return jsonify({"error": f"图片识别失败: {e}"}), 500

        ext = os.path.splitext(fname)[1].lower()
        if ext in SUPPORTED_DOC_EXTS:
            try:
                text = extract_text_from_file(file.read(), ext)
            except RuntimeError as e:
                return jsonify({"error": str(e)}), 400
        elif ext == '.txt':
            text = file.read().decode("utf-8")
        else:
            text = file.read().decode("utf-8", errors="replace")
    elif request.json and "text" in request.json:
        text = request.json["text"]

    if not text or not text.strip():
        return jsonify({"error": "No text or file provided"}), 400

    try:
        result = parse_text(text)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@parse_bp.route("/api/parse/url", methods=["POST"])
def parse_url():
    data = request.json or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "缺少 url 参数"}), 400

    from services.url_scraper import scrape_qyer_url
    from services.ai_parser import parse_qyer_web

    try:
        text = scrape_qyer_url(url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"抓取失败: {e}"}), 502

    try:
        result = parse_qyer_web(text)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"解析失败: {e}"}), 500
