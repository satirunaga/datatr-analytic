import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io

st.set_page_config(page_title="Trading Report Analyzer", layout="wide")

st.title("📊 Trading Report Analyzer")

# Upload multiple files
uploaded_files = st.file_uploader("📂 Upload laporan trading (Excel/CSV)", 
                                  type=["xlsx", "csv"], 
                                  accept_multiple_files=True)

def process_file(file):
    # Baca file
    if file.name.endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file, header=7)

    # Normalisasi nama kolom
    df.columns = [str(c).strip() for c in df.columns]

    # Pastikan kolom penting ada
    required_cols = ["Time.1", "Profit", "Commission", "Swap"]
    if not all(col in df.columns for col in required_cols):
        return None, f"❌ Kolom wajib tidak ditemukan di {file.name}"

    # Konversi tanggal close
    df["CloseDate"] = pd.to_datetime(df["Time.1"], errors="coerce").dt.date

    # Pastikan numerik
    for col in ["Profit", "Commission", "Swap"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Hitung Net Profit per hari
    per_day = df.groupby("CloseDate").agg({
        "Profit": "sum",
        "Swap": "sum",
        "Commission": "sum"
    }).reset_index()

    per_day["NetProfit"] = per_day["Profit"] + per_day["Swap"] + per_day["Commission"]

    # Ringkasan
    total_profit = per_day["NetProfit"].sum()
    max_row = per_day.loc[per_day["NetProfit"].idxmax()]

    return per_day, {
        "file": file.name,
        "total_profit": total_profit,
        "max_profit": max_row["NetProfit"],
        "max_date": max_row["CloseDate"]
    }

if uploaded_files:
    for file in uploaded_files:
        st.divider()
        st.subheader(f"📑 Hasil Analisa: {file.name}")

        per_day, summary = process_file(file)

        if per_day is None:
            st.error(summary)  # error message
        else:
            # Tampilkan tabel
            st.write("### 📊 Profit per Hari")
            st.dataframe(per_day)

            # Grafik bar chart
            fig, ax = plt.subplots(figsize=(8,4))
            ax.bar(per_day["CloseDate"].astype(str), per_day["NetProfit"], color=["red" if x<0 else "green" for x in per_day["NetProfit"]])
            ax.set_title("Net Profit per Hari")
            ax.set_ylabel("Profit")
            plt.xticks(rotation=45)
            st.pyplot(fig)

            # Ringkasan
            st.success(f"""
            🔥 Profit harian terbesar (Net): {summary['max_profit']:.2f} pada {summary['max_date']}
            💰 Total profit (Net): {summary['total_profit']:.2f}
            """)

            # Export tombol download (Excel & CSV)
            st.write("### 📥 Export Data")
            # CSV
            csv = per_day.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download CSV", csv, file_name=f"{summary['file']}_perday.csv", mime="text/csv")

            # Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                per_day.to_excel(writer, index=False, sheet_name="PerDay")
            st.download_button("⬇️ Download Excel", buffer.getvalue(), file_name=f"{summary['file']}_perday.xlsx", mime="application/vnd.ms-excel")
