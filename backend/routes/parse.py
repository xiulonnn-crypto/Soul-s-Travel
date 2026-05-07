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
            img_bytes = file.read()
            ext = '.' + fname.rsplit('.', 1)[-1].lower()
            mime = _MIME_MAP.get(ext, 'image/jpeg')

            # 默认走本地 OCR + PiTravel 解析器（无云端密钥依赖）。
            # 仅当用户显式配置了 AI_API_KEY 时才走 Vision API 路径作为备选。
            if os.environ.get('AI_API_KEY'):
                from services.image_parser import parse_image
                try:
                    return jsonify(parse_image(img_bytes, mime))
                except RuntimeError as e:
                    return jsonify({"error": str(e)}), 400
                except Exception as e:
                    return jsonify({"error": f"图片识别失败: {e}"}), 500

            from services.image_extractor import extract_text_from_image
            from services.planner_parser import parse_planner_text
            # 可选的年份上下文：前端在"已经存在行程数据"时（如 PDF 已解析完再传 JPG）
            # 会把当前行程的年份带上来，避免 PiTravel 海报缺年份时默认推成当前年。
            ctx_year_raw = request.form.get('context_year', '').strip()
            ctx_year = None
            if ctx_year_raw.isdigit():
                y = int(ctx_year_raw)
                if 1900 <= y <= 2100:
                    ctx_year = y
            try:
                ocr_text = extract_text_from_image(img_bytes)
                return jsonify(parse_planner_text(ocr_text, context_year=ctx_year))
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            except RuntimeError as e:
                return jsonify({"error": str(e)}), 400
            except Exception as e:
                return jsonify({"error": f"本地图片识别失败: {e}"}), 500

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

    from urllib.parse import urlparse
    hostname = urlparse(url).hostname or ''

    # ── PiTravel (圆周旅迹) ── JSON API，无需 Playwright
    if 'pitravel.cn' in hostname:
        from services.url_scraper import scrape_pitravel_api
        from services.ai_parser import parse_pitravel_api
        try:
            journey_data = scrape_pitravel_api(url)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": f"抓取失败: {e}"}), 502
        try:
            result = parse_pitravel_api(journey_data)
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": f"解析失败: {e}"}), 500

    # ── 穷游 (qyer) ── Playwright 抓取
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
