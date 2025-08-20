import streamlit as st
import pandas as pd

st.title("📊 Analisis Profit Trading per Hari")

# Fungsi utama
def hitung_profit_perhari(file):
    # Baca file sesuai format
    if file.name.endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file, header=1)  # header=1 karena header ada di baris kedua

    # Pastikan kolom tersedia
    if "Time" not in df.columns or "Profit" not in df.columns:
        st.error("❌ File tidak memiliki kolom 'Time' dan 'Profit'.")
        return None

    # Konversi tipe data
    df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
    df["Profit"] = pd.to_numeric(df["Profit"], errors="coerce")

    # Bersihkan data
    df = df.dropna(subset=["Time", "Profit"])

    # Ambil tanggal saja
    df["Date"] = df["Time"].dt.date

    # Hitung profit per hari
    per_day = df.groupby("Date")["Profit"].sum().reset_index()

    # Hitung metrik utama
    max_row = per_day.loc[per_day["Profit"].idxmax()]
    max_profit, max_date = max_row["Profit"], max_row["Date"]
    total_profit = per_day["Profit"].sum()
    percentage = (max_profit / total_profit) * 100 if total_profit != 0 else 0

    return per_day, max_profit, max_date, total_profit, percentage


# Upload multiple file
uploaded_files = st.file_uploader("Upload file trading (CSV/XLSX)", type=["csv", "xlsx"], accept_multiple_files=True)

if uploaded_files:
    for file in uploaded_files:
        st.subheader(f"📂 File: {file.name}")

        result = hitung_profit_perhari(file)
        if result:
            per_day, max_profit, max_date, total_profit, percentage = result

            # Tampilkan tabel
            st.write("📅 Profit per Hari:")
            st.dataframe(per_day)

            # Ringkasan
            st.success(f"🔥 Profit terbesar: {max_profit:,.2f} pada {max_date}")
            st.info(f"💰 Total profit: {total_profit:,.2f}")
            st.warning(f"📈 Persentase kontribusi profit terbesar: {percentage:.2f}%")
