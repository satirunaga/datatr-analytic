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
    # Normalisasi nama kolom
    cols = {c.lower(): c for c in df.columns}
    close_col = None
    for key in ["time.1", "close time", "close"]:
        if key in cols:
            close_col = cols[key]
            break

    profit_col = None
    for key in ["profit", "net profit"]:
        if key in cols:
            profit_col = cols[key]
            break

    swap_col = None
    for key in ["swap"]:
        if key in cols:
            swap_col = cols[key]
            break

    comm_col = None
    for key in ["commission", "comm"]:
        if key in cols:
            comm_col = cols[key]
            break

    if close_col is None or profit_col is None:
        raise ValueError("Kolom Time/Close atau Profit tidak ditemukan.")

    df[close_col] = pd.to_datetime(df[close_col], errors="coerce")
    df["CloseDate"] = df[close_col].dt.date

    df["Profit"] = pd.to_numeric(df[profit_col], errors="coerce").fillna(0)
    df["Swap"] = pd.to_numeric(df[swap_col], errors="coerce").fillna(0) if swap_col else 0
    df["Commission"] = pd.to_n_
