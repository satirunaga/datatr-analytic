import streamlit as st
import pandas as pd
import io
import plotly.express as px

# ==========================
# Tambah watermark logo di tengah
# ==========================
st.markdown(
    """
    <style>
    .stApp {
        background: none;
        font-family: 'Inter', sans-serif;
    }
    .stApp::before {
        content: "";
        position: fixed;
        top: 50%;
        left: 50%;
        width: 600px;
        height: 600px;
        background: url("https://raw.githubusercontent.com/satirunaga/datatr-analytic/main/tplus_logoo.jpg") no-repeat center center;
        background-size: contain;
        opacity: 0.2;
        transform: translate(-50%, -50%);
        z-index: -1;
    }
    /* Card style */
    .metric-card {
        background: #ffffff;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        margin-bottom: 15px;
    }
    .metric-title {
        font-size: 14px;
        color: #666;
    }
    .metric-value {
        font-size: 20px;
        font-weight: 600;
        color: #222;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("📊 Analisis Laporan Trading MetaTrader")

# Upload file laporan
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

    # Cari 'Name:' dan 'Account:'
    for _, row in df_raw.iterrows():
        joined = " ".join([str(x).strip() for x in row if pd.notna(x)])
        if joined.lower().startswith("name:"):
            name = joined.split(":", 1)[1].strip()
        elif joined.lower().startswith("account:"):
            account = joined.split(":", 1)[1].strip()

    # Cari baris header tabel
    header_row = None
    for i, row in df_raw.iterrows():
        values = [str(x).strip() for x in row.tolist()]
        if any("Time" in v for v in values) and any("Profit" in v for v in values):
            header_row = i
            break

    if header_row is None:
        raise ValueError("Tidak menemukan header tabel transaksi.")

    # Baca ulang mulai dari baris header_row
    file.seek(0)
    try:
        df = pd.read_excel(file, skiprows=header_row)
    except:
        file.seek(0)
        df = pd.read_csv(file, skiprows=header_row)

    return name, account, df


def process_trades(df):
    """Menghitung profit harian berdasarkan Close Time"""
    cols = {c.lower(): c for c in df.columns}

    close_col = next((cols[k] for k in ["time.1", "close time", "close"] if k in cols), None)
    profit_col = next((cols[k] for k in ["profit", "net profit"] if k in cols), None)
    swap_col = next((cols[k] for k in cols if "swap" in k), None)
    comm_col = next((cols[k] for k in cols if "commission" in k or "comm" in k), None)

    if close_col is None or profit_col is None:
        raise ValueError("Kolom Time/Close atau Profit tidak ditemukan.")

    df[close_col] = pd.to_datetime(df[close_col], errors="coerce")
    df["CloseDate"] = df[close_col].dt.date

    df["Profit"] = pd.to_numeric(df[profit_col], errors="coerce").fillna(0)
    df["Swap"] = pd.to_numeric(df[swap_col], errors="coerce").fillna(0) if swap_col else 0
    df["Commission"] = pd.to_numeric(df[comm_col], errors="coerce").fillna(0) if comm_col else 0

    df["NetProfit"] = df["Profit"] + df["Swap"] + df["Commission"]

    daily = df.groupby("CloseDate").agg(
        GrossProfit=("Profit", "sum"),
        Swap=("Swap", "sum"),
        Commission=("Commission", "sum"),
        NetProfit=("NetProfit", "sum")
    ).reset_index()

    return daily


# Proses file yang diupload
if uploaded_files:
    for file in uploaded_files:
        st.markdown('<div class="metric-card">📄 <span class="metric-title">File:</span> '
                    f'<span class="metric-value">{file.name}</span></div>', unsafe_allow_html=True)

        try:
            name, account, df = load_mt_report(file)

            st.markdown('<div class="metric-card">👤 <span class="metric-title">Nama Klien:</span> '
                        f'<span class="metric-value">{name or "-"}</span></div>', unsafe_allow_html=True)

            st.markdown('<div class="metric-card">🏦 <span class="metric-title">Nomor Akun:</span> '
                        f'<span class="metric-value">{account or "-"}</span></div>', unsafe_allow_html=True)

            daily = process_trades(df)

            # Ringkasan
            total_profit = daily["NetProfit"].sum()
            max_row = daily.loc[daily["NetProfit"].idxmax()]
            max_profit = max_row["NetProfit"]
            max_date = max_row["CloseDate"]
            percent = (max_profit / total_profit) * 100 if total_profit != 0 else 0

            status = "✅ PASS" if percent < 30 else "❌ FAILED"

            challenge_80 = total_profit * 0.80
            fasttrack_90 = total_profit * 0.90

            # Tabel
            st.subheader("📊 Profit per Hari (Net)")
            st.dataframe(daily)

            # Grafik
            fig = px.bar(daily, x="CloseDate", y="NetProfit",
                         title="Grafik Profit Harian (Net)",
                         labels={"NetProfit": "Net Profit", "CloseDate": "Tanggal"})
            st.plotly_chart(fig, use_container_width=True)

            # Metrics
            st.markdown(
                f"""
                <div class="metric-card">🔥 <span class="metric-title">Profit Harian Terbesar:</span> 
                <span class="metric-value">{max_profit:.2f} pada {max_date}</span></div>
                
                <div class="metric-card">💰 <span class="metric-title">Total Profit (Net):</span> 
                <span class="metric-value">{total_profit:.2f}</span></div>
                
                <div class="metric-card">📈 <span class="metric-title">Persentase:</span> 
                <span class="metric-value">{percent:.2f}%</span></div>
                
                <div class="metric-card">📋 <span class="metric-title">Status:</span> 
                <span class="metric-value">{status}</span></div>
                
                <div class="metric-card">🎯 <span class="metric-title">80% Challenge:</span> 
                <span class="metric-value">{challenge_80:.2f}</span></div>
                
                <div class="metric-card">🚀 <span class="metric-title">90% Fast Track:</span> 
                <span class="metric-value">{fasttrack_90:.2f}</span></div>
                """,
                unsafe_allow_html=True
            )

            # Download hasil
            output = io.BytesIO()
            daily_out = daily.copy()
            daily_out.insert(0, "Account", account or "-")
            daily_out.insert(0, "ClientName", name or "-")
            daily_out.to_csv(output, index=False)

            st.download_button(
                label="💾 Download hasil per hari (CSV)",
                data=output.getvalue(),
                file_name=f"daily_profit_{file.name}.csv",
                mime="text/csv",
                key=f"dl_{file.name}"
            )

        except Exception as e:
            st.error(f"Gagal memproses file {file.name}: {e}")
