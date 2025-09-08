import streamlit as st
import pandas as pd
import io
import plotly.express as px

# ==========================
# CSS Styling + FontAwesome
# ==========================
st.markdown(
    """
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
    .stApp {
        background: none;
        font-family: 'Inter', sans-serif;
    }
    .stApp::before {
        content: "";
        position: fixed;
        top: 50%;
        left: 50%;
        width: 800px;
        height: 800px;
        background: url("https://raw.githubusercontent.com/satirunaga/datatr-analytic/main/tplus_logoo.jpg") no-repeat center center;
        background-size: contain;
        opacity: 0.08;  /* lebih samar */
        transform: translate(-50%, -50%);
        z-index: -1;
    }
    /* Card layout */
    .metrics-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 16px;
        margin-top: 20px;
    }
    .metric-card {
        background: #ffffff;
        padding: 18px;
        border-radius: 12px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.06);
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .metric-icon {
        font-size: 20px;
        color: #2563eb; /* biru profesional */
    }
    .metric-content {
        display: flex;
        flex-direction: column;
    }
    .metric-title {
        font-size: 13px;
        color: #666;
    }
    .metric-value {
        font-size: 18px;
        font-weight: 600;
        color: #222;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("📊 Analisis Laporan Trading MetaTrader")

# Upload file laporan
uploaded_files = st.file_uploader(
    "Upload file laporan trading (CSV/XLSX)",
    type=["csv", "xlsx"],
    accept_multiple_files=True
)


def load_mt_report(file):
    """Membaca file laporan MT4/MT5 dan mengembalikan info akun + DataFrame transaksi"""
    try:
        df_raw = pd.read_excel(file, header=None, dtype=str)
    except:
        file.seek(0)
        df_raw = pd.read_csv(file, header=None, dtype=str)

    name, account = None, None

    # Cari 'Name:' dan 'Account:'
    for _, row in df_raw.iterrows():
        joined = " ".join([str(x).strip() for x in row if pd.notna(x)])
        if joined.lower().startswith("name:"):
            name = joined.split(":", 1)[1].strip()
        elif joined.lower().startswith("account:"):
            account = joined.split(":", 1)[1].strip()

    # Cari baris header tabel
    header_row = None
    for i, row in df_raw.iterrows():
        values = [str(x).strip() for x in row.tolist()]
        if any("Time" in v for v in values) and any("Profit" in v for v in values):
            header_row = i
            break

    if header_row is None:
        raise ValueError("Tidak menemukan header tabel transaksi.")

    # Baca ulang mulai dari baris header_row
    file.seek(0)
    try:
        df = pd.read_excel(file, skiprows=header_row)
    except:
        file.seek(0)
        df = pd.read_csv(file, skiprows=header_row)

    return name, account, df


def process_trades(df):
    """Menghitung profit harian berdasarkan Open Time"""
    cols = {c
