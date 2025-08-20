import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Trading Report Analyzer (Flexible)", layout="wide")
st.title("📊 Trading Report Analyzer — Flexible Format")

# ---------- Util: cleaning & helpers ----------

def normalize_numeric_series(s: pd.Series) -> pd.Series:
    """Bersihkan angka (hapus currency, koma, spasi, dll) lalu konversi ke float."""
    if s is None:
        return pd.Series(dtype="float64")
    s = s.astype(str).str.replace(r"[^\d\-\.\,]", "", regex=True)
    # ubah koma sebagai pemisah ribuan ke kosong (jika ada titik juga, diasumsikan titik desimal)
    s = s.str.replace(",", "", regex=False)
    return pd.to_numeric(s, errors="coerce").fillna(0.0)

def pick_column(df: pd.DataFrame, candidates=None, patterns=None):
    """Cari kolom dengan nama paling mirip dari daftar candidates/patterns (case-insensitive)."""
    cols = list(df.columns)
    cols_l = [str(c).strip().lower() for c in cols]
    # exact-ish by candidates
    if candidates:
        cand_l = [c.lower() for c in candidates]
        for i, c in enumerate(cols_l):
            if c in cand_l:
                return cols[i]
        # startswith/contains
        for i, c in enumerate(cols_l):
            for cand in cand_l:
                if c.startswith(cand) or cand in c:
                    return cols[i]
    # regex patterns
    if patterns:
        for i, c in enumerate(cols_l):
            for pat in patterns:
                if re.search(pat, c, flags=re.I):
                    return cols[i]
    return None

def find_header_row(raw_df: pd.DataFrame, probe_labels):
    """Deteksi baris header dengan mencari baris yang mengandung sebagian besar label kandidat."""
    best_row, best_score = None, -1
    for r in range(min(len(raw_df), 40)):  # scan maksimal 40 baris pertama
        row_vals = [str(x).strip().lower() for x in list(raw_df.iloc[r].values)]
        score = 0
        for lbl in probe_labels:
            # anggap match jika ada sel yang mengandung label tsb
            if any(lbl in v for v in row_vals):
                score += 1
        if score > best_score:
            best_score = score
            best_row = r
    return best_row if best_score > 0 else None

def read_any(file):
    """Baca CSV/XLSX se-fleksibel mungkin: coba normal, lalu coba deteksi header manual."""
    name = getattr(file, "name", "uploaded_file")
    is_csv = name.lower().endswith(".csv")
    if is_csv:
        # 1) coba baca biasa
        try:
            df = pd.read_csv(file)
            return df
        except Exception:
            file.seek(0)
        # 2) header=None + deteksi header
        raw = pd.read_csv(file, header=None)
        probe = ["time", "profit", "commission", "swap", "time.1", "close", "close time", "p/l", "net"]
        hdr = find_header_row(raw, probe)
        if hdr is not None:
            file.seek(0)
            df = pd.read_csv(file, header=hdr)
            return df
        return raw  # fallback
    else:
        # XLSX
        try:
            df = pd.read_excel(file, sheet_name="Sheet1", header=7)
            return df
        except Exception:
            file.seek(0)
        # baca tanpa header lalu deteksi
        raw = pd.read_excel(file, sheet_name="Sheet1", header=None)
        probe = ["time", "profit", "commission", "swap", "time.1", "close", "close time", "p/l", "net"]
        hdr = find_header_row(raw, probe)
        if hdr is not None:
            file.seek(0)
            df = pd.read_excel(file, sheet_name="Sheet1", header=hdr)
            return df
        return raw  # fallback

def extract_account_info(file):
    """Ambil Name: dan Account: dari baris awal XLSX/CSV (jika ada)."""
    try:
        # Coba baca 25 baris pertama dalam bentuk tabel (tanpa header) untuk discan
        name = getattr(file, "name", "uploaded_file")
        file.seek(0)
        if name.lower().endswith(".csv"):
            header_df = pd.read_csv(file, header=None, nrows=25, dtype=str)
        else:
            header_df = pd.read_excel(file, sheet_name="Sheet1", header=None, nrows=25, dtype=str)
        texts = header_df.apply(lambda r: " ".join([x for x in r.dropna().astype(str)]), axis=1).tolist()
        account_number, account_name = "Tidak ditemukan", "Tidak ditemukan"
        for row in texts:
            rs = row.strip()
            if rs.lower().startswith("name:"):
                account_name = rs.split(":", 1)[1].strip()
            if rs.lower().startswith("account:"):
                account_number = rs.split(":", 1)[1].strip()
        return account_number, account_name
    except Exception:
        return "Tidak ditemukan", "Tidak ditemukan"

def coerce_date_series(s: pd.Series):
    """Parse tanggal secara fleksibel: coba biasa, kalau banyak NaT coba dayfirst."""
    dt = pd.to_datetime(s, errors="coerce")
    if dt.notna().mean() < 0.5:
        dt = pd.to_datetime(s, errors="coerce", dayfirst=True)
    return dt

# ---------- Analisis per file ----------

def analyze_file(file, filename):
    # Info akun
    account_number, account_name = extract_account_info(file)

    st.subheader(f"📑 File: {filename}")
    st.write(f"👤 **Nama Pemilik:** {account_name}")
    st.write(f"🏦 **Nomor Akun:** {account_number}")

    # Baca data trading (fleksibel)
    file.seek(0)
    df = read_any(file)

    # Standardisasi nama kolom (strip, lower utk pencarian)
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # Deteksi kolom CLOSE TIME terlebih dahulu
    close_col = pick_column(
        df,
        candidates=[
            "Time.1", "Close Time", "CloseTime", "Close", "Close Date", "CloseDate",
            "Time Close", "Deal time", "Close time"
        ],
        patterns=[r"\bclose\b", r"\btime\.?1\b", r"\bclose[_\s]?time\b"]
    )
    # Kalau tidak ada, fallback ke 'Time'
    if not close_col:
        close_col = pick_column(df, candidates=["Time", "Open Time", "Datetime", "Date"])

    # Deteksi kolom profit/komisi/swap (fleksibel)
    profit_col = pick_column(
        df,
        candidates=["Net Profit", "Profit", "P/L", "PL", "NetProfit", "Gross Profit"],
        patterns=[r"profit|p\/?l|net"]
    )
    comm_col = pick_column(df, candidates=["Commission", "Comm"], patterns=[r"comm"])
    swap_col = pick_column(df, candidates=["Swap", "Storage", "Rollover"], patterns=[r"swap|roll"])

    # Validasi minimal: harus ada tanggal close & ada salah satu nilai profit
    if not close_col or not profit_col:
        st.error("❌ Tidak menemukan kolom tanggal CLOSE atau PROFIT di file ini.")
        with st.expander("Lihat kolom yang terdeteksi"):
            st.write(list(df.columns))
        return

    # Parse tanggal
    close_dt = coerce_date_series(df[close_col])
    df["CloseDate"] = close_dt.dt.date

    # Normalisasi angka
    df["_profit"] = normalize_numeric_series(df[profit_col])
    df["_comm"] = normalize_numeric_series(df[comm_col]) if comm_col else 0.0
    df["_swap"] = normalize_numeric_series(df[swap_col]) if swap_col else 0.0

    # Hitung per hari (Net = Profit + Commission + Swap ; kolom yang tak ada dianggap 0)
    per_day = (
        df.groupby("CloseDate")[["_profit", "_comm", "_swap"]]
        .sum()
        .reset_index()
        .rename(columns={"_profit": "Profit", "_comm": "Commission", "_swap": "Swap"})
    )
    per_day["NetProfit"] = per_day["Profit"] + per_day["Commission"] + per_day["Swap"]

    # Tampilkan tabel
    st.write("### 📊 Profit per hari (Net)")
    st.dataframe(per_day)

    # Ringkasan
    if len(per_day) == 0:
        st.warning("Tidak ada baris valid untuk dihitung (tanggal atau angka tidak terbaca).")
        return
    max_row = per_day.loc[per_day["NetProfit"].idxmax()]
    max_profit, max_date = float(max_row["NetProfit"]), max_row["CloseDate"]
    total_profit = float(per_day["NetProfit"].sum())
    percentage = (max_profit / total_profit * 100.0) if total_profit != 0 else 0.0

    st.success(
        f"🔥 Profit harian terbesar (Net): {max_profit:.2f} pada {max_date}\n\n"
        f"💰 Total profit (Net): {total_profit:.2f}\n\n"
        f"📈 Persentase kontribusi: {percentage:.2f} %"
    )

    # Download Excel per file
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        per_day.to_excel(writer, index=False, sheet_name="ProfitPerDay")
        summary_df = pd.DataFrame(
            {
                "Nama Pemilik": [account_name],
                "Nomor Akun": [account_number],
                "Total Profit (Net)": [total_profit],
                "Max Profit (Net)": [max_profit],
                "Tanggal Max": [max_date],
                "Persentase (%)": [percentage],
            }
        )
        summary_df.to_excel(writer, index=False, sheet_name="Summary")
    st.download_button(
        label="⬇️ Download Hasil Analisa",
        data=output.getvalue(),
        file_name=f"Hasil_Analisa_{account_number or filename}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"dl_{filename}",  # unik per file
    )

# ---------- UI: upload multi-file ----------

uploaded_files = st.file_uploader(
    "Upload laporan trading (.xlsx / .csv)", type=["xlsx", "csv"], accept_multiple_files=True
)

if uploaded_files:
    for f in uploaded_files:
        analyze_file(f, f.name)
else:
    st.info("Unggah satu atau beberapa file laporan trading (.xlsx / .csv) untuk mulai analisa.")
