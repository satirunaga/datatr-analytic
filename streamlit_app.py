import streamlit as st
import pandas as pd

st.set_page_config(page_title="Analisis Laporan Trading", layout="wide")

# ==========================
# Fungsi ekstrak nama & akun
# ==========================
def extract_account_info(file):
    try:
        # baca 20 baris pertama (header laporan), tanpa header kolom
        header_df = pd.read_excel(file, sheet_name="Sheet1", nrows=20, header=None)

        # gabungkan semua kolom jadi 1 list string
        texts = header_df.astype(str).apply(lambda x: " ".join(x), axis=1).tolist()

        account_number, account_name = "Tidak ditemukan", "Tidak ditemukan"

        for row in texts:
            row_strip = row.strip()
            if row_strip.startswith("Name:"):
                account_name = row_strip.replace("Name:", "").strip()
            if row_strip.startswith("Account:"):
                account_number = row_strip.replace("Account:", "").strip()

        return account_number, account_name, header_df

    except Exception:
        return "Tidak ditemukan", "Tidak ditemukan", pd.DataFrame()


# ==========================
# Fungsi hitung profit harian
# ==========================
def hitung_profit_perhari(file):
    try:
        df = pd.read_excel(file, sheet_name="Sheet1", header=7)
        df = df.dropna(how="all", axis=1)
        df = df.dropna(subset=["Time.1", "Profit"])

        df["CloseDate"] = pd.to_datetime(df["Time.1"], errors="coerce").dt.date

        for col in ["Profit", "Commission", "Swap"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            else:
                df[col] = 0.0

        per_day = df.groupby("CloseDate").agg(
            GrossProfit=("Profit", "sum"),
            Swap=("Swap", "sum"),
            Commission=("Commission", "sum"),
        ).reset_index()

        per_day["NetProfit"] = (
            per_day["GrossProfit"] + per_day["Swap"] + per_day["Commission"]
        )

        max_idx = per_day["NetProfit"].idxmax()
        max_profit = per_day.loc[max_idx, "NetProfit"]
        max_date = per_day.loc[max_idx, "CloseDate"]
        total_profit = per_day["NetProfit"].sum()
        percentage = (max_profit / total_profit * 100) if total_profit != 0 else 0

        return per_day, max_profit, max_date, total_profit, percentage

    except Exception as e:
        raise e


# ==========================
# Streamlit App
# ==========================
st.title("📊 Analisis Laporan Trading MetaTrader")

uploaded_files = st.file_uploader(
    "Unggah satu atau beberapa laporan trading (.xlsx)", 
    type=["xlsx"], 
    accept_multiple_files=True
)

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.divider()
        st.subheader(f"📑 File: {uploaded_file.name}")

        account_number, account_name, header_df = extract_account_info(uploaded_file)

        st.markdown(f"👤 **Nama Pemilik:** {account_name}")
        st.markdown(f"🏦 **Nomor Akun:** {account_number}")

        with st.expander("🔍 Debug: Header laporan (20 baris pertama)"):
            st.dataframe(header_df)

        try:
            per_day, max_profit, max_date, total_profit, percentage = hitung_profit_perhari(uploaded_file)

            st.markdown("### 📊 Profit per hari (Net)")
            st.dataframe(per_day)

            st.success(f"🔥 Profit harian terbesar (Net): **{max_profit:.2f}** pada **{max_date}**")
            st.info(f"💰 Total profit (Net): **{total_profit:.2f}**")
            st.warning(f"📈 Kontribusi profit terbesar: **{percentage:.2f}%**")

        except Exception as e:
            st.error(f"❌ Gagal memproses file: {e}")
            st.write("⚠ Data mungkin tidak sesuai format laporan trading MetaTrader.")
