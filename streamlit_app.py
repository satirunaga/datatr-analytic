import streamlit as st
import pandas as pd

st.title("📊 Trading Report Analyzer")

def baca_file(file):
    """Baca file Excel/CSV trading report dan deteksi header otomatis"""
    if file.name.endswith(".csv"):
        df = pd.read_csv(file)
    else:
        for skip in range(0, 10):
            try:
                df = pd.read_excel(file, skiprows=skip)
                if "Time.1" in df.columns and "Profit" in df.columns:
                    return df
            except Exception:
                continue
        return None
    return df

def hitung_profit_perhari(file):
    df = baca_file(file)

    if df is None or "Time.1" not in df.columns or "Profit" not in df.columns:
        st.error("❌ File tidak memiliki kolom 'Time.1' (Close) dan 'Profit'.")
        return None

    # Konversi tipe data
    df["Time.1"] = pd.to_datetime(df["Time.1"], errors="coerce")
    df["Profit"] = pd.to_numeric(df["Profit"], errors="coerce")
    df["Swap"] = pd.to_numeric(df.get("Swap", 0), errors="coerce").fillna(0)
    df["Commission"] = pd.to_numeric(df.get("Commission", 0), errors="coerce").fillna(0)

    df = df.dropna(subset=["Time.1", "Profit"])

    # Ambil tanggal CLOSE
    df["CloseDate"] = df["Time.1"].dt.date

    # Hitung Net Profit per hari
    per_day = (
        df.groupby("CloseDate")
        .agg(
            GrossProfit=("Profit", "sum"),
            Swap=("Swap", "sum"),
            Commission=("Commission", "sum"),
        )
        .reset_index()
    )
    per_day["NetProfit"] = per_day["GrossProfit"] + per_day["Swap"] + per_day["Commission"]

    # Metrik utama
    max_row = per_day.loc[per_day["NetProfit"].idxmax()]
    max_profit, max_date = max_row["NetProfit"], max_row["CloseDate"]
    total_profit = per_day["NetProfit"].sum()
    percentage = (max_profit / total_profit) * 100 if total_profit != 0 else 0

    return per_day, max_profit, max_date, total_profit, percentage


# Upload multiple files
uploaded_files = st.file_uploader("📂 Upload file laporan trading", accept_multiple_files=True)

if uploaded_files:
    for file in uploaded_files:
        st.subheader(f"📑 File: {file.name}")

        hasil = hitung_profit_perhari(file)
        if hasil:
            per_day, max_profit, max_date, total_profit, percentage = hasil

            st.write("### === Profit per hari (berdasarkan tanggal CLOSE) ===")
            st.dataframe(per_day)

            st.success(f"🔥 Profit harian terbesar (Net): {max_profit} pada {max_date}")
            st.info(f"💰 Total profit (Net): {total_profit}")
            st.warning(f"📈 Persentase: {round(percentage, 2)} %")

            # Tambahan: grafik
            st.line_chart(per_day.set_index("CloseDate")["NetProfit"])
