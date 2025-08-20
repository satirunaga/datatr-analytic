def analyze_file(file, filename):
    # 1) Info Akun
    account_number, account_name = extract_account_info(file)

    # 2) Baca data transaksi
    file.seek(0)
    df = read_any(file).copy()
    df.columns = [str(c).strip() for c in df.columns]

    # 3) Deteksi kolom tanggal CLOSE
    close_col = pick_column(
        df,
        candidates=["Time.1", "Close Time", "Close", "CloseDate", "Close Date", "Deal time"],
        patterns=[r"\bclose[_\s]?time\b", r"\btime\.?1\b", r"\bclose\b"]
    )
    if not close_col:
        close_col = pick_column(df, candidates=["Time", "Open Time", "Datetime", "Date"])
    if not close_col:
        st.error("❌ Tidak menemukan kolom tanggal CLOSE/TIME pada file ini.")
        with st.expander("Kolom yang terbaca"):
            st.write(list(df.columns))
        return

    # 4) Deteksi kolom Profit/Commission/Swap
    profit_col = pick_column(df, candidates=["Profit", "Gross Profit", "Net Profit", "P/L", "PL", "NetProfit"],
                             patterns=[r"profit|p\/?l|net"])
    comm_col = pick_column(df, candidates=["Commission", "Comm"], patterns=[r"comm"])
    swap_col = pick_column(df, candidates=["Swap", "Storage", "Rollover"], patterns=[r"swap|roll"])

    if not profit_col:
        st.error("❌ Tidak menemukan kolom Profit/P&L pada file ini.")
        with st.expander("Kolom yang terbaca"):
            st.write(list(df.columns))
        return

    # 5) Parse tanggal & angka
    close_dt = coerce_date_series(df[close_col])
    df = df.assign(CloseDate=close_dt.dt.date)
    df = df.dropna(subset=["CloseDate"])

    profit_s = normalize_numeric_series(df[profit_col])
    comm_s = normalize_numeric_series(df[comm_col]) if comm_col else pd.Series(0.0, index=df.index)
    swap_s = normalize_numeric_series(df[swap_col]) if swap_col else pd.Series(0.0, index=df.index)

    df = df.assign(_profit=profit_s, _comm=comm_s, _swap=swap_s)
    df["NetProfit"] = df["_profit"] + df["_comm"] + df["_swap"]

    # 6) Agregasi harian
    per_day = (
        df.groupby("CloseDate")[["_profit", "_comm", "_swap", "NetProfit"]]
        .sum()
        .reset_index()
        .rename(columns={"_profit": "Profit", "_comm": "Commission", "_swap": "Swap"})
    )

    if per_day.empty:
        st.warning("Tidak ada baris valid setelah parsing tanggal/angka.")
        return

    # 7) Ringkasan
    max_row = per_day.loc[per_day["NetProfit"].idxmax()]
    max_profit = float(max_row["NetProfit"])
    max_date = max_row["CloseDate"]
    total_profit = float(per_day["NetProfit"].sum())
    percentage = (max_profit / total_profit * 100.0) if total_profit != 0 else 0.0

    # 8) Tampilkan
    st.subheader(f"📑 File: {filename}")
    st.write(f"👤 **Nama Pemilik:** {account_name}")
    st.write(f"🏦 **Nomor Akun:** {account_number}\n")

    st.write("📊 **Profit per hari (Net)**")
    st.write(f"🔥 **Profit harian terbesar (Net): {max_profit:.2f} pada {max_date}**")
    st.write(f"💰 **Total profit (Net): {total_profit:.2f}**")
    st.write(f"📈 **Persentase: {percentage:.2f} %**")
    st.write(f"✅ **Cek {max_date} (Net): {max_profit:.2f}**")

    # 👉 Tambah tampilkan tabel harian
    st.dataframe(per_day, use_container_width=True)

    # 9) Download Excel per file
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
