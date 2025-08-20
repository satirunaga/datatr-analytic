import pandas as pd
import streamlit as st
import io

st.set_page_config(page_title="Trading Report Analyzer", layout="wide")

st.title("📊 Trading Report Analyzer")

uploaded_files = st.file_uploader(
    "Upload laporan trading (CSV/XLSX)", 
    type=["csv", "xlsx"], 
    accept_multiple_files=True
)

results = []

def extract_account_info(df):
    """Coba ambil Nama Pemilik dan Nomor Akun dari metadata di bagian atas file"""
    owner, account = None, None
    for col in df.columns:
        series = df[col].astype(str).dropna().tolist()
        for val in series[:20]:  # cek 20 baris pertama
            if "Name:" in val:
                owner = val.replace("Name:", "").strip()
            if "Account:" in val:
                account = val.replace("Account:", "").strip()
    return owner, account

def process_file(file):
    try:
        if file.name.endswith(".csv"):
            df = pd.read_csv(file, header=None)
        else:
            df = pd.read_excel(file, header=None)

        # ambil metadata (nama & nomor akun)
        owner, account = extract_account_info(df)

        # reload data dengan header normal (baris pertama tabel transaksi)
        if file.name.endswith(".csv"):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file, header=0)

        # cek kolom penting
        required = ["Profit", "Swap", "Commission", "Time.1"]
        for c in required:
            if c not in df.columns:
                raise ValueError(f"Kolom {c} tidak ditemukan di {file.name}")

        # hitung NetProfit
        df["NetProfit"] = df["Profit"].astype(float) + \
                          df["Swap"].astype(float) + \
                          df["Commission"].astype(float)

        # ambil tanggal close
        df["CloseDate"] = pd.to_datetime(df["Time.1"], errors="coerce").dt.date
        df = df.dropna(subset=["CloseDate"])

        # grouping per hari
        daily = df.groupby("CloseDate", as_index=False).agg({
            "Profit": "sum",
            "Swap": "sum",
            "Commission": "sum",
            "NetProfit": "sum"
        })

        # total & max profit harian
        total_profit = daily["NetProfit"].sum()
        max_row = daily.loc[daily["NetProfit"].idxmax()]
        max_profit = max_row["NetProfit"]
        max_date = max_row["CloseDate"]
        pct = (max_profit / total_profit * 100) if total_profit != 0 else 0

        # tampilkan hasil
        st.markdown(f"### 📑 File: {file.name}")
        st.write(f"👤 Nama Pemilik: {owner if owner else '❓'}")
        st.write(f"🏦 Nomor Akun: {account if account else '❓'}\n")

        st.write("📊 Profit per hari (Net)")
        st.write(f"🔥 Profit harian terbesar (Net): {max_profit:.2f} pada {max_date}")
        st.write(f"💰 Total profit (Net): {total_profit:.2f}")
        st.write(f"📈 Persentase: {pct:.2f} %")
        st.write(f"✅ Cek {max_date} (Net): {max_profit:.2f}\n")

        # simpan ke result
        results.append({
            "File": file.name,
            "Owner": owner,
            "Account": account,
            "MaxDate": max_date,
            "MaxProfit": max_profit,
            "TotalProfit": total_profit,
            "ContributionPct": pct
        })

    except Exception as e:
        st.error(f"Gagal memproses file {file.name}: {e}")

# === MAIN ===
if uploaded_files:
    for f in uploaded_files:
        process_file(f)

    if results:
        df_results = pd.DataFrame(results)

        st.subheader("📂 Rekap Hasil Semua File")
        st.dataframe(df_results)

        # tombol download
        buffer = io.StringIO()
        df_results.to_csv(buffer, index=False)
        st.download_button(
            label="📥 Download Rekap (CSV)",
            data=buffer.getvalue(),
            file_name="rekap_trading.csv",
            mime="text/csv",
            key="download_rekap"
        )
