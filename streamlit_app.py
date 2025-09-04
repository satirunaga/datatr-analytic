import streamlit as st
import pandas as pd
import io

st.title("📊 Analisis Laporan Trading MetaTrader")

uploaded_files = st.file_uploader(
    "Upload file laporan trading (CSV/XLSX)",
    type=["csv", "xlsx"],
    accept_multiple_files=True
)

# ---------- Helpers ----------

def _extract_label_value(df_raw: pd.DataFrame, target_label: str) -> str | None:
    """
    Cari nilai untuk label seperti 'Name' atau 'Account' di seluruh kolom.
    Logika:
    - Jika sel berisi 'Name: John Doe' => ambil 'John Doe'
    - Jika sel berisi 'Name:' di kolom j => gabungkan semua sel non-NaN di kanan (j+1 .. akhir)
    - Abaikan tanda baca/variasi '：' (colon full width)
    """
    tgt = target_label.strip().lower()
    for _, row in df_raw.iterrows():
        cells = list(row.values)
        for j, cell in enumerate(cells):
            if pd.isna(cell):
                continue
            raw = str(cell).strip()
            low = raw.lower().replace("：", ":")
            # kasus "Name: John Doe" dalam satu sel
            if low.startswith(tgt + ":"):
                after = raw.split(":", 1)[1].strip()
                if after:
                    return after
                # kalau setelah ":" kosong, coba ambil kanan
                right = [str(x).strip() for x in cells[j+1:] if pd.notna(x) and str(x).strip() != ""]
                if right:
                    return " ".join(right)
            # kasus sel = "Name" atau "Name:"
            if low == tgt or low == tgt + ":":
                right = [str(x).strip() for x in cells[j+1:] if pd.notna(x) and str(x).strip() != ""]
                if right:
                    return " ".join(right)
    return None


def load_mt_report(file):
    """
    Baca file laporan, ambil Name & Account (fleksibel banyak kolom),
    dan temukan header tabel transaksi untuk dibaca ulang sebagai DataFrame 'df'.
    """
    # Baca beberapa puluh baris awal & semua kolom supaya label ketemu
    try:
        df_raw = pd.read_excel(file, header=None, dtype=str, nrows=80)
    except Exception:
        file.seek(0)
        df_raw = pd.read_csv(file, header=None, dtype=str, nrows=80)

    # Ekstrak Name & Account dari semua kolom
    name = _extract_label_value(df_raw, "name") or "-"
    account = _extract_label_value(df_raw, "account") or "-"

    # Cari baris header tabel transaksi (mengandung 'time' / 'open time' dll)
    header_row = None
    for i, row in df_raw.iterrows():
        vals = [str(x).strip().lower() for x in row.values if pd.notna(x)]
        if any(v in ("time", "open time", "close time", "time.1") for v in vals):
            header_row = i
            break
    if header_row is None:
        raise ValueError("❌ Tidak menemukan header tabel transaksi.")

    # Baca ulang tabel dari header_row
    file.seek(0)
    try:
        df = pd.read_excel(file, skiprows=header_row)
    except Exception:
        file.seek(0)
        df = pd.read_csv(file, skiprows=header_row)

    return name, account, df


def process_trades(df: pd.DataFrame) -> pd.DataFrame:
    """
    Hitung profit per hari berdasarkan kolom close time.
    NetProfit = Profit saja (tanpa swap & commission), sesuai permintaan.
    """
    # normalisasi nama kolom
    rename_map = {c.lower(): c for c in df.columns}

    close_col = None
    for key in ["time.1", "close time", "close"]:
        if key in rename_map:
            close_col = rename_map[key]
            break
    if close_col is None:
        raise ValueError("❌ Kolom close time (mis. 'Time.1' / 'Close Time') tidak ditemukan.")

    profit_col = None
    for key in ["profit", "net profit"]:
        if key in rename_map:
            profit_col = rename_map[key]
            break
    if profit_col is None:
        raise ValueError("❌ Kolom Profit tidak ditemukan.")

    # konversi tanggal & angka
    df[close_col] = pd.to_datetime(df[close_col], errors="coerce")
    df = df[pd.notna(df[close_col])].copy()
    df["CloseDate"] = df[close_col].dt.date

    # bersihkan angka (hilangkan koma ribuan)
    df["Profit"] = (
        df[profit_col]
        .astype(str)
        .str.replace(",", "", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0.0)
    )

    # Net = Profit saja (tanpa swap & commission)
    df["NetProfit"] = df["Profit"]

    daily = (
        df.groupby("CloseDate", as_index=False)["NetProfit"]
        .sum()
        .sort_values("CloseDate")
        .reset_index(drop=True)
    )
    return daily


# ---------- UI per file ----------

if uploaded_files:
    for file in uploaded_files:
        st.write(f"📑 File: **{file.name}**")
        try:
            name, account, df = load_mt_report(file)
            st.write(f"👤 Nama Klien: **{name}**")
            st.write(f"🏦 Nomor Akun: **{account}**")

            daily = process_trades(df)

            # Ringkasan
            total_profit = float(daily["NetProfit"].sum())
            if len(daily) == 0:
                st.warning("Tidak ada transaksi yang valid pada file ini.")
                continue
            max_idx = int(daily["NetProfit"].idxmax())
            max_profit = float(daily.loc[max_idx, "NetProfit"])
            max_date = daily.loc[max_idx, "CloseDate"]
            percent = (max_profit / total_profit * 100) if abs(total_profit) > 1e-12 else 0.0

            # 80% & 90%
            challenge_80 = total_profit * 0.80
            fasttrack_90 = total_profit * 0.90

            st.subheader("📊 Profit per hari (Net)")
            st.dataframe(daily, use_container_width=True)

            st.markdown(
                f"""
**🔥 Profit harian terbesar (Net):** **{max_profit:.2f}** pada **{max_date}**  
**💰 Total profit (Net):** **{total_profit:.2f}**  
**📈 Persentase:** **{percent:.2f} %**  
**✅ Cek {max_date} (Net):** **{max_profit:.2f}**

---
**🎯 80% (challenge account):** **{challenge_80:.2f}**  
**🚀 90% (fast track):** **{fasttrack_90:.2f}**
"""
            )

            # Download CSV (tambahkan nama & akun)
            out = daily.copy()
            out.insert(0, "Account", account)
            out.insert(0, "ClientName", name)

            buf = io.BytesIO()
            out.to_csv(buf, index=False)
            st.download_button(
                "💾 Download hasil per hari (CSV)",
                data=buf.getvalue(),
                file_name=f"daily_profit_{file.name}.csv",
                mime="text/csv",
                key=f"dl_{file.name}"
            )

        except Exception as e:
            st.error(f"Gagal memproses file {file.name}: {e}")
else:
    st.info("Silakan upload 1 atau beberapa file laporan.")
