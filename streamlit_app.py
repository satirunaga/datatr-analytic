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
    try:
        df_raw = pd.read_excel(file, header=None, dtype=str)
    except:
        file.seek(0)
        df_raw = pd.read_csv(file, header=None, dtype=str)

    name, account = None, None

    # 🔍 Cari info Name & Account di 2 kolom (format laporan MT)
    for _, row in df_raw.iterrows():
        if str(row[0]).strip().lower().startswith("name"):
            name = str(row[1]).strip() if len(row) > 1 and pd.notna(row[1]) else "-"
        elif str(row[0]).strip().lower().startswith("account"):
            account = str(row[1]).strip() if len(row) > 1 and pd.notna(row[1]) else "-"

    # Cari baris header tabel transaksi
    header_row = None
    for i, row in df_raw.iterrows():
        values = [str(x).lower() for x in row.tolist()]
        if "time" in values or "open time" in values:
            header_row = i
            break

    if header_row is None:
        raise ValueError("❌ Tidak menemukan header tabel transaksi.")

    # Baca ulang tabel mulai dari header_row
    file.seek(0)
    try:
        df = pd.read_excel(file, skiprows=header_row)
    except:
        file.seek(0)
        df = pd.read_csv(file, skiprows=header_row)

    return name or "-", account or "-", df


def process_trades(df):
    """Menghitung profit harian berdasarkan Close Time"""
    cols = {c.lower(): c for c in df.columns}

    # cari kolom waktu
    close_col = None
    for key in ["time.1", "close time", "close"]:
        if key in cols:
            close_col = cols[key]
            break

    # cari kolom profit
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
        raise ValueError("❌ Kolom Time/Close atau Profit tidak ditemukan.")

    df[close_col] = pd.to_datetime(df[close_col], errors="coerce")
    df["CloseDate"] = df[close_col].dt.date

    df["Profit"] = pd.to_numeric(df[profit_col], errors="coerce").fillna(0)
    df["Swap"] = pd.to_numeric(df[swap_col], errors="coerce").fillna(0) if swap_col else 0
    df["Commission"] = pd.to_numeric(df[comm_col], errors="coerce").fillna(0) if comm_col else 0

    # hanya hitung Profit (tanpa swap & komisi)
    df["NetProfit"] = df["Profit"]

    daily = df.groupby("CloseDate").agg(
        NetProfit=("NetProfit", "sum")
    ).reset_index()

    return daily


if uploaded_files:
    for file in uploaded_files:
        st.write(f"📑 File: {file.name}")
        try:
            name, account, df = load_mt_report(file)

            st.write(f"👤 Nama Klien: **{name}**")
            st.write(f"🏦 Nomor Akun: **{account}**")

            daily = process_trades(df)

            # Hitung ringkasan
            total_profit = daily["NetProfit"].sum()
            max_row = daily.loc[daily["NetProfit"].idxmax()]
            max_profit = max_row["NetProfit"]
            max_date = max_row["CloseDate"]
            percent = (max_profit / total_profit * 100) if total_profit != 0 else 0

            # 80% & 90%
            profit_80 = total_profit * 0.8
            profit_90 = total_profit * 0.9

            st.subheader("📊 Profit per hari (Net)")
            st.dataframe(daily)

            st.markdown(
                f"""
                🔥 Profit harian terbesar (Net): **{max_profit:.2f}** pada **{max_date}**  
                💰 Total profit (Net): **{total_profit:.2f}**  
                📈 Persentase: **{percent:.2f} %**  
                ✅ Cek {max_date} (Net): **{max_profit:.2f}**

                ---
                🎯 80% (challenge account): **{profit_80:.2f}**  
                🚀 90% (fast track): **{profit_90:.2f}**
                """
            )

            # Simpan ke CSV termasuk info nama & akun
            daily["ClientName"] = name
            daily["Account"] = account

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
