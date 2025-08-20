import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Trading Report Analyzer — Flexible", layout="wide")
st.title("📊 Trading Report Analyzer — Flexible")

# ========== Utils ==========

def normalize_numeric_series(s: pd.Series) -> pd.Series:
    if s is None:
        return pd.Series(dtype="float64")
    s = s.astype(str).str.replace(r"[^\d\-\.\,]", "", regex=True)  # buang symbol, spasi, $
    s = s.str.replace(",", "", regex=False)  # buang pemisah ribuan
    return pd.to_numeric(s, errors="coerce").fillna(0.0)

def pick_column(df: pd.DataFrame, candidates=None, patterns=None):
    cols = list(df.columns)
    cols_l = [str(c).strip().lower() for c in cols]
    # exact/contains
    if candidates:
        cand_l = [c.lower() for c in candidates]
        for i, c in enumerate(cols_l):
            if c in cand_l:
                return cols[i]
        for i, c in enumerate(cols_l):
            for cand in cand_l:
                if c.startswith(cand) or cand in c:
                    return cols[i]
    # regex
    if patterns:
        for i, c in enumerate(cols_l):
            for pat in patterns:
                if re.search(pat, c, flags=re.I):
                    return cols[i]
    return None

def find_header_row(raw_df: pd.DataFrame, probe_labels):
    best_row, best_score = None, -1
    scan_rows = min(len(raw_df), 60)
    for r in range(scan_rows):
        row_vals = [str(x).strip().lower() for x in raw_df.iloc[r].values]
        score = 0
        for lbl in probe_labels:
            if any(lbl in v for v in row_vals):
                score += 1
        if score > best_score:
            best_score, best_row = score, r
    return best_row if best_score > 0 else None

def read_any(file):
    """Baca CSV/XLSX se-fleksibel mungkin + deteksi header."""
    name = getattr(file, "name", "uploaded_file")
    is_csv = name.lower().endswith(".csv")

    probe = ["time.1", "close", "close time", "profit", "p/l", "commission", "swap"]

    if is_csv:
        # 1) coba normal
        try:
            file.seek(0)
            return pd.read_csv(file)
        except Exception:
            pass
        # 2) header=None lalu deteksi header
        file.seek(0)
        raw = pd.read_csv(file, header=None, dtype=str)
        hdr = find_header_row(raw, probe)
        if hdr is not None:
            file.seek(0)
            return pd.read_csv(file, header=hdr)
        return raw
    else:
        # XLSX: coba header=7 (umum MT4/MT5 export)
        try:
            file.seek(0)
            return pd.read_excel(file, sheet_name="Sheet1", header=7)
        except Exception:
            pass
        # coba header=0
        try:
            file.seek(0)
            return pd.read_excel(file, sheet_name="Sheet1", header=0)
        except Exception:
            pass
        # deteksi header manual
        file.seek(0)
        raw = pd.read_excel(file, sheet_name="Sheet1", header=None, dtype=str)
        hdr = find_header_row(raw, probe)
        if hdr is not None:
            file.seek(0)
            return pd.read_excel(file, sheet_name="Sheet1", header=hdr)
        return raw

def extract_account_info(file):
    """Cari Name: dan Account: di 30 baris awal."""
    try:
        name = getattr(file, "name", "uploaded_file")
        file.seek(0)
        if name.lower().endswith(".csv"):
            head = pd.read_csv(file, header=None, nrows=30, dtype=str)
        else:
            head = pd.read_excel(file, sheet_name="Sheet1", header=None, nrows=30, dtype=str)
        lines = head.apply(lambda r: " ".join([x for x in r.dropna().astype(str)]), axis=1).tolist()
        account_name, account_number = None, None
        for row in lines:
            row_str = row.strip()
            if row_str.lower().startswith("name:"):
                account_name = row_str.split(":", 1)[1].strip()
            if row_str.lower().startswith("account:"):
                account_number = row_str.split(":", 1)[1].strip()
        return account_number or "Tidak ditemukan", account_name or "Tidak ditemukan"
    except Exception:
        return "Tidak ditemukan", "Tidak ditemukan"

def coerce_date_series(s: pd.Series):
    dt = pd.to_datetime(s, errors="coerce")
    if dt.notna().mean() < 0.5:
        dt = pd.to_datetime(s, errors="coerce", dayfirst=True)
    return dt

# ========== Analisis per file ==========

def analyze_file(file, filename):
    # 1) Info Akun
    account_number, account_name = extract_account_info(file)

    # 2) Baca data transaksi
    file.seek(0)
    df = read_any(file).copy()
    # rapikan kolom
    df.columns = [str(c).strip() for c in df.columns]

    # 3) Deteksi kolom tanggal CLOSE (prioritas Time.1 / Close Time)
    close_col = pick_column(
        df,
        candidates=["Time.1", "Close Time", "Close", "CloseDate", "Close Date", "Deal time"],
        patterns=[r"\bclose[_\s]?time\b", r"\btime\.?1\b", r"\bclose\b"]
    )
    if not close_col:
        # fallback ke 'Time' bila tidak ada
        close_col = pick_column(df, candidates=["Time", "Open Time", "Datetime", "Date"])
    if not close_col:
        st.error("❌ Tidak menemukan kolom tanggal CLOSE/TIME pada file ini.")
        with st.expander("Kolom yang terbaca"):
            st.write(list(df.columns))
        return

    # 4) Deteksi kolom Profit/Commission/Swap (toleran nama)
    profit_col = pick_column(
        df,
        candidates=["Profit", "Gross Profit", "Net Profit", "P/L", "PL", "NetProfit"],
        patterns=[r"profit|p\/?l|net"]
    )
    comm_col = pick_column(df, candidates=["Commission", "Comm"], patterns=[r"comm"])
    swap_col = pick_column(df, candidates=["Swap", "Storage", "Rollover"], patterns=[r"swap|roll"])

    if not profit_col:
        st.error("❌ Tidak menemukan kolom Profit/P&L pada file ini.")
        with st.expander("Kolom yang terbaca"):
            st.write(list(df.columns))
        return

    # 5) Parse tanggal & normalisasi angka
    close_dt = coerce_date_series(df[close_col])
    df = df.assign(CloseDate=close_dt.dt.date)
    df = df.dropna(subset=["CloseDate"])

    profit_s = normalize_numeric_series(df[profit_col])
    comm_s = normalize_numeric_series(df[comm_col]) if comm_col else pd.Series(0.0, index=df.index)
    swap_s = normalize_numeric_series(df[swap_col]) if swap_col else pd.Series(0.0, index=df.index)

    # Selalu hitung NetProfit = Profit + Commission + Swap
    df = df.assign(_profit=profit_s, _comm=comm_s, _swap=swap_s)
    df["NetProfit"] = df["_profit"] + df["_comm"] + df["_swap"]

    # 6) Agregasi per hari (berdasarkan tanggal CLOSE)
    per_day = (
        df.groupby("CloseDate")[["_profit", "_comm", "_swap", "NetProfit"]]
        .sum()
        .reset_index()
        .rename(columns={"_profit": "Profit", "_comm": "Commission", "_swap": "Swap"})
    )

    if per_day.empty:
        st.warning("Tidak ada baris valid setelah parsing tanggal/angka.")
        return

    # 7) Ringkasan yang Anda minta
    max_row = per_day.loc[per_day["NetProfit"].idxmax()]
    max_profit = float(max_row["NetProfit"])
    max_date = max_row["CloseDate"]
    total_profit = float(per_day["NetProfit"].sum())
    percentage = (max_profit / total_profit * 100.0) if total_profit != 0 else 0.0

    # 8) Tampilkan ringkasan + identitas akun
    st.subheader(f"📑 File: {filename}")
    st.write(f"👤 **Nama Pemilik:** {account_name}")
    st.write(f"🏦 **Nomor Akun:** {account_number}\n")

    st.write("📊 **Profit per hari (Net)**")
    st.write(f"🔥 **Profit harian terbesar (Net): {max_profit:.2f} pada {max_date}**")
    st.write(f"💰 **Total profit (Net): {total_profit:.2f}**")
    st.write(f"📈 **Persentase: {percentage:.2f} %**")
    st.write(f"✅ **Cek {max_date} (Net): {max_profit:.2f}**")

    # 9) Download Excel per file (unique key)
    out = BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        per_day.to_excel(writer, index=False, sheet_name="ProfitPerDay")
        pd.DataFrame({
            "Nama Pemilik": [account_name],
            "Nomor Akun": [account_number],
            "Total Profit (Net)": [total_profit],
            "Max Profit (Net)": [max_profit],
            "Tanggal Max": [max_date],
            "Persentase (%)": [percentage],
        }).to_excel(writer, index=False, sheet_name="Summary")

    st.download_button(
        label="⬇️ Download Hasil (Excel)",
        data=out.getvalue(),
        file_name=f"Hasil_Analisa_{account_number or filename}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"dl_{filename}",
    )

# ========== UI ==========

uploaded_files = st.file_uploader(
    "Upload laporan trading (.xlsx / .csv)", type=["xlsx", "csv"], accept_multiple_files=True
)

if uploaded_files:
    for f in uploaded_files:
        analyze_file(f, f.name)
else:
    st.info("Unggah satu atau beberapa file laporan trading untuk mulai analisa.")
