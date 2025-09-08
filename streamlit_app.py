# streamlit_app.py
import streamlit as st
import pandas as pd
import io
import re
import numpy as np

# optional plotly, fallback ke st.line_chart bila tidak ada
try:
    import plotly.express as px
    PLOTLY = True
except Exception:
    PLOTLY = False

st.set_page_config(page_title="Analisis Laporan Trading", layout="wide")
st.title("📊 Analisis Laporan Trading MetaTrader (Daily by Open Time)")

# ----------------------
# Upload + opsi
# ----------------------
uploaded_files = st.file_uploader(
    "Upload file laporan trading (CSV/XLSX)",
    type=["csv", "xlsx"],
    accept_multiple_files=True,
)

st.markdown("**Pengaturan perhitungan**")
col1, col2 = st.columns([1,2])
with col1:
    use_net = st.checkbox("Gunakan NetProfit (Profit + Swap + Commission)", value=False)
    percent_threshold = st.number_input("Threshold % untuk PASS (jika < threshold → PASS)", value=30.0, step=1.0)
with col2:
    symbol_filter = st.text_input("Filter symbol (kosong = semua) — contoh: BTCUSD, gunakan koma untuk beberapa", value="")
    symbol_list = [s.strip().upper() for s in symbol_filter.split(",") if s.strip()] if symbol_filter.strip() else []

# ----------------------
# util: parsing angka "smart"
# ----------------------
def to_numeric_series(series):
    s = series.astype(str).fillna("").str.strip()
    # handle parentheses as negative
    s = s.str.replace(r'^\((.*)\)$', r'-\1', regex=True)
    # remove thousands separators (commas) and spaces, NB: this assumes decimal point is "."
    s = s.str.replace(",", "", regex=False).str.replace(" ", "", regex=False)
    # convert empty strings to NaN
    s = s.replace({"": np.nan, "nan": np.nan})
    return pd.to_numeric(s, errors="coerce")

# ----------------------
# detect header robustly and read df starting at header row
# ----------------------
def detect_header_and_read(fileobj, max_candidates_search=20):
    """
    Read raw file (no header), find valid header row (contains Time & Profit),
    try to re-read using that header and validate by checking datetime parsing.
    Returns name (if any), account (if any), df (with header).
    """
    # read raw without headers
    try:
        raw = pd.read_excel(fileobj, header=None, dtype=str)
    except Exception:
        fileobj.seek(0)
        raw = pd.read_csv(fileobj, header=None, dtype=str)

    name, account = None, None
    # find name/account by joining all columns in each row
    for _, r in raw.iterrows():
        joined = " ".join([str(x).strip() for x in r if pd.notna(x)])
        low = joined.lower()
        if low.startswith("name:"):
            name = joined.split(":", 1)[1].strip()
        elif low.startswith("account:"):
            account = joined.split(":", 1)[1].strip()

    # candidate header row indices: rows containing 'time' and 'profit' (case-ins)
    candidates = []
    for i, r in raw.iterrows():
        vals = [str(x).strip().lower() for x in r.tolist() if pd.notna(x)]
        if any("time" in v for v in vals) and any("profit" in v for v in vals):
            candidates.append(i)
        if len(candidates) >= max_candidates_search:
            break

    # fallback: try first 12 rows if none found
    if not candidates:
        candidates = list(range(0, min(12, len(raw))))

    # try each candidate: read df with skiprows=candidate and validate
    for hr in candidates:
        fileobj.seek(0)
        try:
            df_try = pd.read_excel(fileobj, skiprows=hr)
        except Exception:
            fileobj.seek(0)
            df_try = pd.read_csv(fileobj, skiprows=hr)
        # look for time-like column and try parse
        cols_lower = {str(c).lower(): c for c in df_try.columns}
        # pick preferred time columns to test
        for time_key in ("time", "open time", "time.1", "close time", "close"):
            if time_key in cols_lower:
                colname = cols_lower[time_key]
                parsed = pd.to_datetime(df_try[colname], errors="coerce", infer_datetime_format=True)
                non_null_ratio = parsed.notna().mean() if len(parsed) > 0 else 0.0
                # accept header if at least 20% of values parse as datetime
                if non_null_ratio >= 0.20:
                    return name, account, df_try
        # else try guess: if any column can be parsed as datetime >20% accept
        parsed_any = False
        for c in df_try.columns:
            parsed = pd.to_datetime(df_try[c], errors="coerce", infer_datetime_format=True)
            if parsed.notna().mean() >= 0.20:
                parsed_any = True
                break
        if parsed_any:
            return name, account, df_try

    # If none validated, still return using first candidate fallback (best-effort)
    fileobj.seek(0)
    try:
        df_final = pd.read_excel(fileobj, skiprows=candidates[0])
    except Exception:
        fileobj.seek(0)
        df_final = pd.read_csv(fileobj, skiprows=candidates[0])
    return name, account, df_final

# ----------------------
# detect which column is Profit (robust heuristics)
# ----------------------
def detect_profit_column(df):
    cols_map = {str(c).lower(): c for c in df.columns}
    # primary: any column name containing 'profit'
    candidates = [cols_map[c] for c in cols_map if "profit" in c]
    if candidates:
        # choose candidate whose numeric median abs is smallest (likely profit, not cumulative price)
        scored = []
        for c in candidates:
            ser = to_numeric_series(df[c])
            median_abs = ser.abs().median(skipna=True)
            neg_ratio = float((ser < 0).mean())
            scored.append((c, median_abs if not np.isnan(median_abs) else 1e18, neg_ratio))
        scored.sort(key=lambda x: (x[1], -x[2]))
        return scored[0][0]

    # fallback: among numeric-parsable columns choose one that looks like profit:
    stats = []
    for c in df.columns:
        ser = to_numeric_series(df[c])
        non_na = ser.notna().sum()
        if non_na == 0:
            continue
        median_abs = ser.abs().median(skipna=True)
        neg_ratio = float((ser < 0).mean())
        pct_small = float((ser.abs() < 1000).mean())
        stats.append((c, median_abs if not np.isnan(median_abs) else 1e18, neg_ratio, pct_small))
    if not stats:
        raise ValueError("Tidak menemukan kolom numeric apapun untuk dipakai sebagai Profit.")
    # prefer columns that have negative values OR many small values
    candidates2 = [s for s in stats if (s[2] > 0 or s[3] > 0.4)]
    if not candidates2:
        candidates2 = stats
    candidates2.sort(key=lambda x: (x[1], -x[2], -x[3]))
    return candidates2[0][0]

# ----------------------
# process: group by OPEN time but require CloseTime valid
# ----------------------
def process_by_open(df, use_net=False, symbol_list=None):
    """
    Steps:
    - detect open_col (Time), close_col (Time.1), profit_col (robust).
    - keep only rows with valid CloseTime (so trade is closed)
    - parse OpenTime & CloseTime; group by date(OpenTime)
    - compute GrossProfit, Swap, Commission, NetProfit
    """
    cols_lower = {str(c).lower(): c for c in df.columns}

    # detect open & close & swap & commission columns
    open_col = cols_lower.get("time") or next((cols_lower[k] for k in cols_lower if "open time" in k or k == "open"), None)
    close_col = cols_lower.get("time.1") or cols_lower.get("close time") or cols_lower.get("close")
    if open_col is None or close_col is None:
        raise ValueError("Tidak menemukan kolom Open Time ('Time') atau Close Time ('Time.1').")

    profit_col = detect_profit_column(df)
    swap_col = next((cols_lower[k] for k in cols_lower if "swap" in k), None)
    comm_col = next((cols_lower[k] for k in cols_lower if "commission" in k or "comm" in k), None)
    symbol_col = next((cols_lower[k] for k in cols_lower if "symbol" in k), None)

    # filter closed trades: attempt to parse close times robustly
    df2 = df.copy()
    # parse close time
    df2["__close_parsed"] = pd.to_datetime(df2[close_col], errors="coerce", infer_datetime_format=True)
    # fallback dayfirst if too many NaT
    if df2["__close_parsed"].isna().mean() > 0.5:
        df2["__close_parsed"] = pd.to_datetime(df2[close_col], errors="coerce", dayfirst=True)
    # keep only rows with parsed close time
    df_valid = df2[df2["__close_parsed"].notna()].copy()
    if df_valid.shape[0] == 0:
        raise ValueError("Tidak ada baris transaksi dengan Close Time valid — tidak ada transaksi closed ditemukan.")

    # parse open time
    df_valid["__open_parsed"] = pd.to_datetime(df_valid[open_col], errors="coerce", infer_datetime_format=True)
    if df_valid["__open_parsed"].isna().mean() > 0.5:
        df_valid["__open_parsed"] = pd.to_datetime(df_valid[open_col], errors="coerce", dayfirst=True)
    df_valid = df_valid[df_valid["__open_parsed"].notna()].copy()
    df_valid["OpenDate"] = df_valid["__open_parsed"].dt.date

    # numeric parse columns
    df_valid["_profit_num"] = to_numeric_series(df_valid[profit_col]).fillna(0)
    df_valid["_swap_num"] = to_numeric_series(df_valid[swap_col]).fillna(0) if swap_col else 0
    df_valid["_comm_num"] = to_numeric_series(df_valid[comm_col]).fillna(0) if comm_col else 0
    df_valid["_net"] = df_valid["_profit_num"] + df_valid["_swap_num"] + df_valid["_comm_num"]

    # symbol filter
    if symbol_list:
        if symbol_col:
            df_valid = df_valid[df_valid[symbol_col].astype(str).str.upper().isin(symbol_list)]
        else:
            # no symbol column, cannot filter
            pass

    # aggregate per OpenDate
    daily = (
        df_valid.groupby("OpenDate", as_index=False)
        .agg(
            GrossProfit=("_profit_num", "sum"),
            Swap=("_swap_num", "sum"),
            Commission=("_comm_num", "sum"),
            NetProfit=("_net", "sum"),
        )
        .sort_values("OpenDate")
        .reset_index(drop=True)
    )

    # chosen sum for display (depending on use_net)
    daily["ChosenSum"] = daily["NetProfit"] if use_net else daily["GrossProfit"]
    return daily, df_valid, {"open_col": open_col, "close_col": close_col, "profit_col": profit_col,
                             "swap_col": swap_col, "comm_col": comm_col, "symbol_col": symbol_col}

# ----------------------
# Main loop: process uploaded files
# ----------------------
if uploaded_files:
    for idx, f in enumerate(uploaded_files):
        st.markdown(f"### 📑 File: {f.name}")
        try:
            name, account, df = detect_header_and_read(f)
            st.write("👤 Nama Klien:", name or "-")
            st.write("🏦 Nomor Akun:", account or "-")

            daily, df_used, meta = process_by_open(df, use_net=use_net, symbol_list=symbol_list)

            if daily.empty:
                st.warning("Hasil per-hari kosong setelah proses. Periksa format kolom.")
                continue

            # format display
            display = daily.copy()
            for c in ("GrossProfit", "Swap", "Commission", "NetProfit", "ChosenSum"):
                display[c] = display[c].map(lambda x: f"{x:,.2f}")

            st.subheader("📊 Profit per hari (berdasarkan Open Time)")
            st.dataframe(display)

            # summary
            total_profit = float(daily["ChosenSum"].sum())
            imax = daily["ChosenSum"].idxmax()
            max_profit = float(daily.loc[imax, "ChosenSum"])
            max_date = daily.loc[imax, "OpenDate"]
            pct = (max_profit / total_profit * 100) if total_profit != 0 else 0.0
            status = "PASS" if pct < float(percent_threshold) else "FAILED"
            challenge_80 = total_profit * 0.80
            fasttrack_90 = total_profit * 0.90

            st.markdown(
                f"""
                🔥 **Profit harian terbesar:** **{max_profit:,.2f}** pada **{max_date}**  
                💰 **Total profit:** **{total_profit:,.2f}**  
                📈 **Persentase kontribusi:** **{pct:.2f} %**  
                📝 **Status:** **{status}**
                """
            )

            st.markdown(f"🎯 80% (challenge): **{challenge_80:,.2f}** &nbsp;&nbsp; 🚀 90% (fast track): **{fasttrack_90:,.2f}**")

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
                "💾 Download hasil per hari (CSV)",
                data=out.getvalue(),
                file_name=f"daily_profit_{f.name}.csv",
                mime="text/csv",
                key=f"dl_{idx}_{f.name}"
            )

        except Exception as e:
            st.error(f"Gagal memproses file {f.name}: {e}")
            import traceback as tb
            st.text(tb.format_exc())
