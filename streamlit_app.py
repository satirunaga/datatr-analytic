import streamlit as st
import pandas as pd

st.title("📊 Analisis Laporan Trading (MT4/MT5)")

uploaded_files = st.file_uploader(
    "Unggah file laporan trading (CSV/XLSX)", 
    type=["csv", "xlsx"], 
    accept_multiple_files=True
)

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.write(f"📑 File: {uploaded_file.name}")

        try:
            # Baca file
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            # Normalisasi nama kolom
            df.columns = df.columns.str.strip().str.lower()

            # Pastikan ada kolom time (close) & profit
            time_col = None
            for c in df.columns:
                if "time" in c:
                    time_col = c
                    break

            profit_col = None
            for c in df.columns:
                if "profit" in c:
                    profit_col = c
                    break

            if not time_col or not profit_col:
                st.error(f"❌ Tidak menemukan kolom tanggal atau profit pada {uploaded_file.name}")
                continue

            # Parsing tanggal close
            df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
            df = df.dropna(subset=[time_col])

            # Ambil tanggal saja
            df["CloseDate"] = df[time_col].dt.date

            # Hitung per hari (hanya kolom profit)
            df_daily = df.groupby("CloseDate")[profit_col].sum().reset_index()
            df_daily.rename(columns={profit_col: "Profit"}, inplace=True)

            # Cari profit harian terbesar
            max_row = df_daily.loc[df_daily["Profit"].idxmax()]
            max_profit = max_row["Profit"]
            max_date = max_row["CloseDate"]

            # Hitung total profit
            total_profit = df_daily["Profit"].sum()

            # Hitung kontribusi (%)
            contribution_pct = (max_profit / total_profit * 100) if total_profit != 0 else 0

            # Tampilkan hasil
            st.write("📊 **Profit per hari**")
            st.dataframe(df_daily)

            st.markdown(f"""
            🔥 Profit harian terbesar: **{max_profit:,.2f}** pada **{max_date}**  
            💰 Total profit: **{total_profit:,.2f}**  
            📈 Persentase: **{contribution_pct:.2f} %**  
            ✅ Cek {max_date} (Profit): **{max_profit:,.2f}**
            """)

        except Exception as e:
            st.error(f"Gagal memproses file {uploaded_file.name}: {e}")
