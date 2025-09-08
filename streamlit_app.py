# streamlit_app.py
import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# optional plotly for nicer chart
try:
    import plotly.express as px
    PLOTLY = True
except Exception:
    PLOTLY = False

st.set_page_config(page_title="Analisis Laporan Trading (Open-time daily)", layout="wide")
st.title("📊 Analisis Laporan Trading MetaTrader — Daily by Open Time")

# ----------------------------
# Upload & options
# ----------------------------
uploaded_files = st.file_uploader(
    "Upload file laporan trading (CSV/XLSX)", type=["csv", "xlsx"], accept_multiple_files=True
)

st.sidebar.header("Pengaturan")
use_net = st.sidebar.checkbox("Gunakan NetProfit (Profit+Swap+Commission)", value=False)
threshold_pct = st.sidebar.number_input("Threshold % untuk PASS (jika < threshold → PASS)", value=30.0, step=1.0)
symbol_filter = st.sidebar.text_input("Filter symbol (kosong=semua). Contoh: BTCUSD,ETHUSD", value="")
symbol_list = [s.strip().upper() for s in symbol_filter.split(",") if s.strip()]

# ----------------------------
# util: robust numeric parsing
# ----------------------------
def smart_to_numeric(series):
    s = series.astype(str).fillna("").str.strip()
    # handle parentheses -> negative
    s = s.str.replace(r'^\((.*)\)$', r'-\1', regex=True)
    # remove non-breaking spaces
    s = s.str.replace('\xa0', '', regex=False)
    # remove thousands separators: spaces and commas (assume decimal point is '.')
    s = s.str.replace(',', '', regex=False).str.replace(' ', '', regex=False)
    # empty to NaN
    s = s.replace({'': np.nan, 'nan': np.nan})
    return pd.to_numeric(s, errors='coerce')

# ----------------------------
# detect header row and load DataFrame
# ----------------------------
def detect_header_and_read(fileobj):
    """
    Read raw without header, find a header row that contains 'Time' and 'Profit' (case-insensitive),
    then read data with that header. Returns (name, account, df).
    """
    try:
        raw = pd.read_excel(fileobj, header=None, dtype=str)
    except Exception:
        fileobj.seek(0)
        raw = pd.read_csv(fileobj, header=None, dtype=str)

    name = None
    account = None
    # find name/account lines
    for _, row in raw.iterrows():
        joined = " ".join([str(x).strip() for x in row if pd.notna(x)])
        low = joined.lower()
        if low.startswith("name:"):
            name = joined.split(":", 1)[1].strip()
        elif low.startswith("account:"):
            account = joined.split(":", 1)[1].strip()

    # find header row candidates
    header_row = None
    for i, row in raw.iterrows():
        vals = [str(x).strip().lower() for x in row.tolist() if pd.notna(x)]
        if any("time" in v for v in vals) and any("profit" in v for v in vals):
            header_row = i
            break

    if header_row is None:
        # fallback: try first 10 rows
        header_row = 0

    fileobj.seek(0)
    try:
        df = pd.read_excel(fileobj, skiprows=header_row)
    except Exception:
        fileobj.seek(0)
        df = pd.read_csv(fileobj, skiprows=header_row)

    return name, account, df

# ----------------------------
# detect proper profit column
# ----------------------------
def detect_profit_col(df):
    lc = {str(c).lower(): c for c in df.columns}
    # 1) direct name containing 'profit'
    for key in lc:
        if "profit" in key:
            return lc[key]
    # 2) check rightmost numeric-ish columns (likely Profit is on the right)
    tail_cols = list(df.columns[-6:])  # examine last up to 6 columns
    candidates = []
    for c in tail_cols:
        ser = smart_to_numeric(df[c])
        if ser.notna().sum() > 0:
            median_abs = ser.abs().median(skipna=True)
            neg_ratio = float((ser < 0).mean())
            candidates.append((c, median_abs if not np.isnan(median_abs) else 1e18, neg_ratio))
    if candidates:
        # prefer smallest median_abs (profit small vs price large)
        candidates.sort(key=lambda x: (x[1], -x[2]))
        return candidates[0][0]
    # 3) fallback: choose any numeric column with many values and relatively small median
    stats = []
    for c in df.columns:
        ser = smart_to_numeric(df[c])
        if ser.notna().sum() == 0:
            continue
        stats.append((c, ser.abs().median(skipna=True), float((ser<0).mean())))
    if not stats:
        raise ValueError("Tidak menemukan kolom numeric untuk Profit.")
    stats.sort(key=lambda x: (x[1], -x[2]))
    return stats[0][0]

# ----------------------------
# main processing: group by OPEN date but require CLOSE valid
# ----------------------------
def process_by_open(df, use_net, symbol_list):
    # map lowercase->original
    lc = {str(c).lower(): c for c in df.columns}
    # pick open col (prefer 'time' exact)
    open_col = lc.get("time") or next((lc[k] for k in lc if "open time" in k or k=="open"), None)
    close_col = lc.get("time.1") or lc.get("close time") or lc.get("close")
    if open_col is None or close_col is None:
        raise ValueError("Kolom Open Time atau Close Time tidak ditemukan (periksa header).")
    profit_col = detect_profit_col(df)
    swap_col = next((lc[k] for k in lc if "swap" in k), None)
    comm_col = next((lc[k] for k in lc if "commission" in k or "comm" in k), None)
    symbol_col = next((lc[k] for k in lc if "symbol" in k), None)

    df2 = df.copy()
    # parse close time to decide closed trades
    df2["_close_parsed"] = pd.to_datetime(df2[close_col], errors="coerce", infer_datetime_format=True)
    if df2["_close_parsed"].isna().mean() > 0.5:
        df2["_close_parsed"] = pd.to_datetime(df2[close_col], errors="coerce", dayfirst=True)
    df_valid = df2[df2["_close_parsed"].notna()].copy()
    if df_valid.shape[0] == 0:
        raise ValueError("Tidak ada transaksi 'closed' (Close Time valid) yang terdeteksi.")

    # parse open time
    df_valid["_open_parsed"] = pd.to_datetime(df_valid[open_col], errors="coerce", infer_datetime_format=True)
    if df_valid["_open_parsed"].isna().mean() > 0.5:
        df_valid["_open_parsed"] = pd.to_datetime(df_valid[open_col], errors="coerce", dayfirst=True)
    df_valid = df_valid[df_valid["_open_parsed"].notna()].copy()
    df_valid["OpenDate"] = df_valid["_open_parsed"].dt.date

    # numeric columns
    df_valid["_profit_num"] = smart_to_numeric(df_valid[profit_col]).fillna(0)
    df_valid["_swap_num"] = smart_to_numeric(df_valid[swap_col]).fillna(0) if swap_col else 0
    df_valid["_comm_num"] = smart_to_numeric(df_valid[comm_col]).fillna(0) if comm_col else 0
    df_valid["_net"] = df_valid["_profit_num"] + df_valid["_swap_num"] + df_valid["_comm_num"]

    # symbol filter
    if symbol_list and symbol_col:
        df_valid = df_valid[df_valid[symbol_col].astype(str).str.upper().isin(symbol_list)]

    # aggregation by OpenDate
    daily = df_valid.groupby("OpenDate", as_index=False).agg(
        GrossProfit=("_profit_num", "sum"),
        Swap=("_swap_num", "sum"),
        Commission=("_comm_num", "sum"),
        NetProfit=("_net", "sum")
    ).sort_values("OpenDate").reset_index(drop=True)

    daily["ChosenSum"] = daily["NetProfit"] if use_net else daily["GrossProfit"]
    return daily, df_valid, {"open_col": open_col, "close_col": close_col, "profit_col": profit_col,
                              "swap_col": swap_col, "comm_col": comm_col, "symbol_col": symbol_col}

# ----------------------------
# Run processing for uploaded files
# ----------------------------
if uploaded_files:
    for idx, f in enumerate(uploaded_files):
        st.markdown(f"### 📄 File: {f.name}")
        try:
            name, account, df = detect_header_and_read(f)
            st.write("👤 Nama Klien:", name or "-")
            st.write("🏦 Nomor Akun:", account or "-")

            daily, df_valid, meta = process_by_open(df, use_net=use_net, symbol_list=symbol_list)

            if daily.empty:
                st.warning("Tidak ada data per-hari setelah filter.")
                continue

            # formatting display
            disp = daily.copy()
            for c in ["GrossProfit", "Swap", "Commission", "NetProfit", "ChosenSum"]:
                disp[c] = disp[c].map(lambda x: f"{x:,.2f}")

            st.subheader("📊 Profit per hari (berdasarkan Open Time)")
            st.dataframe(disp)

            # summary
            total = float(daily["ChosenSum"].sum())
            imax = daily["ChosenSum"].idxmax()
            max_profit = float(daily.loc[imax, "ChosenSum"])
            max_date = daily.loc[imax, "OpenDate"]
            pct = (max_profit / total * 100) if total != 0 else 0.0
            status = "PASS" if pct < float(threshold_pct) else "FAILED"
            challenge80 = total * 0.80
            fast90 = total * 0.90

            st.markdown(
                f"🔥 **Profit harian terbesar:** **{max_profit:,.2f}** pada **{max_date}**  \n"
                f"💰 **Total profit:** **{total:,.2f}**  \n"
                f"📈 **Persentase kontribusi:** **{pct:.2f}%**  \n"
                f"📝 **Status:** **{status}**"
            )
            st.markdown(f"🎯 80% (challenge): **{challenge80:,.2f}** &nbsp;&nbsp; 🚀 90% (fast track): **{fast90:,.2f}**")

            # Show debug: sample trades that contributed to max_date (so you can verify 109.40)
            st.subheader(f"Contoh baris trades untuk tanggal Open = {max_date} (sample untuk verifikasi)")
            sample_rows = df_valid[df_valid["OpenDate"] == max_date].copy()
            # show relevant columns (open, pos, symbol, volume, open price, close time, close price, commission, swap, profit_num)
            show_cols = []
            for cand in [meta["open_col"], "Position", meta["profit_col"], meta["close_col"], meta["swap_col"], meta["comm_col"], meta["symbol_col"]]:
                if cand and cand in sample_rows.columns:
                    show_cols.append(cand)
            # always include parsed and numeric columns
            sample_rows["_profit_num"] = sample_rows["_profit_num"]
            sample_rows["_swap_num"] = sample_rows["_swap_num"]
            sample_rows["_comm_num"] = sample_rows["_comm_num"]
            for c in ["_profit_num", "_swap_num", "_comm_num", "_net"]:
                if c in sample_rows.columns and c not in show_cols:
                    show_cols.append(c)
            # Add open/close parsed
            if "_open_parsed" in sample_rows.columns:
                show_cols = ["_open_parsed"] + show_cols
            if "_close_parsed" in sample_rows.columns and "_close_parsed" not in show_cols:
                show_cols.append("_close_parsed")

            if sample_rows.empty:
                st.info("Tidak ada trades untuk tanggal max (cek format).")
            else:
                # format numeric columns for display
                sample_display = sample_rows[show_cols].copy()
                for c in ["_profit_num", "_swap_num", "_comm_num", "_net"]:
                    if c in sample_display.columns:
                        sample_display[c] = sample_display[c].map(lambda x: f"{x:,.2f}")
                st.dataframe(sample_display.head(50))

            # chart
            st.subheader("Grafik Profit Harian")
            plot_df = daily[["OpenDate", "ChosenSum"]].copy()
            plot_df["OpenDate"] = pd.to_datetime(plot_df["OpenDate"])
            plot_df = plot_df.sort_values("OpenDate")
            if PLOTLY:
                fig = px.line(plot_df, x="OpenDate", y="ChosenSum", markers=True,
                              labels={"ChosenSum": "Profit", "OpenDate": "Tanggal"},
                              title="Profit Harian")
                fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.line_chart(plot_df.set_index("OpenDate")["ChosenSum"])

            # download CSV
            out = io.BytesIO()
            out_df = daily.copy()
            out_df.insert(0, "Account", account or "-")
            out_df.insert(0, "ClientName", name or "-")
            out_df.to_csv(out, index=False)
            st.download_button(
                label="💾 Download hasil per hari (CSV)",
                data=out.getvalue(),
                file_name=f"daily_profit_{f.name}.csv",
                mime="text/csv",
                key=f"dl_{idx}_{f.name}"
            )

        except Exception as e:
            st.error(f"Gagal memproses file {f.name}: {e}")
            import traceback as tb
            st.text(tb.format_exc())
