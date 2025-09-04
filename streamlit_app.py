import streamlit as st
import pandas as pd
import io

st.title("📊 Analisis Laporan Trading MetaTrader")

uploaded_files = st.file_uploader(
    "Upload file laporan trading (CSV/XLSX)", 
    type=["csv", "xlsx"], 
    accept_multiple_files=True
)

def load_mt_report(file):
    """Membaca file laporan MT4/MT5 dan mengembalikan info akun + DataFrame transaksi"""
    # Cari teks nama & account di awal file (pakai pandas read_excel tanpa header dulu)
    try:
        df_raw = pd.read_excel(file, header=None)
    except:
        file.seek(0)
        df_raw = pd.read_csv(file, header=None)

    name, account = None, None
    for row in df_raw[0].dropna().astype(str):
        if row.startswith("Name:"):
            name = row.replace("Name:", "").strip()
        elif row.startswith("Account:"):
            account = row.replace("Account:", "").strip()

    # Cari baris header tabel (biasanya ada kolom "Time" atau "Open Time")
    header_row = None
    for i, row in df_raw.iterrows():
        values = [str(x) for x in row.tolist()]
        if "Time" in values or "Open Time" in values:
            header_row = i
            break

    if header_row is None:
        raise ValueError("Tidak menemukan header tabel transaksi.")

    # Baca ulang mulai dari header_row
    file.seek(0)
    try:
        df = pd.read_excel(file, skiprows=header_row)
    except:
        file.seek(0)
        df = pd.read_csv(file, skiprows=header_row)

    return name, account, df

def process_trades(df):
    """Menghitung profit harian berdasarkan Close Time (Time.1)"""
    # Normalisasi nama kolom
    cols = {c.lower(): c for c in df.columns}
    close_col = None
    for key in ["time.1", "close time", "close"]:
        if key in cols:
            close_col = cols[key]
            break

    profit_col = None
    for key in ["profit", "net profit"]:
        if key in cols:
            profit_col = cols[key]
            break

    swap_col = None
    for key in ["swap"]:
        if key in cols:
            swap_col = cols[key]
            break

    comm_col = None
    for key in ["commission", "comm"]:
        if key in cols:
            comm_col = cols[key]
            break

    if close_col is None or profit_col is None:
        raise ValueError("Kolom Time/Close atau Profit tidak ditemukan.")

    df[close_col] = pd.to_datetime(df[close_col], errors="coerce")
    df["CloseDate"] = df[close_col].dt.date

    df["Profit"] = pd.to_numeric(df[profit_col], errors="coerce").fillna(0)
    df["Swap"] = pd.to_numeric(df[swap_col], errors="coerce").fillna(0) if swap_col else 0
    df["Commission"] = pd.to_numeric(df[comm_col], errors="coerce").fillna(0) if comm_col else 0

    df["NetProfit"] = df["Profit"] + df["Swap"] + df["Commission"]

    daily = df.groupby("CloseDate").agg(
        GrossProfit=( "Profit", "sum"),
        Swap=("Swap", "sum"),
        Commission=("Commission", "sum"),
        NetProfit=("NetProfit", "sum")
    ).reset_index()

    return daily

if uploaded_files:
    for file in uploaded_files:
        st.write(f"📑 File: {file.name}")
        try:
            name, account, df = load_mt_report(file)
            if name: st.write(f"👤 Nama Pemilik: **{name}**")
            if account: st.write(f"🏦 Nomor Akun: **{account}**")

            daily = process_trades(df)

            # Hitung ringkasan
            total_profit = daily["NetProfit"].sum()
            max_row = daily.loc[daily["NetProfit"].idxmax()]
            max_profit = max_row["NetProfit"]
            max_date = max_row["CloseDate"]
            percent = (max_profit / total_profit) * 100 if total_profit != 0 else 0

            st.subheader("📊 Profit per hari (Net)")
            st.dataframe(daily)

            st.markdown(
                f"""
                🔥 Profit harian terbesar (Net): **{max_profit:.2f}** pada **{max_date}**  
                💰 Total profit (Net): **{total_profit:.2f}**  
                📈 Persentase: **{percent:.2f} %**  
                ✅ Cek {max_date} (Net): **{max_profit:.2f}**
                """
            )

            # Tombol download hasil per hari
            output = io.BytesIO()
            daily.to_csv(output, index=False)
            st.download_button(
                label="💾 Download hasil per hari (CSV)",
                data=output.getvalue(),
                file_name=f"daily_profit_{file.name}.csv",
                mime="text/csv",
                key=f"dl_{file.name}"
            )

        except Exception as e:
            st.error(f"Gagal memproses file {file.name}: {e}")
