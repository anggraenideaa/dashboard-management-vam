# import streamlit as st
# import pandas as pd
# import plotly.express as px
# from datetime import datetime
# from db import load_sales_report

# st.set_page_config(page_title="AR Performance (Piutang)", layout="wide")

# def load_css(file_name):
#     try:
#         with open(file_name) as f:
#             st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
#     except FileNotFoundError:
#         pass

# load_css("assets/style.css")

# def format_id(val, decimal=0):
#     try:
#         if decimal == 0:
#             formatted = f"{val:,.0f}"
#         else:
#             formatted = f"{val:,.{decimal}f}"
#         formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
#         return formatted
#     except Exception:
#         return val

# st.title("💳 AR Performance (Piutang)")
# st.markdown("<div class='spacer-15'></div>", unsafe_allow_html=True)

# df_raw = load_sales_report()

# if df_raw is None or df_raw.empty:
#     st.warning("Data Piutang belum tersedia atau gagal dimuat.")
# else:
#     df = df_raw.copy()
#     df.columns = df.columns.astype(str).str.strip()

#     col_total_amnt = "Total_Amnt"
#     col_balance = "Balance"
#     col_ket_bayar = "Ket_Bayar"
#     col_tanda = "Tanda"
#     col_ket_jth_tempo = "Ket_Jth_Tempo"
#     col_jth_tempo = "Jth_Tempo"
#     col_sales = "Sales_Name"
#     col_branch = "Branch"
#     col_cust = "Cust_Name"
#     col_inv = "No_Inv"
#     col_top = "Top_Days"

#     for col in [col_total_amnt, col_balance]:
#         if col in df.columns:
#             df[col] = pd.to_numeric(
#                 df[col].astype(str).str.replace(r'[^0-9,.-]', '', regex=True)
#                 .str.replace('.', '', regex=False).str.replace(',', '.', regex=False), 
#                 errors="coerce"
#             ).fillna(0)
#         else:
#             df[col] = 0

#     if col_top in df.columns: df[col_top] = pd.to_numeric(df[col_top], errors="coerce").fillna(0)
#     if col_jth_tempo in df.columns: df[col_jth_tempo] = pd.to_datetime(df[col_jth_tempo], errors='coerce')

#     df_filtered = df.copy()
#     if col_ket_bayar in df_filtered.columns:
#         df_filtered = df_filtered[df_filtered[col_ket_bayar].astype(str).str.strip().isin(['02. Kurang Bayar', '03. Belum Bayar'])]

#     user_role = st.session_state.get("role", "sales")
#     nama_user = st.session_state.get("nama_sales", "")

#     if user_role == "sales" and col_sales in df_filtered.columns:
#         df_ar = df_filtered[df_filtered[col_sales].astype(str).str.upper() == nama_user.upper()].copy()
#     else:
#         df_ar = df_filtered.copy()

#     df_display = df_ar.copy()
    
#     with st.expander("🔍 Filter Data AR / Piutang", expanded=False):
#         f1, f2 = st.columns(2)
#         if col_branch in df_display.columns:
#             branch_options = sorted(df_display[col_branch].dropna().astype(str).unique().tolist())
#             selected_branch = f1.multiselect("Filter Branch:", branch_options, placeholder="Pilih Cabang...")
#             if selected_branch:
#                 df_display = df_display[df_display[col_branch].astype(str).isin(selected_branch)]

#     st.markdown("<div class='spacer-5'></div>", unsafe_allow_html=True)
#     st.caption(f"ℹ️ Total baris data piutang dimuat: **{format_id(len(df_display), 0)} baris**")

#     total_pembayaran_val = df[col_total_amnt].sum() if col_total_amnt in df.columns else 0
#     total_piutang_val = df_display[col_balance].sum() if col_balance in df.columns else 0

#     m1, m2 = st.columns(2)
#     m1.metric("💰 Total Pembayaran", f"Rp {format_id(total_pembayaran_val, 0)}")
#     m2.metric("📋 Total Piutang", f"Rp {format_id(total_piutang_val, 0)}")

#     st.markdown("<div class='spacer-10'></div>", unsafe_allow_html=True)

#     with st.container(border=True):
#         st.subheader("📋 Tabel Piutang / AR")
#         st.dataframe(df_display.reset_index(drop=True), use_container_width=True)