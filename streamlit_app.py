import streamlit as st
import pandas as pd
import io
import plotly.express as px

# ==========================
# CSS untuk watermark + metric cards
# ==========================
st.markdown(
    """
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">

    <style>
    /* watermark logo */
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
        pointer-events: none;
    }

    /* metrics grid */
    .metrics-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 16px;
        margin-top: 18px;
        margin-bottom: 18px;
    }

    /* card */
    .metric-card {
        padding: 16px;
        border-radius: 12px;
        box-shadow: 0 6px 20px rgba(16,24,40,0.06);
        display: flex;
        align-items: center;
        gap: 14px;
        color: #fff;
        min-height: 80px;
    }
    .metric-icon { font-size: 22px; width: 44px; text-align: center; opacity: 0.95; }
    .metric-content { display:flex; flex-direction:column; }
    .metric-title { font-size: 13px; opacity: 0.95; margin-bottom: 6px; }
    .metric-value { font-size: 18px; font-weight: 700; }

    /* gradient color classes */
    .card-profit { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); }
    .card-total { background: linear-gradient(135deg,#10b981 0%,#059669 100%); }
    .card-percent{ background: linear-gradient(135deg,#f59e0b 0%,#d97706 100%); }
    .card-status-pass { background: linear-gradient(135deg,#22c55e 0%,#16a34a 100%); }
    .card-status-fail { background: linear-gradient(135deg,#ef4444 0%,#dc2626 100%); }
    .card-challenge { background: linear-gradient(135deg,#8b5cf6 0%,#6d28d9 100%); }
    .card-fast { background: linear-gradient(135deg,#ec4899 0%,#db2777 100%); }

    /* responsive tweaks */
    @media (max-width: 640px) {
        .metric-title { font-size: 12px; }
        .metric-value { font-size: 16px; }
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ==========================
# Judul aplikasi
# ==========================
st.title("📊 Analisis Laporan Trading MetaTrader")

# Upload file laporan
uploaded_files = st.file_uploader(
    "Upload file laporan trading (CSV / XLSX)",
    type=["csv", "xlsx"],
    accept_multiple_files=True
)

# ==========================
# Fungsi helper
# ==========================
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

    # Identifikasi kolom
    close_col = next((cols[k] for k in ["time.1", "close time", "close"] if k in cols), None)
    profit_col = next((cols[k] for k in ["profit", "net profit"] if k in cols), None)
    swap_col = next((cols[k] for k in cols if "swap" in k), None)
    comm_col = next((cols[k] for k in cols if "commission" in k or "comm" in k), None)

    if close_col is None or profit_col is None:
        raise ValueError("Kolom Time/Close atau Profit tidak ditemukan.")

    # Parsing data
    df[close_col] = pd.to_datetime(df[close_col], errors="coerce")
    df["CloseDate"] = df[close_col].dt.date

    df["Profit"] = pd.to_numeric(df[profit_col], errors="coerce").fillna(0)
    df["Swap"] = pd.to_numeric(df[swap_col], errors="coerce").fillna(0) if swap_col else 0
    df["Commission"] = pd.to_numeric(df[comm_col], errors="coerce").fillna(0) if comm_col else 0

    df["NetProfit"] = df["Profit"] + df["Swap"] + df["Commission"]

    # Hitung profit harian
    daily = df.groupby("CloseDate").agg(
        GrossProfit=("Profit", "sum"),
        Swap=("Swap", "sum"),
        Commission=("Commission", "sum"),
        NetProfit=("NetProfit", "sum")
    ).reset_index()

    return daily


# ==========================
# Proses file upload
# ==========================
if uploaded_files:
    for file in uploaded_files:
        st.write(f"📑 File: {file.name}")

        try:
            name, account, df = load_mt_report(file)
            st.write(f"👤 Nama Klien: **{name or '-'}**")
            st.write(f"🏦 Nomor Akun: **{account or '-'}**")

            daily = process_trades(df)

            # Ringkasan
            total_profit = daily["NetProfit"].sum()
            max_row = daily.loc[daily["NetProfit"].idxmax()]
            max_profit = max_row["NetProfit"]
            max_date = max_row["CloseDate"]
            percent = (max_profit / total_profit) * 100 if total_profit != 0 else 0

            # Tentukan status
            status = "PASS" if percent < 30 else "FAILED"

            # Target 80% & 90%
            challenge_80 = total_profit * 0.80
            fasttrack_90 = total_profit * 0.90

            # ======================
            # Metrics cards (HTML + CSS)
            # ======================
            metrics_html = f"""
            <div class="metrics-container">

                <div class="metric-card card-profit">
                    <i class="fa-solid fa-fire metric-icon"></i>
                    <div class="metric-content">
                        <span class="metric-title">Profit Harian Terbesar</span>
                        <span class="metric-value">{max_profit:,.2f} ({max_date})</span>
                    </div>
                </div>

                <div class="metric-card card-total">
                    <i class="fa-solid fa-sack-dollar metric-icon"></i>
                    <div class="metric-content">
                        <span class="metric-title">Total Profit (Net)</span>
                        <span class="metric-value">{total_profit:,.2f}</span>
                    </div>
                </div>

                <div class="metric-card card-percent">
                    <i class="fa-solid fa-chart-line metric-icon"></i>
                    <div class="metric-content">
                        <span class="metric-title">Persentase</span>
                        <span class="metric-value">{percent:.2f}%</span>
                    </div>
                </div>

                <div class="metric-card {'card-status-pass' if status=='PASS' else 'card-status-fail'}">
                    <i class="fa-solid fa-clipboard-check metric-icon"></i>
                    <div class="metric-content">
                        <span class="metric-title">Status</span>
                        <span class="metric-value">{status}</span>
                    </div>
                </div>

                <div class="metric-card card-challenge">
                    <i class="fa-solid fa-bullseye metric-icon"></i>
                    <div class="metric-content">
                        <span class="metric-title">80% Challenge</span>
                        <span class="metric-value">{challenge_80:,.2f}</span>
                    </div>
                </div>

                <div class="metric-card card-fast">
                    <i class="fa-solid fa-rocket metric-icon"></i>
                    <div class="metric-content">
                        <span class="metric-title">90% Fast Track</span>
                        <span class="metric-value">{fasttrack_90:,.2f}</span>
                    </div>
                </div>

            </div>
            """
            st.markdown(metrics_html, unsafe_allow_html=True)

            # ======================
            # Grafik Profit Harian
            # ======================
            fig = px.line(
                daily,
                x="CloseDate",
                y="NetProfit",
                markers=True,
                title="📈 Grafik Profit Harian (Net)"
            )
            st.plotly_chart(fig, use_container_width=True)

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
