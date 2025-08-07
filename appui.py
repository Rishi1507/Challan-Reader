# streamlit_app.py

import os
import requests
import pandas as pd
import streamlit as st
from datetime import datetime

# === CONFIG ===
API_ENDPOINT = "https://challan-reader.onrender.com/extract"

st.set_page_config(page_title="FIRC Extractor", layout="centered")
st.title("📄 Delivery Challan Extractor")

st.markdown("Upload one or more Delivery Challan PDFs. Data will be extracted and returned in Excel format.")

uploaded_files = st.file_uploader("Upload PDF Files", type="pdf", accept_multiple_files=True)

if st.button("Extract and Download Excel") and uploaded_files:
    all_data = []
    for file in uploaded_files:
        st.write(f"🔍 Processing `{file.name}`...")
        try:
            files = {"file": (file.name, file.read(), "application/pdf")}
            response = requests.post(API_ENDPOINT, files=files)
            response.raise_for_status()
            data = response.json().get("data", [])
            for entry in data:
                entry["Filename"] = file.name
            all_data.extend(data)
        except Exception as e:
            st.error(f"❌ Failed to process {file.name}: {e}")

    if all_data:
        df = pd.DataFrame(all_data)
        df.insert(0, "Sr No.", range(1, len(df) + 1))
        filename = f"challan_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df.to_excel(filename, index=False)
        with open(filename, "rb") as f:
            st.success("✅ Extraction complete.")
            st.download_button("📥 Download Excel", f.read(), file_name=filename)
        os.remove(filename)
    else:
        st.warning("No data extracted from uploaded PDFs.")
