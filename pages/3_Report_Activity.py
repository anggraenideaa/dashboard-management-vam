import streamlit as st
import pandas as pd
import plotly.express as px
from db import load_report_activity, check_role_access

st.set_page_config(page_title="Report Activity", layout="wide")

# --- FUNGSI CSS (Memuat dari file terpusat assets/style.css) ---
def load_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"File CSS '{file_name}' tidak ditemukan.")

load_css("assets/style.css")

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
    df = df_raw.copy()
    df.columns = df.columns.astype(str).str.strip()

    col_sales = "Sales_Name"
    col_prospek = "Nama_Prospek_Customer"
    col_berat = "Potensi_Pengambilan_Kg"
    col_omzet = "Perkiraan_Omzet"
    col_status = "Status"
    col_visit = "Visit_Terakhir"

    prod_col_opts = [c for c in df.columns if any(k in c.lower() for k in ['produk', 'item', 'barang', 'offering'])]
    col_produk = prod_col_opts[0] if prod_col_opts else None

    if col_sales in df.columns:
        df[col_sales] = df[col_sales].fillna("UNCATEGORIZED").astype(str).str.strip().str.upper()

    uang_columns = [col for col in df.columns if any(keyword in col.lower() for keyword in ['omzet', 'harga', 'jual', 'price', 'rp'])]
    
    for c in uang_columns:
        cleaned_series = df[c].astype(str).str.replace("Rp", "", case=False, regex=True).str.strip()
        cleaned_series = cleaned_series.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        df[c] = pd.to_numeric(cleaned_series, errors="coerce").fillna(0)

    if col_omzet not in df.columns:
        df[col_omzet] = 0

    if col_berat in df.columns:
        df[col_berat] = pd.to_numeric(df[col_berat].astype(str).str.replace(r'[^0-9.]', '', regex=True), errors="coerce").fillna(0)
    else:
        df[col_berat] = 0

    df[col_visit] = pd.to_datetime(df[col_visit], errors="coerce")
    df[col_status] = df[col_status].fillna("Unknown").astype(str).str.strip()

    df = check_role_access(df, sales_column_name=col_sales, filter_by_sales=True)

    # ==========================================
    # FILTER UTAMA
    # ==========================================
    with st.expander("🔍 Filter Data & Pencarian", expanded=False):
        f_col1, f_col2 = st.columns(2)
        
        if col_sales in df.columns:
            all_sales = sorted([s for s in df[col_sales].unique() if s != "UNCATEGORIZED"])
            with f_col1:
                selected_sales = st.multiselect("Filter Sales Name:", options=all_sales, default=[], placeholder="Pilih Sales...")
            if selected_sales:
                df = df[df[col_sales].isin([str(s).upper().strip() for s in selected_sales])]

        if col_status in df.columns:
            all_status = sorted(df[col_status].dropna().unique().tolist())
            with f_col2:
                selected_status = st.multiselect("Filter Status:", options=all_status, default=[], placeholder="Pilih Status...")
            if selected_status:
                df = df[df[col_status].isin(selected_status)]

        search_query = st.text_input("🔎 Cari Prospek / Customer:", placeholder="Ketik nama customer...")
        if search_query:
            if col_prospek in df.columns:
                df = df[df[col_prospek].astype(str).str.contains(search_query, case=False, na=False)]

    st.caption(f"ℹ️ Total data dimuat: **{format_id(len(df), 0)} baris**")
    
    # --- METRIK ---
    total_deal_cust = df[df[col_status].astype(str).str.contains('trial order|5', case=False, na=False)].shape[0]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Total Omzet", f"{format_id(df[col_omzet].sum(), 2)}")
    col2.metric("⚖️ Total Berat", f"{format_id(df[col_berat].sum(), 2)} Kg")
    col3.metric("👥 Total Prospek", f"{format_id(df[col_prospek].nunique(), 0)}")
    col4.metric("🎯 Deal (Trial Order)", f"{format_id(total_deal_cust, 0)} Cust")

    # --- TABEL ---
    with st.container(border=True):
        st.subheader("📋 Detail Prospek Customer")
        df_sorted = df.sort_values(by=col_omzet, ascending=False).reset_index(drop=True)
        
        df_display = pd.DataFrame()
        df_display["Sales Name"] = df_sorted[col_sales] if col_sales in df_sorted.columns else "-"
        df_display["Nama Customer"] = df_sorted[col_prospek] if col_prospek in df_sorted.columns else "-"
        df_display["Produk Yang Ditawarkan"] = df_sorted[col_produk] if col_produk and col_produk in df_sorted.columns else "-"
        df_display["Status"] = df_sorted[col_status] if col_status in df_sorted.columns else "-"
        
        if col_visit in df_sorted.columns:
            df_display["Visit Terakhir"] = pd.to_datetime(df_sorted[col_visit], errors='coerce').dt.strftime('%Y-%m-%d').fillna('-')
        else:
            df_display["Visit Terakhir"] = "-"
            
        if col_omzet in df_sorted.columns:
            df_display["Perkiraan Omzet"] = df_sorted[col_omzet].apply(lambda x: format_id(x, 2))
        else:
            df_display["Perkiraan Omzet"] = "0,00"

        available_cols = list(df_display.columns)

        html_table = """
        <div style='max-height: 450px; overflow-y: auto; overflow-x: auto; border: 1px solid #d6d6d6; border-radius: 8px; margin-bottom: 15px;'>
            <table style='width: 100%; border-collapse: collapse; font-size: 13px; background-color: white;'>
                <thead>
                    <tr style='background-color: #f8f9fb; color: #31333F;'>
                        <th style='position: sticky; top: 0; left: 0; z-index: 3; background-color: #f8f9fb; padding: 10px; border: 1px solid #d6d6d6; text-align: center; min-width: 50px;'>No.</th>
        """
        
        for col in available_cols:
            html_table += f"<th style='position: sticky; top: 0; z-index: 2; background-color: #f8f9fb; padding: 10px; border: 1px solid #d6d6d6; text-align: center;'>{col}</th>"
        
        html_table += "</tr></thead><tbody>"
        
        for idx, row in df_display.iterrows():
            row_num = idx + 1
            html_table += f"<tr><td style='position: sticky; left: 0; z-index: 1; background-color: #ffffff; padding: 8px; border: 1px solid #d6d6d6; text-align: center; color: #31333F;'>{row_num}</td>"
            for col in available_cols:
                val = row[col]
                if col == "Perkiraan Omzet":
                    align = "right"
                elif col in ["Sales Name", "Status", "Visit Terakhir"]:
                    align = "center"
                else:
                    align = "left"
                    
                html_table += f"<td style='padding: 8px; border: 1px solid #d6d6d6; text-align: {align}; color: #31333F;'>{val}</td>"
            html_table += "</tr>"
            
        html_table += "</tbody></table></div>"
        
        st.markdown(html_table, unsafe_allow_html=True)

    # --- GRAFIK PERKIRAAN OMZET PER BULAN ---
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
                labels={'Bulan_Tahun': 'Bulan / Periode', col_omzet: 'Perkiraan Omzet'}
            )
            
            max_y1 = df_chart[col_omzet].max() * 1.1 if not df_chart.empty else 10

            fig1.update_layout(
                separators=',.',
                yaxis=dict(
                    tickformat='~s',
                    range=[0, max_y1],
                    nticks=8
                ),
                margin=dict(l=20, r=20, t=20, b=40),
                height=350,
                xaxis=dict(tickangle=-25)
            )
            fig1.update_traces(
                marker_color='#4C78A8',
                hovertemplate="<b>%{x}</b><br>Omzet: Rp %{y:,.2f}<extra></extra>"
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
            labels={col_omzet: "Perkiraan Omzet", col_sales: "Sales Name", col_status: "Status"}
        )
        
        max_y2 = df_status[col_omzet].max() * 1.1 if not df_status.empty else 10

        fig2.update_layout(
            separators=',.',
            yaxis=dict(
                tickformat='~s',
                range=[0, max_y2],
                nticks=8
            ),
            margin=dict(l=20, r=20, t=20, b=80),
            height=420,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.35,
                xanchor="center",
                x=0.5,
                font=dict(size=10)
            )
        )
        fig2.update_traces(
            hovertemplate="<b>Sales: %{x}</b><br>Status: %{fullData.name}<br>Omzet: Rp %{y:,.2f}<extra></extra>"
        )
        
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})