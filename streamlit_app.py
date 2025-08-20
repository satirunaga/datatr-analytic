import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Trading Report Analyzer", layout="wide")

st.title("📊 Trading Report Analyzer (MetaTrader)")

# --- fungsi ekstraksi info akun (nama & nomor akun) ---
def extract_account_info(file):
    try:
        header_df = pd.read_excel(file, sheet_name="Sheet1", nrows=20, header=None)

        texts = (
            header_df.apply(
                lambda row: " ".join([str(x) for x in row if pd.notna(x)]), axis=1
            )
            .tolist()
        )

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


# --- fungsi analisis profit harian ---
def analyze_file(file, filename):
    account_number, account_name, header_df = extract_account_info(file)

    st.subheader(f"📑 File: {filename}")
    st.write(f"👤 **Nama Pemilik:** {account_name}")
    st.write(f"🏦 **Nomor Akun:** {account_number}")

    try:
        df = pd.read_excel(file, sheet_name="Sheet1", header=7)

        if not {"Time", "Time.1", "Profit", "Commission", "Swap"}.issubset(df.columns):
            st.error("❌ Data tidak sesuai format laporan trading MetaTrader.")
            return

        for col in ["Profit", "Commission", "Swap"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        df["CloseDate"] = pd.to_datetime(df["Time.1"], errors="coerce").dt.date

        per_day = (
            df.groupby("CloseDate")[["Profit", "Commission", "Swap"]]
            .sum()
            .reset_index()
        )
        per_day["NetProfit"] = (
            per_day["Profit"] + per_day["Commission"] + per_day["Swap"]
        )

        st.write("### 📊 Profit per hari (Net)")
        st.dataframe(per_day)

        max_row = per_day.loc[per_day["NetProfit"].idxmax()]
        max_profit, max_date = max_row["NetProfit"], max_row["CloseDate"]

        total_profit = per_day["NetProfit"].sum()
        percentage = (max_profit / total_profit * 100) if total_profit != 0 else 0

        st.success(
            f"🔥 Profit harian terbesar (Net): {max_profit:.2f} pada {max_date}\n\n"
            f"💰 Total profit (Net): {total_profit:.2f}\n\n"
            f"📈 Persentase kontribusi: {percentage:.2f} %"
        )

        # --- buat file Excel hasil analisa untuk download ---
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            per_day.to_excel(writer, index=False, sheet_name="ProfitPerDay")
            summary_df = pd.DataFrame(
                {
                    "Nama Pemilik": [account_name],
                    "Nomor Akun": [account_number],
                    "Total Profit (Net)": [total_profit],
                    "Max Profit (Net)": [max_profit],
                    "Tanggal Max": [max_date],
                    "Persentase (%)": [percentage],
                }
            )
            summary_df.to_excel(writer, index=False, sheet_name="Summary")

        st.download_button(
            label="⬇️ Download Hasil Analisa",
            data=output.getvalue(),
            file_name=f"Hasil_Analisa_{account_number}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"download_{filename}",  # 🔑 unik per file
        )

    except Exception as e:
        st.error(f"Gagal memproses file: {e}")


# --- Upload multiple files ---
uploaded_files = st.file_uploader(
    "Upload laporan trading (.xlsx)", type=["xlsx"], accept_multiple_files=True
)

if uploaded_files:
    for file in uploaded_files:
        analyze_file(file, file.name)
