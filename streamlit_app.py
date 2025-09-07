import streamlit as st
import pandas as pd
import io


# ==========================
# Custom Style (Font + Icons + Logo Watermark)
# ==========================
st.markdown(
    """
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
    <style>
    /* Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Watermark logo */
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

# ==========================
# Title
# ==========================
st.markdown('<h1><i class="bi bi-bar-chart-fill"></i> Analisis Laporan Trading MetaTrader</h1>', unsafe_allow_html=True)

# ==========================
# Upload file
# ==========================
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


# ==========================
# Process uploaded files
# ==========================
if uploaded_files:
    for file in uploaded_files:
        st.markdown(f'<p><i class="bi bi-file-earmark-text"></i> File: <b>{file.name}</b></p>', unsafe_allow_html=True)

        try:
            name, account, df = load_mt_report(file)
            st.markdown(f'<p><i class="bi bi-person-circle"></i> Nama Klien: <b>{name or "-"}</b></p>', unsafe_allow_html=True)
            st.markdown(f'<p><i class="bi bi-bank"></i> Nomor Akun: <b>{account or "-"}</b></p>', unsafe_allow_html=True)

            daily = process_trades(df)

            total_profit = daily["NetProfit"].sum()
            max_row = daily.loc[daily["NetProfit"].idxmax()]
            max_profit = max_row["NetProfit"]
            max_date = max_row["CloseDate"]
            percent = (max_profit / total_profit) * 100 if total_profit != 0 else 0
            status = "PASS ✅" if percent < 30 else "FAILED ❌"

            challenge_80 = total_profit * 0.80
            fasttrack_90 = total_profit * 0.90

            # ========== Metrics (pakai card) ==========
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f'<div class="metric-card"><div class="metric-title"><i class="bi bi-cash-coin"></i> Total Profit</div><div class="metric-value">{total_profit:.2f}</div></div>', unsafe_allow_html=True)
            with col2:
                st.markdown(f'<div class="metric-card"><div class="metric-title"><i class="bi bi-graph-up"></i> Max Profit</div><div class="metric-value">{max_profit:.2f} ({max_date})</div></div>', unsafe_allow_html=True)
            with col3:
                st.markdown(f'<div class="metric-card"><div class="metric-title"><i class="bi bi-clipboard-check"></i> Status</div><div class="metric-value">{status}</div></div>', unsafe_allow_html=True)

            # ========== Grafik ==========
            st.subheader("📊 Grafik Profit Harian")
            fig = px.bar(daily, x="CloseDate", y="NetProfit", title="Net Profit Harian", template="simple_white")
            st.plotly_chart(fig, use_container_width=True)

            # ========== Download ==========
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
