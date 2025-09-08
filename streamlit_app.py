# streamlit_app.py
import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# Optional: nicer chart
try:
    import plotly.express as px
    PLOTLY = True
except Exception:
    PLOTLY = False

# ----------------------------
# Streamlit setup
# ----------------------------
st.set_page_config(page_title="Daily Profit Report (Open Time)", layout="wide")
st.title("📊 Daily Profit Report — berdasarkan Open Time")

st.sidebar.header("Pengaturan")
use_net = st.sidebar.checkbox("Gunakan Net Profit (Profit+Swap+Commission)", value=False)
threshold_pct = st.sidebar.number_input("Threshold % untuk PASS", value=30.0, step=1.0)
symbol_filter = st.sidebar.text_input("Filter symbol (pisahkan dengan koma, kosong=semua)", value="")
symbol_list = [s
