import streamlit as st
import pandas as pd
import io
import plotly.express as px

# ==========================
# Inject CSS + Font Awesome
# ==========================
st.markdown(
    """
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
    /* watermark logo di tengah */
    .stApp::before {
        content: "";
        position: fixed;
        top: 50%;
        left: 50%;
        width: 800px;
        height: 800px;
        background: url("https://raw.githubusercontent.com/satirunaga/datatr-analytic/main/tplus_logoo.jpg") no-repeat center center;
        background-size: contain;
        opacity: 0.08;
        transform: translate(-50%, -50%);
        z-index: -1;
        pointer-events: none;
    }

    /* metrics grid */
    .metrics-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 16px;
        margin-top: 18px;
        margin-bottom: 18px;
    }

    /* card style */
    .metric-card {
        padding: 16px;
        border-radius: 12px;
        box-shadow: 0 6px 20px rgba(16,24,40,0.06);
        display: flex;
        align-items: center;
        gap: 14px;
        color: #fff;
        min-height: 80px;
    }
    .metric-icon {
        font-size: 22px;
        width: 44px;
        text-align: center;
        opacity: 0.95;
    }
    .metric-content { display:flex; flex-direction:column; }
    .metric-title { font-size: 13px; opacity: 0.95; margin-bottom: 6px; }
    .metric-value { font-size: 18px; font-weight: 700; }

    /* gradient backgrounds */
    .card-profit      { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); }
    .card-total       { background: linear-gradient(135deg,#10b981 0%,#059669 100%); }
    .card-percent     { background: linear-gradient(135deg,#f59e0b 0%,#d97706 100%); }
    .card-status-pass { background: linear-gradient(135deg,#22c55e 0%,#16a34a 100%); }
    .card-status-fail { background: linear-gradient(135deg,#ef4444 0%,#dc2626 100%); }
    .card-challenge   { background: linear-gradient(135deg,#8b5cf6 0%,#6d28d9 100%); }
    .card-fast        { background: linear-gradient(135deg,#ec4899 0%,#db2777 100%); }

    /* responsive tweaks */
    @media (max-width: 640px) {
        .metric-title { font-size: 12px; }
        .metric-value { font-size: 16px; }
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ==========================
# Judul
# ==========================
st.title("📊 Analisis Laporan Trading MetaTrader")

# ==========================
# Upload file
# ==========================
uploaded_files = st.file_uploader(
    "Upload file laporan trading (CSV / XLSX)",
    type=["csv", "xlsx"],
    accept_multiple_files=True
)

# ==========================
# Fungsi Load Data
# ==========================
def load_mt_report(file):
    try:
        df_raw = pd.read_excel(file, header=None, dtype=str)
    except:
        file.seek(0)
        df_raw = pd.read_csv(file, header=None, dtype=str)

    name, account = None, None
    for _, row in df_raw.iterrows():
        joined = " ".join([str(x).strip() for x in row if pd.notna(x)])
        if joined.lower().startswith("name:"):
            name = joined.split(":", 1)[1].strip()
        elif joined.lower().startswith("account:"):
            account = joined.split(":", 1)[1].strip()

    header_row = None
    for i, row in df_raw.iterrows():
        values = [str(x).strip() for x in row.tolist()]
        if any("Time" in v for v in values) and any("Profit" in v for v in values):
            header_row = i
            break

    if header_row is None:
        raise ValueError("Tidak menemukan header tabel transaksi.")

    file.seek(0)
    try:
        df = pd.read_excel(file, skiprows=header_row)
    except:
        file.seek(0)
        df = pd.read_csv(file, skiprows=header_row)

    return name, account, df

# ==========================
# Fungsi Proses Data
# ==========================
def process_trades(df):
    cols = {c.lower(): c for c in df.columns}
    close_col = next((cols[k] for k in ["time.1", "close time", "close"] if k in cols), None)
    profit_col = next((cols[k] for k in ["profit", "net profit"] if k in cols), None)
    swap_col = next((cols[k] for k in cols if "swap" in k), None)
    comm_col = next((cols[k] for k in cols if "commission" in k or "comm" in k), None)

    if close_col is None or profit_col is None:
        raise ValueError("Kolom Time/Close atau Profit tidak ditemukan.")

    df[close_col] = pd.to_datetime(df[close_col], errors="coerce")
    df["CloseDate"] = df[close_col].dt.date

    df["Profit"] = pd.to_numeric(df[profit_col], errors="coerce").fillna(0)
    df["Swap"] = pd.to_numeric(df[swap_col], errors="coerce").fillna(0) if swap_col else 
