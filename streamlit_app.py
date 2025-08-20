import streamlit as st
import pandas as pd

st.set_page_config(page_title="Trading Report Analyzer", layout="wide")

# === Fungsi ambil info Account & Nama ===
def extract_account_info(file):
    """Ambil informasi account dan nama trader dari baris awal laporan MetaTrader"""
    try:
        header_df = pd.read_excel(file, sheet_name="Sheet1", nrows=6, header=None)

        account_number, account_name = "Tidak ditemukan", "Tidak ditemukan"

        # Cari di seluruh isi dataframe, bukan hanya kolom 0
        for row in header_df.values.flatten():
            if pd.isna(row):
                continue
            text = str(row)
            if "Account" in text:
                account_number = text.replace("Account:", "").strip()
            if "Name" in text:
                account_name = text.replace("Name:", "").strip()

        return account_number, account_name, header_df
    except Exception:
        return "Tidak ditemukan", "Tidak ditemukan", pd.DataFrame()


# === Fungsi analisa profit ===
def hitung_profit_perhari(file):
    try:
        df = pd.read_excel(file, sheet_name="Sheet1", header=7)

        # Pastikan kolom penting ada
        if not {"Time.1", "Profit", "Commission", "Swap"}.issubset(df.columns):
            return None

        # Bersihkan data
        df = df.dropna(subset=["Time.1", "Profit"])
        df["CloseDate"] = pd.to_datetime(df["Time.1"]).dt.date
        df["Profit"] = pd.to_numeric(df["Profit"], errors="coerce").fillna(0)
        df["Swap"] = pd.to_numeric(df["Swap"], errors="coerce").fillna(0)
        df["Commission"] = pd.to_numeric(df["Commission"], errors="coerce").fillna(0)

        # Hitung gross/net per hari
        per_day = (
            df.groupby("CloseDate")
            .agg(
                GrossProfit=("Profit", "sum"),
                Swap=("Swap", "sum"),
                Commission=("Commission", "sum"),
            )
            .reset_index()
        )
        per_day["NetProfit"] = (
            per_day["GrossProfit"] + per_day["Swap"] + per_day["Commission"]
        )

        # Statistik
        max_row = per_day.loc[per_day["NetProfit"].idxmax()]
        max_profit, max_date = max_row["NetProfit"], max_row["CloseDate"]
        total_profit = per_day["NetProfit"].sum()
        percentage = (max_profit / total_profit * 100) if total_profit != 0 else 0

        return per_day, max_profit, max_date, total_profit, percentage
    except Exception as e:
        st.error(f"Gagal memproses file: {e}")
        return None


# === UI Streamlit ===
st.title("📊 Trading Report Analyzer")

uploaded_files = st.file_uploader(
    "Upload file laporan trading (.xlsx)", type=["xlsx"], accept_multiple_files=True
)

if uploaded_files:
    for file in uploaded_files:
        st.divider()
        st.subheader(f"📑 File: {file.name}")

        # Ambil info akun & nama
        account_number, account_name, header_df = extract_account_info(file)
        st.write(f"👤 Nama Pemilik: **{account_name}**")
        st.write(f"🏦 Nomor Akun: **{account_number}**")

        # Debug opsional (bisa dimatikan kalau sudah yakin)
        with st.expander("🔍 Debug: 6 baris pertama file"):
            st.dataframe(header_df)

        # Hitung profit per hari
        result = hitung_profit_perhari(file)
        if result:
            per_day, max_profit, max_date, total_profit, percentage = result

            st.write("### 📊 Profit per Hari (berdasarkan tanggal CLOSE)")
            st.dataframe(per_day)

            st.success(f"🔥 Profit harian terbesar (Net): {max_profit:.2f} pada {max_date}")
            st.info(f"💰 Total profit (Net): {total_profit:.2f}")
            st.warning(f"📈 Persentase kontribusi: {percentage:.2f} %")
        else:
            st.error("❌ Data tidak sesuai format laporan trading MetaTrader.")
