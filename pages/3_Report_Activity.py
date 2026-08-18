import streamlit as st
import pandas as pd
import plotly.express as px
from db import load_report_activity, check_role_access

st.set_page_config(page_title="Report Activity", layout="wide")

# --- FUNGSI CSS ---
def load_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"File CSS '{file_name}' tidak ditemukan.")

load_css("assets/style.css")

# Fungsi untuk memformat angka ke standar Indonesia (titik=ribuan, koma=desimal)
def format_id(val, decimal=2):
    try:
        if decimal == 0:
            formatted = f"{val:,.0f}"
        else:
            formatted = f"{val:,.{decimal}f}"
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        return formatted
    except Exception:
        return val

st.title("📝 Report Activity Dashboard")
st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

# Load Data
df_raw = load_report_activity()

if df_raw is None or df_raw.empty:
    st.warning("Data Activity belum tersedia atau gagal dimuat.")
else:
    # --- PROSES PEMBERSIHAN DATA ---
    df = df_raw.copy()
    df.columns = df.columns.astype(str).str.strip()

    col_sales = "Sales_Name"
    col_prospek = "Nama_Prospek_Customer"
    col_berat = "Potensi_Pengambilan_Kg"
    col_omzet = "Perkiraan_Omzet"
    col_status = "Status"
    col_visit = "Visit_Terakhir"

    # Pembersihan Sales Name (Penting untuk filter)
    if col_sales in df.columns:
        df[col_sales] = df[col_sales].fillna("UNCATEGORIZED").astype(str).str.strip().str.upper()

    # Pembersihan Omzet & Berat
    if col_omzet in df.columns:
        df[col_omzet] = pd.to_numeric(df[col_omzet].astype(str).str.replace(r'[^0-9,.]', '', regex=True).str.replace('.', '', regex=False).str.replace(',', '.', regex=False), errors="coerce").fillna(0)
    else:
        df[col_omzet] = 0

    if col_berat in df.columns:
        df[col_berat] = pd.to_numeric(df[col_berat].astype(str).str.replace(r'[^0-9.]', '', regex=True), errors="coerce").fillna(0)
    else:
        df[col_berat] = 0

    df[col_visit] = pd.to_datetime(df[col_visit], errors="coerce")
    df[col_status] = df[col_status].fillna("Unknown").astype(str).str.strip()

    # Diterapkan agar jika role-nya sales, data otomatis terfilter hanya milik sales tersebut yang login
    df = check_role_access(df, sales_column_name=col_sales, filter_by_sales=True)

    # ==========================================
    # FILTER UTAMA
    # ==========================================
    with st.expander("🔍 Filter Data & Pencarian", expanded=False):
        f_col1, f_col2 = st.columns(2)
        
        # FILTER SALES (Dibersihkan agar sinkron)
        if col_sales in df.columns:
            all_sales = sorted([s for s in df[col_sales].unique() if s != "UNCATEGORIZED"])
            with f_col1:
                selected_sales = st.multiselect("Filter Sales Name:", options=all_sales, default=[], placeholder="Pilih Sales...")
            if selected_sales:
                df = df[df[col_sales].isin([str(s).upper().strip() for s in selected_sales])]

        # FILTER STATUS
        if col_status in df.columns:
            all_status = sorted(df[col_status].dropna().unique().tolist())
            with f_col2:
                selected_status = st.multiselect("Filter Status:", options=all_status, default=[], placeholder="Pilih Status...")
            if selected_status:
                df = df[df[col_status].isin(selected_status)]

        # SEARCH PROSPEK
        search_query = st.text_input("🔎 Cari Prospek / Customer:", placeholder="Ketik nama customer...")
        if search_query:
            if col_prospek in df.columns:
                df = df[df[col_prospek].astype(str).str.contains(search_query, case=False, na=False)]

    st.caption(f"ℹ️ Total data dimuat: **{format_id(len(df), 0)} baris**")
    
    # --- METRIK ---
    total_deal_cust = df[df[col_status].astype(str).str.contains('trial order|5', case=False, na=False)].shape[0]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Total Omzet", f"Rp {format_id(df[col_omzet].sum(), 2)}")
    col2.metric("⚖️ Total Berat", f"{format_id(df[col_berat].sum(), 2)} Kg")
    col3.metric("👥 Total Prospek", f"{format_id(df[col_prospek].nunique(), 0)}")
    col4.metric("🎯 Deal (Trial Order)", f"{format_id(total_deal_cust, 0)} Cust")

    # --- TABEL ---
    with st.container(border=True):
        st.subheader("📋 Detail Prospek Customer")
        df_sorted = df.sort_values(by=col_omzet, ascending=False).reset_index(drop=True)
        st.dataframe(df_sorted, use_container_width=True)

    # --- GRAFIK PERKIRAAN OMZET PER BULAN (MENGGUNAKAN PLOTLY AGAR FORMAT ANGKA KONSISTEN) ---
    with st.container(border=True):
        st.subheader("📈 Perkiraan Omzet per Bulan")
        
        df_chart_data = df.copy()
        if col_visit in df_chart_data.columns:
            df_chart_data['Bulan_Tahun'] = df_chart_data[col_visit].dt.strftime('%B %Y').fillna("No Date")
        else:
            df_chart_data['Bulan_Tahun'] = "No Date"
            
        df_chart = df_chart_data.groupby('Bulan_Tahun', as_index=False)[col_omzet].sum()
        df_chart = df_chart.sort_values(by='Bulan_Tahun')
        
        if not df_chart.empty:
            fig1 = px.bar(
                df_chart, 
                x='Bulan_Tahun', 
                y=col_omzet, 
                template="plotly_white",
                labels={'Bulan_Tahun': 'Bulan / Periode', col_omzet: 'Perkiraan Omzet (Rp)'}
            )
            # Format pemisah ribuan titik (.) dan desimal koma (,) ala Indonesia
            fig1.update_layout(
                separators=',.',
                yaxis=dict(tickformat=',.0f'),
                margin=dict(l=20, r=20, t=30, b=20)
            )
            fig1.update_traces(
                hovertemplate="<b>%{x}</b><br>Omzet: Rp %{y:,.0f}<extra></extra>"
            )
            st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Data grafik belum tersedia.")

    # --- GRAFIK OMZET PER STATUS & SALES ---
    with st.container(border=True):
        st.subheader("📊 Omzet per Status & Sales")
        df_status = df.groupby([col_sales, col_status])[col_omzet].sum().reset_index()
        
        fig2 = px.bar(
            df_status, 
            x=col_sales, 
            y=col_omzet, 
            color=col_status, 
            barmode="group", 
            template="plotly_white",
            labels={col_omzet: "Perkiraan Omzet (Rp)", col_sales: "Sales Name", col_status: "Status"}
        )
        
        # Format pemisah ribuan titik (.) dan desimal koma (,) ala Indonesia
        fig2.update_layout(
            separators=',.',
            yaxis=dict(tickformat=',.0f'),
            margin=dict(l=20, r=20, t=30, b=20)
        )
        fig2.update_traces(
            hovertemplate="<b>%{x}</b><br>Omzet: Rp %{y:,.0f}<extra></extra>"
        )
        
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})