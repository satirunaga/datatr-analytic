import streamlit as st
import pandas as pd
from io import BytesIO

st.title("📊 Analisa Laporan Trading per Klien")

uploaded_files = st.file_uploader("Upload file laporan trading (Excel)", type=["xlsx"], accept_multiple_files=True)

def extract_account_info(file):
    """Ambil informasi account dan nama trader dari baris awal laporan MetaTrader"""
    try:
        header_df = pd.read_excel(file, sheet_name="Sheet1", nrows=6, header=None)
        account_number, account_name = "Tidak diketahui", "Tidak diketahui"
        for row in header_df[0].dropna():
            if "Account" in str(row):
                account_number = str(row).replace("Account:", "").strip()
            if "Name" in str(row):
                account_name = str(row).replace("Name:", "").strip()
        return account_number, account_name
    except Exception:
        return "Tidak diketahui", "Tidak diketahui"

def hitung_profit_perhari(file):
    # baca tabel transaksi
    df = pd.read_excel(file, sheet_name="Sheet1", header=7)

    if not {"Time.1", "Profit", "Swap", "Commission"}.issubset(df.columns):
        st.error("❌ Kolom transaksi tidak ditemukan dalam file ini.")
        return None

    df["CloseDate"] = pd.to_datetime(df["Time.1"], errors="coerce").dt.date

    df["Profit"] = pd.to_numeric(df["Profit"], errors="coerce").fillna(0)
    df["Swap"] = pd.to_numeric(df["Swap"], errors="coerce").fillna(0)
    df["Commission"] = pd.to_numeric(df["Commission"], errors="coerce").fillna(0)

    per_day = df.groupby("CloseDate").agg({
        "Profit": "sum",
        "Swap": "sum",
        "Commission": "sum"
    }).reset_index()

    per_day["NetProfit"] = per_day["Profit"] + per_day["Swap"] + per_day["Commission"]

    max_row = per_day.loc[per_day["NetProfit"].idxmax()]
    max_profit, max_date = max_row["NetProfit"], max_row["CloseDate"]

    total_profit = per_day["NetProfit"].sum()
    percentage = (max_profit / total_profit * 100) if total_profit != 0 else 0

    return per_day, max_profit, max_date, total_profit, percentage

def convert_to_excel(df):
    """Convert dataframe ke file Excel dalam memory"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="ProfitPerHari")
    processed_data = output.getvalue()
    return processed_data

if uploaded_files:
    for file in uploaded_files:
        st.subheader(f"📑 File: {file.name}")

        # ambil info akun
        account_number, account_name = extract_account_info(file)
        st.markdown(f"👤 **Nama Pemilik:** {account_name}")
        st.markdown(f"🏦 **Nomor Akun:** {account_number}")

        result = hitung_profit_perhari(file)
        if result is None:
            continue

        per_day, max_profit, max_date, total_profit, percentage = result

        st.dataframe(per_day)

        st.markdown(f"🔥 Profit harian terbesar (Net): **{max_profit:.2f}** pada **{max_date}**")
        st.markdown(f"💰 Total profit (Net): **{total_profit:.2f}**")
        st.markdown(f"📈 Persentase kontribusi: **{percentage:.2f}%**")

        # tombol download Excel
        excel_data = convert_to_excel(per_day)
        st.download_button(
            label="⬇️ Download Hasil Analisa (Excel)",
            data=excel_data,
            file_name=f"Analisa_{account_number}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # tombol download CSV
        csv_data = per_day.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download Hasil Analisa (CSV)",
            data=csv_data,
            file_name=f"Analisa_{account_number}.csv",
            mime="text/csv"
        )
