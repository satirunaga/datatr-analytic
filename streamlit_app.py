import streamlit as st
import pandas as pd
import io

# ==========================
# Styling Font, Warna & Icon
# ==========================
st.markdown(
    """
    <style>
    /* Import Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Roboto', sans-serif;
    }

    /* Warna judul */
    .stApp h1, h2, h3, h4 {
        color: #1E293B; /* abu gelap */
        font-weight: 700;
    }

    /* Badge status */
    .status-dot {
        height: 14px;
        width: 14px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 6px;
    }
    .dot-pass {
        background-color: #16A34A; /* hijau */
    }
    .dot-fail {
        background-color: #DC2626; /* merah */
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
        opacity: 0.25;
        transform: translate(-50%, -50%);
        z-index: -1;
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


# Proses file
if uploaded_files:
    for file in uploaded_files:
        st.write(f"📑 File: {file.name}")

        try:
            name, account, df = load_mt_report(file)
            st.write(f"👤 Nama Klien: **{name or '-'}**")
            st.write(f"🏦 Nomor Akun: **{account or '-'}**")

            daily = process_trades(df)

            total_profit = daily["NetProfit"].sum()
            max_row = daily.loc[daily["NetProfit"].idxmax()]
            max_profit = max_row["NetProfit"]
            max_date = max_row["CloseDate"]
            percent = (max_profit / total_profit) * 100 if total_profit != 0 else 0

            # Status dengan ikon bulat
            if percent < 30:
                status_html = '<span class="status-dot dot-pass"></span><b>PASS</b>'
            else:
                status_html = '<span class="status-dot dot-fail"></span><b>FAILED</b>'

            challenge_80 = total_profit * 0.80
            fasttrack_90 = total_profit * 0.90

            st.subheader("📊 Profit per hari (Net)")
            st.dataframe(daily)

            # Grafik
            st.subheader("📈 Grafik Profit Harian (Net)")
            st.line_chart(daily.set_index("CloseDate")["NetProfit"])

            # Ringkasan
            st.markdown(
                f"""
                🔥 Profit harian terbesar (Net): **{max_profit:.2f}** pada **{max_date}**  
                💰 Total profit (Net): **{total_profit:.2f}**  
                📉 Persentase: **{percent:.2f} %**  
                📝 Status: {status_html}  
                ✅ Cek {max_date} (Net): **{max_profit:.2f}**

                ---
                🎯 80% (challenge account): **{challenge_80:.2f}**  
                🚀 90% (fast track): **{fasttrack_90:.2f}**
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
