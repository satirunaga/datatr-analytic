import streamlit as st
import pandas as pd
import io
import traceback

# optional plotting lib (fallback ke st.line_chart jika tidak tersedia)
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except Exception:
    PLOTLY_AVAILABLE = False

# ==========================
# CSS Styling + FontAwesome + watermark
# ==========================
st.markdown(
    """
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
    /* basic page */
    .stApp {
        background: none;
        font-family: 'Inter', sans-serif;
    }

    /* watermark logo di tengah (samar) */
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

    /* Metrics grid */
    .metrics-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 16px;
        margin-top: 18px;
        margin-bottom: 18px;
    }

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

    .metric-icon { font-size: 22px; width: 40px; text-align: center; opacity: 0.95; }
    .metric-content { display:flex; flex-direction:column; }
    .metric-title { font-size: 13px; opacity: 0.9; margin-bottom: 6px; }
    .metric-value { font-size: 18px; font-weight: 700; }

    /* gradient color classes */
    .card-profit { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); }
    .card-total { background: linear-gradient(135deg,#10b981 0%,#059669 100%); }
    .card-percent { background: linear-gradient(135deg,#f59e0b 0%,#d97706 100%); }
    .card-status-pass { background: linear-gradient(135deg,#22c55e 0%,#16a34a 100%); }
    .card-status-fail { background: linear-gradient(135deg,#ef4444 0%,#dc2626 100%); }
    .card-challenge { background: linear-gradient(135deg,#8b5cf6 0%,#6d28d9 100%); }
    .card-fast { background: linear-gradient(135deg,#ec4899 0%,#db2777 100%); }

    /* smaller responsiveness tweaks */
    @media (max-width: 640px) {
        .metric-title { font-size: 12px; }
        .metric-value { font-size: 16px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<h1 style="margin-bottom:6px;"><i class="fa-solid fa-chart-line"></i> Analisis Laporan Trading MetaTrader</h1>', unsafe_allow_html=True)

# ==========================
# File uploader
# ==========================
uploaded_files = st.file_uploader(
    "Upload file laporan trading (CSV / XLSX)",
    type=["csv", "xlsx"],
    accept_multiple_files=True
)

# ==========================
# Helpers: load & process
# ==========================
def load_mt_report(file):
    """Baca file (excel/csv) tanpa mengasumsikan header, cari Name/Account & baris header tabel."""
    try:
        df_raw = pd.read_excel(file, header=None, dtype=str)
    except Exception:
        file.seek(0)
        df_raw = pd.read_csv(file, header=None, dtype=str)

    name, account = None, None

    # fleksibel: gabungkan sel di tiap baris untuk meng-detect Name/Account
    for _, row in df_raw.iterrows():
        joined = " ".join([str(x).strip() for x in row if pd.notna(x)])
        low = joined.lower()
        if low.startswith("name:"):
            name = joined.split(":", 1)[1].strip()
        elif low.startswith("account:"):
            account = joined.split(":", 1)[1].strip()

    # cari header tabel (baris yang mengandung kata time & profit)
    header_row = None
    for i, row in df_raw.iterrows():
        values = [str(x).strip() for x in row.tolist() if pd.notna(x)]
        lowvals = [v.lower() for v in values]
        if any("time" in v for v in lowvals) and any("profit" in v for v in lowvals):
            header_row = i
            break

    if header_row is None:
        raise ValueError("Tidak menemukan header tabel transaksi (baris yang mengandung 'Time' dan 'Profit').")

    # baca ulang mulai header_row
    file.seek(0)
    try:
        df = pd.read_excel(file, skiprows=header_row)
    except Exception:
        file.seek(0)
        df = pd.read_csv(file, skiprows=header_row)

    return name, account, df


def process_trades(df):
    """Normalisasi kolom & hitung NetProfit per CloseDate."""
    # normalisasi kolom lookup (case-insensitive)
    cols = {str(c).lower(): c for c in df.columns}

    # cari kolom tanggal close & profit
    # prefer exact names first, fallback to contains
    close_col = None
    for key in ("time.1", "close time", "close", "time"):
        if key in cols:
            close_col = cols[key]
            break
    if not close_col:
        close_col = next((cols[c] for c in cols if ("close" in c or "time" in c)), None)

    profit_col = next((cols[c] for c in cols if "profit" in c), None)
    swap_col = next((cols[c] for c in cols if "swap" in c), None)
    comm_col = next((cols[c] for c in cols if "commission" in c or "comm" in c), None)

    if close_col is None or profit_col is None:
        raise ValueError("Kolom Time/Close atau Profit tidak ditemukan di file (cek nama kolom).")

    # parsing & cleaning
    df[close_col] = pd.to_datetime(df[close_col], errors="coerce")
    df = df.dropna(subset=[close_col])
    df["CloseDate"] = pd.to_datetime(df[close_col]).dt.date

    def to_num(col):
        # handle missing column gracefully
        if col is None:
            return pd.Series(0, index=df.index)
        s = df[col].astype(str).str.replace(",", "").str.replace(" ", "")
        return pd.to_numeric(s, errors="coerce").fillna(0)

    df["Profit"] = to_num(profit_col)
    df["Swap"] = to_num(swap_col)
    df["Commission"] = to_num(comm_col)
    df["NetProfit"] = df["Profit"] + df["Swap"] + df["Commission"]

    daily = (
        df.groupby("CloseDate", as_index=False)
          .agg(GrossProfit=("Profit", "sum"),
               Swap=("Swap", "sum"),
               Commission=("Commission", "sum"),
               NetProfit=("NetProfit", "sum"))
    )

    # sort by date
    daily = daily.sort_values("CloseDate").reset_index(drop=True)
    return daily

# ==========================
# Main loop: proses file-file uploaded
# ==========================
if uploaded_files:
    for file in uploaded_files:
        st.markdown(f'<div style="margin-bottom:8px;"><strong>File:</strong> {file.name}</div>', unsafe_allow_html=True)

        try:
            name, account, df = load_mt_report(file)
            st.markdown(f'<div style="margin-bottom:4px;"><strong>Nama Klien:</strong> {name or "-"}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="margin-bottom:10px;"><strong>Nomor Akun:</strong> {account or "-"}</div>', unsafe_allow_html=True)

            daily = process_trades(df)

            if daily.empty:
                st.warning("Tabel hasil per-hari kosong setelah proses. Periksa format file.")
                continue

            total_profit = float(daily["NetProfit"].sum())
            idx = daily["NetProfit"].idxmax()
            max_row = daily.loc[idx]
            max_profit = float(max_row["NetProfit"])
            max_date = max_row["CloseDate"]
            percent = (max_profit / total_profit) * 100 if total_profit != 0 else 0.0

            status = "PASS" if percent < 30 else "FAILED"
            status_class = "card-status-pass" if status == "PASS" else "card-status-fail"

            challenge_80 = total_profit * 0.80
            fasttrack_90 = total_profit * 0.90

            # Tabel per-hari
            st.subheader("Profit per Hari (Net)")
            # tampilkan dengan formatting sederhana
            st.dataframe(daily.assign(
                GrossProfit=daily["GrossProfit"].map("{:,.2f}".format),
                Swap=daily["Swap"].map("{:,.2f}".format),
                Commission=daily["Commission"].map("{:,.2f}".format),
                NetProfit=daily["NetProfit"].map("{:,.2f}".format),
            ))

            # Grafik: line chart (Plotly jika tersedia)
            st.subheader("Grafik Profit Harian (Net)")
            try:
                plot_df = daily.copy()
                plot_df["CloseDate"] = pd.to_datetime(plot_df["CloseDate"])
                if PLOTLY_AVAILABLE:
                    fig = px.line(plot_df, x="CloseDate", y="NetProfit", markers=True,
                                  labels={"NetProfit": "Net Profit", "CloseDate": "Tanggal"},
                                  title="")
                    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.line_chart(plot_df.set_index("CloseDate")["NetProfit"])
            except Exception as e_plot:
                st.error("Gagal menampilkan grafik interaktif. Menampilkan chart sederhana sebagai fallback.")
                st.line_chart(daily.set_index("CloseDate")["NetProfit"])
                st.text(traceback.format_exc())

            # Metrics (colored cards) — dibangun sebagai HTML
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

                <div class="metric-card {status_class}">
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

            # Download CSV
            output = io.BytesIO()
            daily_out = daily.copy()
            daily_out.insert(0, "Account", account or "-")
            daily_out.insert(0, "ClientName", name or "-")
            daily_out.to_csv(output, index=False)
            st.download_button(
                label="Download hasil per hari (CSV)",
                data=output.getvalue(),
                file_name=f"daily_profit_{file.name}.csv",
                mime="text/csv",
                key=f"dl_{file.name}"
            )

        except Exception as e:
            st.error(f"Gagal memproses file {file.name}: {e}")
            st.text(traceback.format_exc())
