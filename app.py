# app.py

import os
import re
import json
import tempfile
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify
import pandas as pd
import fitz  # PyMuPDF
import mimetypes
import google.generativeai as genai

# === CONFIGURATION ===
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")  # secure via env var
genai.configure(api_key=GOOGLE_API_KEY)

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash-latest",
    generation_config={
        "temperature": 0.1,
        "top_p": 1,
        "top_k": 32,
        "max_output_tokens": 4096,
    },
    safety_settings=[
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]
)

# === FLASK APP ===
app = Flask(__name__)

# === PROMPTS ===
system_prompt = """
You are an expert in reading Indian Delivery Challans.
Your task is to extract structured information from delivery challans.
"""

user_prompt = """
You are reading an Indian Delivery Challan PDF.

Extract the following fields in a JSON list of one object with these exact keys:

- "Date of Pullback": Leave blank if not available
- "Date of Invoice": The date mentioned as Invoice Date
- "Date of Delivery": Leave blank if not available
- "Invoice No. Challan No.": Value next to 'Invoice#'
- "SC No.": Value next to 'SC#'
- "LR No.": Value next to 'L.R.No.' if found
- "Equipment Name": Product or equipment name from the Description (e.g., Logiq P9)
- "Serial No. of main unit": Serial number(s) of the main equipment
- "Qty of Units": Quantity under the 'Qty' field for main unit
- "Qty of Probes": Count of distinct probe models mentioned in description
- "Pick up address": Address from the “Dispatched From” or Customer section
- "Status": Leave blank
- "Delivery Location": Address under “Place of Delivery” section
- "Serial No. of Probes": List of individual serial numbers for all probes
- "Serial Nos.": All serial numbers mentioned in the goods description

Return only a JSON array with one object containing these keys.
If a field is not clearly available, return it as an empty string "".
Do not include any extra text, explanation, or markdown formatting.
"""

# === HELPERS ===
def parse_json_from_response(response_text):
    match = re.search(r'\[.*\]', response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None

def extract_text_from_pdf(pdf_path):
    results = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=300)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as img_file:
                img_path = img_file.name
                pix.save(img_path)

            mime_type, _ = mimetypes.guess_type(img_path)
            img_data = Path(img_path).read_bytes()
            try:
                response = model.generate_content([
                    system_prompt,
                    {"mime_type": mime_type, "data": img_data},
                    user_prompt
                ])
                if response.text:
                    results.append(response.text)
            except Exception as e:
                print(f"❌ Error on page {i}: {e}")
            finally:
                os.remove(img_path)
    return results

@app.route("/")
def home():
    return "✅ Gemini FIRC Extractor API is live"

@app.route("/extract", methods=["POST"])
def extract():
    if 'file' not in request.files:
        return jsonify({"error": "Missing PDF file"}), 400

    pdf_file = request.files['file']
    if not pdf_file.filename.endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported."}), 400

    # Save PDF to a temp file and close it before processing
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
    os.close(tmp_fd)
    pdf_file.save(tmp_path)

    try:
        responses = extract_text_from_pdf(tmp_path)
        data = []
        for res in responses:
            parsed = parse_json_from_response(res)
            if parsed:
                data.extend(parsed)
        return jsonify({"status": "success", "data": data})
    finally:
        os.unlink(tmp_path)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
