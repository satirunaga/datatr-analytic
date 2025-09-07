import streamlit as st
import pandas as pd
import io
import plotly.express as px

# ==========================
# CSS Styling + FontAwesome
# ==========================
st.markdown(
    """
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
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
        width: 800px;
        height: 800px;
        background: url("https://raw.githubusercontent.com/satirunaga/datatr-analytic/main/tplus_logoo.jpg") no-repeat center center;
        background-size: contain;
        opacity: 0.08;
        transform: translate(-50%, -50%);
        z-index: -1;
    }
    /* Card layout */
    .metrics-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 16px;
        margin-top: 20px;
    }
    .metric-card {
        padding: 18px;
        border-radius: 12px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.06);
        display: flex;
        align-items: center;
        gap: 12px;
        color: white;
    }
    .metric-icon {
        font-size: 22px;
    }
    .metric-content {
        display: flex;
        flex-direction: column;
    }
    .metric-title {
        font-size: 13px;
        opacity: 0.9;
    }
    .metric-value {
        font-size: 18px;
        font-weight: 600;
    }
    /* Warna tiap card */
    .card-profit { background: linear-gradient(135deg, #3b82f6, #2563eb); }
    .card-total { background: linear-gradient(135deg, #10b981, #059669); }
    .card-percent { background: linear-gradient(135deg, #f59e0b, #d97706); }
    .card-status-pass { background: linear-gradient(135deg, #22c55e, #16a34a); }
    .card-status-fail { background: linear-gradient(135deg, #ef4444, #dc2626); }
    .card-challenge { background: linear-gradient(135deg, #8b5cf6, #6d28d9); }
    .card-fast { background: linear-gradient(135deg, #ec4899, #db2777); }
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
    try:
        df_raw = pd.read_excel(file, header=None, dtype=str)
    except:
        file.seek(0)
        df_raw = pd.read_csv(file, header=None, dtype=str)

    name, account = None, None
    for _, row in df_raw.iterrows():
        joined = " ".join([str(x).strip() for x in row if pd.notna(x)])
        if joined.lower().startswith("name:"):
            name = joined.split(":", 1)[1].strip()
        elif joined.lower().startswith("account:"):
            account = joined.split(":", 1)[1].strip()

    header_row = None
    for i, row in df_raw.iterrows():
        values = [str(x).strip() for x in row.tolist()]
        if any("Time" in v for v in values) and any("Profit" in v for v in values):
            header_row = i
            break

    if header_row is None:
        raise ValueError("Tidak menemukan header tabel transaksi.")

    file.seek(0)
    try:
        df = pd.read_excel(file, skiprows=header_row)
    except:
        file.seek(0)
        df = pd.read_csv(file, skiprows=header_row)

    return name, account, df


def process_trades(df):
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


if uploaded_files:
    for file in uploaded_files:
        st.markdown(f"<p><b>📄 File:</b> {file.name}</p>", unsafe_allow_html=True)

        try:
            name, account, df = load_mt_report(file)

            st.markdown(f"<p><b>👤 Nama Klien:</b> {name or '-'}</p>", unsafe_allow_html=True)
            st.markdown(f"<p><b>🏦 Nomor Akun:</b> {account or '-'}</p>", unsafe_allow_html=True)

            daily = process_trades(df)

            total_profit = daily["NetProfit"].sum()
            max_row = daily.loc[daily["NetProfit"].idxmax()]
            max_profit = max_row["NetProfit"]
            max_date = max_row["CloseDate"]
            percent = (max_profit / total_profit) * 100 if total_profit != 0 else 0
            status = "PASS" if percent < 30 else "FAILED"

            challenge_80 = total_profit * 0.80
            fasttrack_90 = total_profit * 0.90

            st.subheader("📊 Profit per Hari (Net)")
            st.dataframe(daily)

            fig = px.line(daily, x="CloseDate", y="NetProfit",
                          title="Grafik Profit Harian (Net)",
                          markers=True,
                          labels={"NetProfit": "Net Profit", "CloseDate": "Tanggal"})
            st.plotly_chart(fig, use_container_width=True)

            # Metrics dengan warna
            st.markdown(
                f"""
                <div class="metrics-container">
                    <div class="metric-card card-profit">
                        <i class="fa-solid fa-fire metric-icon"></i>
                        <div class="metric-content">
                            <span class="metric-title">Profit Harian Terbesar</span>
                            <span class="metric-value">{max_profit:.2f} ({max_date})</span>
                        </div>
                    </div>
                    <div class="metric-card card-total">
                        <i class="fa-solid fa-sack-dollar metric-icon"></i>
                        <div class="metric-content">
                            <span class="metric-title">Total Profit (Net)</span>
                            <span class="metric-value">{total_profit:.2f}</span>
                        </div>
                    </div>
                    <div class="metric-card card-percent">
                        <i class="fa-solid fa-chart-line metric-icon"></i>
                        <div class="metric-content">
                            <span class="metric-title">Persentase</span>
                            <span class="metric-value">{percent:.2f}%</span>
                        </div>
                    </div>
                    <div class="metric-card {'card
