import streamlit as st
import pandas as pd

st.title("📊 Trading Report Analyzer")

def baca_file(file):
    """Baca file dan otomatis cari header yang benar."""
    if file.name.endswith(".csv"):
        df = pd.read_csv(file)
    else:
        # coba baca beberapa kali dengan skiprows
        for skip in range(0, 10):
            try:
                df = pd.read_excel(file, skiprows=skip)
                if "Time" in df.columns and "Profit" in df.columns:
                    return df
            except Exception:
                continue
        return None
    return df

def hitung_profit_perhari(file):
    df = baca_file(file)

    if df is None or "Time" not in df.columns or "Profit" not in df.columns:
        st.error("❌ File tidak memiliki kolom 'Time' dan 'Profit'.")
        return None

    # Debug tampilkan kolom
    st.write("Kolom terbaca:", list(df.columns))

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


# Upload multiple files
uploaded_files = st.file_uploader("📂 Upload file laporan trading", accept_multiple_files=True)

if uploaded_files:
    for file in uploaded_files:
        st.subheader(f"📑 File: {file.name}")

        hasil = hitung_profit_perhari(file)
        if hasil:
            per_day, max_profit, max_date, total_profit, percentage = hasil

            st.write("### 📊 Profit per hari:")
            st.dataframe(per_day)

            st.success(f"🔥 Profit terbesar: {max_profit} pada {max_date}")
            st.info(f"💰 Total profit: {total_profit}")
            st.warning(f"📈 Kontribusi profit terbesar: {round(percentage, 2)} %")
