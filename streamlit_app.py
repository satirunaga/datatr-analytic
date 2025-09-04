import streamlit as st
import pandas as pd
import io

st.title("📊 Analisis Laporan Trading (MT4/MT5)")

uploaded_files = st.file_uploader(
    "Unggah file laporan trading (CSV/XLSX)",
    type=["csv", "xlsx"],
    accept_multiple_files=True
)

# helper ambil nama & akun
def extract_label_value(df_raw: pd.DataFrame, target: str) -> str | None:
    target = target.lower()
    for _, row in df_raw.iterrows():
        cells = [str(x).strip() for x in row if pd.notna(x)]
        for j, cell in enumerate(cells):
            low = cell.lower().replace("：", ":")
            if low.startswith(target + ":"):
                after = cell.split(":", 1)[1].strip()
                if after:
                    return after
                if j + 1 < len(cells):
                    return " ".join(cells[j+1:])
            if low == target or low == target + ":":
                if j + 1 < len(cells):
                    return " ".join(cells[j+1:])
    return None

def load_mt_report(file):
    """Baca laporan MT4/MT5: deteksi nama/akun + tabel transaksi"""
    # baca raw dulu (tanpa header) utk info nama & akun
    try:
        df_raw = pd.read_excel(file, header=None, dtype=str)
    except:
        file.seek(0)
        df_raw = pd.read_csv(file, header=None, dtype=str)

    # ambil nama & akun
    name = extract_label_value(df_raw, "name") or "-"
    account = extract_label_value(df_raw, "account") or "-"

    # cari baris header tabel (kolom transaksi)
    header_row = None
    for i, row in df_raw.iterrows():
        cells = [str(x).lower().strip() for x in row if pd.notna(x)]
        if any("profit" in c for c in cells) and any("time" in c for c in cells):
            header_row = i
            break

    if header_row is None:
        raise ValueError("❌ Tidak menemukan header tabel transaksi")

    # baca ulang mulai header_row
    file.seek(0)
    try:
        df = pd.read_excel(file, skiprows=header_row)
    except:
        file.seek(0)
        df = pd.read_csv(file, skiprows=header_row)

    return name, account, df

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.write(f"📑 File: {uploaded_file.name}")

        try:
            name, account, df = load_mt_report(uploaded_file)
            st.write(f"👤 Nama Klien: **{name}**")
            st.write(f"🏦 Nomor Akun: **{account}**")

            # normalisasi kolom
            df.columns = df.columns.str.strip().str.lower()

            # cari kolom tanggal & profit
            time_col = next((c for c in df.columns if "time" in c), None)
            profit_col = next((c for c in df.columns if "profit" in c), None)

            if not time_col or not profit_col:
                st.error(f"❌ Tidak menemukan kolom tanggal atau profit pada {uploaded_file.name}")
                continue

            # parsing tanggal
            df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
            df = df.dropna(subset=[time_col])

            df["CloseDate"] = df[time_col].dt.date
            df["Profit"] = (
                df[profit_col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .pipe(pd.to_numeric, errors="coerce")
                .fillna(0)
            )

            # hitung per hari
            df_daily = df.groupby("CloseDate")["Profit"].sum().reset_index()

            # profit harian max
            max_row = df_daily.loc[df_daily["Profit"].idxmax()]
            max_profit = max_row["Profit"]
            max_date = max_row["CloseDate"]

            # total profit
            total_profit = df_daily["Profit"].sum()
            contribution_pct = (max_profit / total_profit * 100) if total_profit != 0 else 0

            # tambahan 80% & 90%
            challenge_80 = total_profit * 0.80
            fasttrack_90 = total_profit * 0.90

            st.write("📊 **Profit per hari**")
            st.dataframe(df_daily)

            st.markdown(f"""
            🔥 Profit harian terbesar: **{max_profit:,.2f}** pada **{max_date}**  
            💰 Total profit: **{total_profit:,.2f}**  
            📈 Persentase: **{contribution_pct:.2f} %**  
            ✅ Cek {max_date} (Profit): **{max_profit:,.2f}**

            ---
            🎯 80% (challenge account): **{challenge_80:,.2f}**  
            🚀 90% (fast track): **{fasttrack_90:,.2f}**
            """)

            # download csv
            out = df_daily.copy()
            out.insert(0, "Account", account)
            out.insert(0, "ClientName", name)

            buf = io.BytesIO()
            out.to_csv(buf, index=False)
            st.download_button(
                "💾 Download hasil per hari (CSV)",
                data=buf.getvalue(),
                file_name=f"daily_profit_{uploaded_file.name}.csv",
                mime="text/csv",
                key=f"dl_{uploaded_file.name}"
            )

        except Exception as e:
            st.error(f"Gagal memproses file {uploaded_file.name}: {e}")
