import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.title("📊 Analisa Laporan Trading")

uploaded_files = st.file_uploader("Upload file laporan trading (Excel)", type=["xlsx"], accept_multiple_files=True)

def hitung_profit_perhari(file):
    # baca file excel (mulai dari baris ke-7, sesuai format MetaTrader report)
    df = pd.read_excel(file, sheet_name="Sheet1", header=7)

    # pastikan kolom ada
    if not {"Time.1", "Profit", "Swap", "Commission"}.issubset(df.columns):
        st.error("❌ Kolom yang dibutuhkan tidak ditemukan dalam file ini.")
        return None

    # ubah Time.1 menjadi tanggal close
    df["CloseDate"] = pd.to_datetime(df["Time.1"], errors="coerce").dt.date

    # pastikan numerik
    df["Profit"] = pd.to_numeric(df["Profit"], errors="coerce").fillna(0)
    df["Swap"] = pd.to_numeric(df["Swap"], errors="coerce").fillna(0)
    df["Commission"] = pd.to_numeric(df["Commission"], errors="coerce").fillna(0)

    # hitung profit harian
    per_day = df.groupby("CloseDate").agg({
        "Profit": "sum",
        "Swap": "sum",
        "Commission": "sum"
    }).reset_index()

    per_day["NetProfit"] = per_day["Profit"] + per_day["Swap"] + per_day["Commission"]

    # cari profit terbesar
    max_row = per_day.loc[per_day["NetProfit"].idxmax()]
    max_profit, max_date = max_row["NetProfit"], max_row["CloseDate"]

    # total profit
    total_profit = per_day["NetProfit"].sum()

    # persentase
    percentage = (max_profit / total_profit * 100) if total_profit != 0 else 0

    return per_day, max_profit, max_date, total_profit, percentage


if uploaded_files:
    for file in uploaded_files:
        st.subheader(f"📑 File: {file.name}")

        result = hitung_profit_perhari(file)
        if result is None:
            continue

        per_day, max_profit, max_date, total_profit, percentage = result

        # tampilkan tabel
        st.dataframe(per_day)

        # tampilkan hasil analisa
        st.markdown(f"🔥 Profit harian terbesar (Net): **{max_profit:.2f}** pada **{max_date}**")
        st.markdown(f"💰 Total profit (Net): **{total_profit:.2f}**")
        st.markdown(f"📈 Persentase kontribusi: **{percentage:.2f}%**")

        # grafik line chart sederhana
        st.subheader("📈 Grafik Profit Harian (Net)")
        fig, ax = plt.subplots()
        ax.plot(per_day["CloseDate"], per_day["NetProfit"], linestyle="-", color="blue")
        ax.set_xlabel("Tanggal")
        ax.set_ylabel("Net Profit")
        ax.set_title("Grafik Profit Harian (Line Chart)")
        ax.grid(True, linestyle="--", alpha=0.5)
        st.pyplot(fig)
