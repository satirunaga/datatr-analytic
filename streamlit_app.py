import streamlit as st
import pandas as pd
import io

st.title("📊 Analisis Laporan Trading MetaTrader")

uploaded_files = st.file_uploader(
    "Upload file laporan trading (CSV/XLSX)", 
    type=["csv", "xlsx"], 
    accept_multiple_files=True
)

def load_mt_report(file):
    """Membaca file laporan MT4/MT5 dan mengembalikan info akun + DataFrame transaksi"""
    # Cari teks nama & account di awal file (pakai pandas read_excel tanpa header dulu)
    try:
        df_raw = pd.read_excel(file, header=None)
    except:
        file.seek(0)
        df_raw = pd.read_csv(file, header=None)

    name, account = None, None
    for row in df_raw[0].dropna().astype(str):
        if row.startswith("Name:"):
            name = row.replace("Name:", "").strip()
        elif row.startswith("Account:"):
            account = row.replace("Account:", "").strip()

    # Cari baris header tabel (biasanya ada kolom "Time" atau "Open Time")
    header_row = None
    for i, row in df_raw.iterrows():
        values = [str(x) for x in row.tolist()]
        if "Time" in values or "Open Time" in values:
            header_row = i
            break

    if header_row is None:
        raise ValueError("Tidak menemukan header tabel transaksi.")

    # Baca ulang mulai dari header_row
    file.seek(0)
    try:
        df = pd.read_excel(file, skiprows=header_row)
    except:
        file.seek(0)
        df = pd.read_csv(file, skiprows=header_row)

    return name, account, df

def process_trades(df):
    """Menghitung profit harian berdasarkan Close Time (Time.1)"""
    # No
