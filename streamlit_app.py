# streamlit_app.py
import streamlit as st
import pandas as pd
import io
import re

# optional plotly
try:
    import plotly.express as px
    PLOTLY = True
except Exception:
    PLOTLY = False

st.set_page_config(page_title="Analisis Laporan Trading", layout="wide")
st.title("📊 Analisis Laporan Trading MetaTrader (Daily Profit by Open Time)")

# ----------------------
# Uploader + options
# ----------------------
uploaded_files = st.file_uploader(
    "Upload file laporan trading (CSV/XLSX)",
    type=["csv", "xlsx"],
    accept_multiple_files=True,
)

st.markdown("**Pengaturan perhitungan**")
col1, col2 = st.columns([1,2])
with col1:
    use_net = st.checkbox("Gunakan NetProfit (Profit + Swap + Commission)", value=False)
    percent_threshold = st.number_input("Threshold % untuk PASS (jika < threshold → PASS)", value=30.0, step=1.0)
with col2:
    symbol_filter = st.text_input("Filter symbol (kosong = semua)", value="")
    symbol_list = [s.strip().upper() for s in symbol_filter.split(",") if s.strip()] if symbol_filter.strip() else []

# ----------------------
# Helpers
# ----------------------
def detect_header_row_and_read(fileobj):
    try:
        df_raw = pd.read_excel(fileobj, header=None, dtype=str)
    except Exception:
        fileobj.seek(0)
        df_raw = pd.read_csv(fileobj, header=None, dtype=str)

    name = None
    account = None
    for _, r in df_raw.iterrows():
        joined = " ".join([str(x).strip() for x in r if pd.notna(x)])
        if joined.lower().startswith("name:"):
            name = joined.split(":",1)[1].strip()
        elif joined.lower().startswith("account:"):
            account = joined.split(":",1)[1].strip()

    header_row = None
    for i, r in df_raw.iterrows():
        vals = [str(x).strip() for x in r.tolist() if pd.notna(x)]
        lowvals = [v.lower() for v in vals]
        if any("time" in v for v in lowvals) and any("profit" in v for v in lowvals):
            header_row = i
            break

    if header_row is None:
        raise ValueError("Tidak menemukan header tabel transaksi.")

    fileobj.seek(0)
    try:
        df = pd.read_excel(fileobj, skiprows=header_row)
    except Exception:
        fileobj.seek(0)
        df = pd.read_csv(fileobj, skiprows=header_row)

    return name, account, df

def looks_like_datetime_string(s):
    if pd.isna(s):
        return False
    s = str(s).strip()
    return bool(re.match(r'^\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2}$', s))

def process_df_open_based(df):
