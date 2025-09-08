import streamlit as st
import pandas as pd
import io

# optional: plotly (fallback ke st.line_chart jika tidak ada)
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except Exception:
    PLOTLY_AVAILABLE = False

# ==========================
# Simple CSS watermark + fonts
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
        pointer-events: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📊 Analisis Laporan Trading MetaTrader")

# --------------------------
# Uploader
# --------------------------
uploaded_files = st.file_uploader(
    "Upload file laporan trading (CSV/XLSX)",
    type=["csv", "xlsx"],
    accept_multiple_files=True,
)

# --------------------------
# Helper: load report and detect header row
# --------------------------
def load_mt_report(file):
    """
    Baca file (xlsx/csv) tanpa asumsi header, deteksi 'Name:' & 'Account:' di top rows,
    lalu cari baris header (mengandung 'Time' dan 'Profit') dan baca DataFrame dari situ.
    """
    try:
        df_raw = pd.read_excel(file, header=None, dtype=str)
    except Exception:
        file.seek(0)
        df_raw = pd.read_csv(file, header=None, dtype=str)

    name = None
    account = None

    # cari Name: dan Account: (gabungkan semua kolom tiap baris)
    for _, row in df_raw.iterrows():
        joined = " ".join([str(x).strip() for x in row if pd.notna(x)])
        low = joined.lower()
        if low.startswith("name:"):
            name = joined.split(":", 1)[1].strip()
        elif low.startswith("account:"):
            account = joined.split(":", 1)[1].strip()

    # cari header row: baris yang mengandung 'time' & 'profit'
    header_row = None
    for i, row in df_raw.iterrows():
        vals = [str(x).strip() for x in row.tolist() if pd.notna(x)]
        lowvals = [v.lower() for v in vals]
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

# --------------------------
# Helper: proses trades berdasarkan OPEN TIME
# --------------------------
def process_trades_by_open(df):
    """
    Hitung profit harian berdasarkan Open Time.
    Mengembalikan DataFrame 'daily' dengan kolom:
      OpenDate, GrossProfit, Swap, Commission, NetProfit
    """
    # buat mapping lowercase -> original column name
    cols = {str(c).lower(): c for c in df.columns}

    # Preferensi kolom OPEN: cari 'time' (biasanya open), 'open time', atau 'open'
    open_col = None
    for cand in ("time", "open time", "open"):
        if cand in cols:
            open_col = cols[cand]
            break

    # kolom profit, swap, commission (robust search)
    profit_col = None
    for cand in ("profit", "net profit"):
        if cand in cols:
            profit_col = cols[cand]
            break

    swap_col = next((cols[c] for c in cols if "swap" in c), None)
    comm_col = next((cols[c] for c in cols if "commission" in c or "comm" in c), None)

    if open_col is None or profit_col is None:
        raise ValueError("Kolom Open Time atau Profit tidak ditemukan. Periksa header file.")

    # Convert Open Time ke datetime
    df[open_col] = pd.to_datetime(df[open_col], errors="coerce", infer_datetime_format=True)

    # Jika terlalu banyak NaT, coba dayfirst=True (fallback)
    if df[open_col].isna().sum() > len(df) * 0.4:
        df[open_col] = pd.to_datetime(df[open_col], errors="coerce", dayfirst=True)

    df = df.dropna(subset=[open_col]).copy()
    df["OpenDate"] = df[open_col].dt.date

    # Numeric parsing sederhana (pandas numeric coercion). Jika anda butuh parsing kompleks
    # (contoh: '1,234.56' vs '1.234,56' atau '(123)'), kita bisa ganti dengan smart parser.
    df["Profit"] = pd.to_numeric(df[profit_col], errors="coerce").fillna(0)
    df["Swap"] = pd.to_numeric(df[swap_col], errors="coerce").fillna(0) if swap_col else 0
    df["Commission"] = pd.to_numeric(df[comm_col], errors="coerce").fillna(0) if comm_col else 0

    df["NetProfit"] = df["Profit"] + df["Swap"] + df["Commission"]

    # group by OpenDate
    daily = (
        df.groupby("OpenDate", as_index=False)
          .agg(GrossProfit=("Profit", "sum"),
               Swap=("Swap", "sum"),
               Commission=("Commission", "sum"),
               NetProfit=("NetProfit", "sum"))
    )

    daily = daily.sort_values("OpenDate").reset_index(drop=True)
    return daily

# --------------------------
# Main processing per uploaded file
# --------------------------
if uploaded_files:
    for idx, uploaded_file in enumerate(uploaded_files):
        st.markdown(f"**File:** {uploaded_file.name}")
        try:
            name, account, df = load_mt_report(uploaded_file)

            st.markdown(f"**Nama Klien:** {name or '-'}  \n**Nomor Akun:** {account or '-'}")

            # proses berdasarkan Open Time
            daily = process_trades_by_open(df)

            if daily.empty:
                st.warning("Hasil per-hari kosong setelah proses. Periksa format tanggal kolom Open Time.")
                continue

            # Tampilkan tabel per-hari
            st.subheader("📊 Profit per Hari (Net) — berdasarkan Open Time")
            # tampilkan angka format rapi
            daily_display = daily.copy()
            for col in ("GrossProfit", "Swap", "Commission", "NetProfit"):
                daily_display[col] = daily_display[col].map(lambda x: f"{x:,.2f}")
            st.dataframe(daily_display)

            # Summary metrics
            total_profit = float(daily["NetProfit"].sum())
            idx_max = daily["NetProfit"].idxmax()
            max_profit = float(daily.loc[idx_max, "NetProfit"])
            max_date = daily.loc[idx_max, "OpenDate"]
            percent = (max_profit / total_profit * 100) if total_profit != 0 else 0.0
            status = "PASS" if percent < 30 else "FAILED"
            challenge_80 = total_profit * 0.80
            fasttrack_90 = total_profit * 0.90

            # Grafik line chart (plotly bila ada)
            st.subheader("Grafik Profit Harian (Net)")
            plot_df = daily.copy()
            plot_df["OpenDate"] = pd.to_datetime(plot_df["OpenDate"])
            if PLOTLY_AVAILABLE:
                fig = px.line(plot_df, x="OpenDate", y="NetProfit", markers=True,
                              labels={"NetProfit": "Net Profit", "OpenDate": "Tanggal"},
                              title="Grafik Profit Harian (berdasarkan Open Time)")
                fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.line_chart(plot_df.set_index("OpenDate")["NetProfit"])

            # Metrics using columns (Streamlit-native) — safe & no raw HTML issues
            st.subheader("Ringkasan")
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("Profit Harian Terbesar", f"{max_profit:,.2f}", str(max_date))
            c2.metric("Total Profit (Net)", f"{total_profit:,.2f}")
            c3.metric("Persentase kontribusi", f"{percent:.2f}%")
            c4.metric("Status", status)
            c5.metric("80% (challenge)", f"{challenge_80:,.2f}")
            c6.metric("90% (fast track)", f"{fasttrack_90:,.2f}")

            # Download hasil per-hari (CSV)
            out_buf = io.BytesIO()
            daily_out = daily.copy()
            daily_out.insert(0, "Account", account or "-")
            daily_out.insert(0, "ClientName", name or "-")
            # simpan sebagai CSV bytes
            daily_out.to_csv(out_buf, index=False)
            st.download_button(
                label="💾 Download hasil per hari (CSV)",
                data=out_buf.getvalue(),
                file_name=f"daily_profit_{uploaded_file.name}.csv",
                mime="text/csv",
                key=f"dl_{idx}_{uploaded_file.name}"
            )

        except Exception as e:
            st.error(f"Gagal memproses file {uploaded_file.name}: {e}")
            # tampilkan traceback singkat supaya mudah debug di deploy logs
            import traceback as tb
            st.text(tb.format_exc())
