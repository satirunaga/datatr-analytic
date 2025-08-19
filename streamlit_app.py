import streamlit as st
import pandas as pd

st.title("📊 Trading Profit Analyzer")

uploaded_files = st.file_uploader(
    "Upload file laporan trading (XLSX/CSV)",
    type=["xlsx", "csv"],
    accept_multiple_files=True
)

# Baca data (header sudah benar di baris index 7)
df = pd.read_excel(file_path, sheet_name="Sheet1", header=7)

# Bersihkan kolom tak terpakai
df = df.drop(columns=["Unnamed: 13"], errors="ignore")

# Pastikan tipe data numerik
for col in ["Profit", "Swap", "Commission"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# Pastikan datetime untuk open & close time
df["Time"]   = pd.to_datetime(df["Time"], errors="coerce")
df["Time.1"] = pd.to_datetime(df["Time.1"], errors="coerce")  # <-- close time

# Filter hanya baris trade buy/sell
df["Type"] = df["Type"].astype(str).str.lower()
trades = df[df["Type"].isin(["buy", "sell"])].copy()

# Profit bersih per trade
trades["Net"] = trades["Profit"] + trades["Swap"] - trades["Commission"]

# Kelompokkan per TANGGAL CLOSE
trades["CloseDate"] = trades["Time.1"].dt.date
per_day = (
    trades.groupby("CloseDate", as_index=False)
          .agg(GrossProfit=("Profit","sum"),
               Swap=("Swap","sum"),
               Commission=("Commission","sum"),
               NetProfit=("Net","sum"))
          .sort_values("CloseDate")
)

# Ambil nilai terbesar & total
max_row = per_day.loc[per_day["NetProfit"].idxmax()]
max_profit = float(max_row["NetProfit"])
max_date   = max_row["CloseDate"]
total_profit = float(per_day["NetProfit"].sum())
percentage = (max_profit / total_profit * 100) if total_profit != 0 else 0.0

print("=== Profit per hari (berdasarkan tanggal CLOSE) ===")
print(per_day)

print("\n🔥 Profit harian terbesar (Net):", round(max_profit, 2), "pada", max_date)
print("💰 Total profit (Net):", round(total_profit, 2))
print("📈 Persentase:", round(percentage, 2), "%")

# Validasi cepat tanggal tertentu
check_date = pd.to_datetime("2025-08-04").date()
cek_sum = trades.loc[trades["CloseDate"] == check_date, "Net"].sum()
print("\n✅ Cek 2025-08-04 (Net):", round(cek_sum, 2))
