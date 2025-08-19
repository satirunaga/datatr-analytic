import streamlit as st
import pandas as pd

st.title("📊 Trading Profit Analyzer")

uploaded_files = st.file_uploader(
    "Upload file laporan trading (XLSX/CSV)",
    type=["xlsx", "csv"],
    accept_multiple_files=True
)

def hitung_profit_perhari(file):
    if file.name.endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file, header=1)  # header=1 karena baris pertama biasanya title "Positions"

    # Pastikan kolom sesuai
    if "Time" not in df.columns or "Profit" not in df.columns:
        return None

    # Konversi datetime & float
    df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
    df["Profit"] = pd.to_numeric(df["Profit"], errors="coerce")

    # Drop baris kosong
    df = df.dropna(subset=["Time", "Profit"])

    # Ambil tanggal saja
    df["Date"] = df["Time"].dt.date

    # Hitung profit per hari
    per_day = df.groupby("Date")["Profit"].sum().reset_index()

    # Hitung metrik
    max_row = per_day.loc[per_day["Profit"].idxmax()]
    max_profit, max_date = max_row["Profit"], max_row["Date"]
    total_profit = per_day["Profit"].sum()
    percentage = (max_profit / total_profit) * 100 if total_profit != 0 else 0

    return per_day, max_profit, max_date, total_profit, percentage

if uploaded_files:
    for file in uploaded_files:
        st.subheader(f"📂 Hasil untuk {file.name}")
        result = hitung_profit_perhari(file)
        if result:
            per_day, max_profit, max_date, total_profit, percentage = result
            st.dataframe(per_day)
            st.write("🔥 Profit terbesar:", max_profit, "pada", max_date)
            st.write("💰 Total profit:", total_profit)
            st.write("📈 Persentase kontribusi profit terbesar:", round(percentage, 2), "%")
        else:
            st.error("File tidak memiliki kolom Time dan Profit yang valid.")
