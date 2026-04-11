import io
from flask import Blueprint, request, jsonify
import pdfplumber
from services.ai_parser import parse_text

parse_bp = Blueprint("parse", __name__)


@parse_bp.route("/api/parse", methods=["POST"])
def parse_trip():
    text = None

    if "file" in request.files:
        file = request.files["file"]
        if file.filename.lower().endswith(".pdf"):
            pdf_bytes = file.read()
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
                text = "\n".join(pages)
        else:
            text = file.read().decode("utf-8")
    elif request.json and "text" in request.json:
        text = request.json["text"]

    if not text or not text.strip():
        return jsonify({"error": "No text or file provided"}), 400

    try:
        result = parse_text(text)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
