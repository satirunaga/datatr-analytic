import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import re

# -----------------------
# Helpers
# -----------------------

def read_any(file):
    """Baca file apapun (csv/excel)"""
    name = file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(file)
    else:
        return pd.read_excel(file)

def coerce_date_series(s):
    """Paksa kolom tanggal ke datetime"""
    return pd.to_datetime(s, errors="coerce", dayfirst=True, infer_datetime_format=True)

def normalize_numeric_series(s):
    """Pastikan kolom numerik"""
    return pd.to_numeric(s, errors="coerce").fillna(0.0)

def pick_column(df, candidates=None, patterns=None):
    """Cari kolom dengan nama mirip"""
    cols = [c.lower().strip() for c in df.columns]
    if candidates:
        for c in candidates:
            if c.lower() in cols:
                return df.columns[cols.index(c.lower())]
    if patterns:
        for pat in patterns:
            for i, c in enumerate(cols):
                if re.search(pat, c):
                    return df.columns[i]
    return None

def extract_account_info(file):
    """Ambil info Name & Account dari header file excel"""
    try:
        fbytes = file.getvalue()
        f = BytesIO(fbytes)
        df0 = pd.read_excel(f, header=None)
        text = " ".join(df0.astype(str).fillna("").values.flatten().tolist())

        # Cari Name:
        name_match = re.search(r"Name:\s*([A-Z\s]+)", text, re.IGNORECASE)
        name = name_match.group(1).strip() if name_match else ""

        # Cari Account:
        acc_match = re.search(r"Account:\s*([0-9]+[^\s]*)", text, re.IGNORECASE)
        acc = acc_match.group(1).strip() if acc_match else ""

        return acc, name
    except Exception:
        return "", ""

# -----------------------
# Main analysis
# -----------------------

def analyze_file(file, filename):
    # 1) Info Akun
    account_number, account_name = extract_account_info(file)

    # 2) Baca data transaksi
    file.seek(0)
    df = read_any(file).copy()
    df.columns = [str(c).strip() for c in df.columns]

    # 3) Deteksi kolom tanggal CLOSE
    close_col = pick_column(
        df,
        candidates=["Time.1", "Close Time", "Close", "CloseDate", "Close Date", "Deal time"],
        patterns=[r"\bclose[_\s]?time\b", r"\btime\.?1\b", r"\bclose\b"]
    )
    if not close_col:
        close_col = pick_column(df, candidates=["Time", "Open Time", "Datetime", "Date"])
    if not close_col:
        st.error(f"❌ Tidak menemukan kolom tanggal CLOSE/TIME pada {filename}")
        return

    # 4) Deteksi kolom Profit/Commission/Swap
    profit_col = pick_column(df, candidates=["Profit", "Gross Profit", "Net Profit", "P/L", "PL", "NetProfit"],
                             patterns=[r"profit|p\/?l|net"])
    comm_col = pick_column(df, candidates=["Commission", "Comm"], patterns=[r"comm"])
    swap_col = pick_column(df, candidates=["Swap", "Storage", "Rollover"], patterns=[r"swap|roll"])

    if not profit_col:
        st.error(f"❌ Tidak menemukan kolom Profit/P&L pada {filename}")
        return

    # 5) Parse tanggal & angka
    close_dt = coerce_date_series(df[close_col])
    df = df.assign(CloseDate=close_dt.dt.date)
    df = df.dropna(subset=["CloseDate"])

    profit_s = normalize_numeric_series(df[profit_col])
    comm_s = normalize_numeric_series(df[comm_col]) if comm_col else pd.Series(0.0, index=df.index)
    swap_s = normalize_numeric_series(df[swap_col]) if swap_col else pd.Series(0.0, index=df.index)

    df = df.assign(_profit=profit_s, _comm=comm_s, _swap=swap_s)
    df["NetProfit"] = df["_profit"] + df["_comm"] + df["_swap"]

    # 6) Agregasi harian
    per_day = (
        df.groupby("CloseDate")[["_profit", "_comm", "_swap", "NetProfit"]]
        .sum()
        .reset_index()
        .rename(columns={"_profit": "Profit", "_comm": "Commission", "_swap": "Swap"})
    )

    if per_day.empty:
        st.warning(f"Tidak ada baris valid setelah parsing {filename}")
        return

    # 7) Ringkasan
    max_row = per_day.loc[per_day["NetProfit"].idxmax()]
    max_profit = float(max_row["NetProfit"])
    max_date = max_row["CloseDate"]
    total_profit = float(per_day["NetProfit"].sum())
    percentage = (max_profit / total_profit * 100.0) if total_profit != 0 else 0.0

    # 8) Tampilkan
    st.subheader(f"📑 File: {filename}")
    st.write(f"👤 **Nama Pemilik:** {account_name}")
    st.write(f"🏦 **Nomor Akun:** {account_number}\n")

    st.write("📊 **Ringkasan Profit (Net)**")
    st.write(f"🔥 **Profit harian terbesar (Net): {max_profit:.2f} pada {max_date}**")
    st.write(f"💰 **Total profit (Net): {total_profit:.2f}**")
    st.write(f"📈 **Persentase: {percentage:.2f} %**")
    st.write(f"✅ **Cek {max_date} (Net): {max_profit:.2f}**")

    # 👉 Tambah tampilkan tabel harian
    st.write("📊 **Detail Profit Harian**")
    st.dataframe(per_day, use_container_width=True)

    # 9) Download Excel per file
    out = BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        per_day.to_excel(writer, index=False, sheet_name="ProfitPerDay")
        pd.DataFrame({
            "Nama Pemilik": [account_name],
            "Nomor Akun": [account_number],
            "Total Profit (Net)": [total_profit],
            "Max Profit (Net)": [max_profit],
            "Tanggal Max": [max_date],
            "Persentase (%)": [percentage],
        }).to_excel(writer, index=False, sheet_name="Summary")

    st.download_button(
        label="⬇️ Download Hasil (Excel)",
        data=out.getvalue(),
        file_name=f"Hasil_Analisa_{account_number or filename}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"dl_{filename}",
    )

# -----------------------
# Streamlit App
# -----------------------

st.title("📊 Analisis Laporan Trading (Fleksibel)")

uploaded_files = st.file_uploader("Upload file laporan trading (CSV/XLSX)", type=["csv", "xlsx"], accept_multiple_files=True)

if uploaded_files:
    for file in uploaded_files:
        try:
            analyze_file(file, file.name)
        except Exception as e:
            st.error(f"Gagal memproses file {file.name}: {e}")
