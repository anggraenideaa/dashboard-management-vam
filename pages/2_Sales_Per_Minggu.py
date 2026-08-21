import streamlit as st
import pandas as pd
import plotly.express as px
from decimal import Decimal
import re
from db import load_sales_report

st.set_page_config(page_title="Sales Performance Dashboard", layout="wide")

# Fungsi untuk memuat file CSS eksternal (terpusat)
def load_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"File CSS '{file_name}' tidak ditemukan. Pastikan folder 'assets' dan file 'style.css' sudah dibuat.") 

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

st.title("📊 Sales Performance Dashboard")
st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

# Load Data dari db.py
df = load_sales_report()

if df is None:
    st.error("Fungsi `load_sales_report()` mengembalikan nilai `None`. Periksa koneksi database/Google Sheets Anda.")
elif df.empty:
    st.error("DataFrame kosong (`df.empty` bernilai True). Pastikan sumber data memiliki isi.")
else:
    # 1. BERSIHKAN NAMA KOLOM DARI SPASI TERSEMBUNYI
    df.columns = df.columns.astype(str).str.strip()

    # --- 1.1 FILTER TANGGAL BERDASARKAN Tgl_Inv (MINGGUAN DEFAULT) ---
    col_tgl_inv = "Tgl_Inv"
    if col_tgl_inv in df.columns:
        df[col_tgl_inv] = pd.to_datetime(df[col_tgl_inv], errors="coerce")
        
        # Rentang tanggal mingguan default
        start_date = pd.to_datetime("2026-08-08")
        end_date = pd.to_datetime("2026-08-14")
        
        df = df[(df[col_tgl_inv] >= start_date) & (df[col_tgl_inv] <= end_date)]
    else:
        st.warning(f"Kolom tanggal invoice ('{col_tgl_inv}') tidak ditemukan pada data. Filter tanggal mingguan dilewati.")

    if df.empty:
        st.warning("Tidak ada data sales yang ditemukan pada rentang tanggal tersebut (01 Agustus 2026 - 07 Agustus 2026).")
    else:
        # 2. PEMBERSIHAN DATA NET SALES
        if "Net_Sales_Amnt_Excl_Ppn" in df.columns:
            def clean_to_decimal(val):
                try:
                    if pd.isna(val):
                        return Decimal('0')
                    s = str(val)
                    s = s.replace("Rp", "").replace("(", "-").replace(")", "").replace(",", "")
                    s = re.sub(r'[^0-9.\-]', '', s)
                    if s == "" or s == "-":
                        return Decimal('0')
                    return Decimal(s)
                except Exception:
                    return Decimal('0')

            df["Net_Sales_Amnt_Excl_Ppn"] = df["Net_Sales_Amnt_Excl_Ppn"].apply(clean_to_decimal).astype(float)
        else:
            df["Net_Sales_Amnt_Excl_Ppn"] = 0.0

        # 3. PEMBERSIHAN KOLOM NUMERIK LAINNYA
        other_numeric_cols = ["Total_COGM", "Total_COGS", "Tot_Qty_Kg", "Target"]
        for col in other_numeric_cols:
            if col in df.columns:
                if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
                    df[col] = pd.to_numeric(
                        df[col].astype(str)
                        .str.replace("(", "-", regex=False)
                        .str.replace(")", "", regex=False)
                        .str.replace(",", "", regex=False)
                        .str.replace(r'[^0-9.\-]', '', regex=True), 
                        errors="coerce"
                    ).fillna(0)
                else:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            else:
                df[col] = 0

        if "Sales_Name" in df.columns:
            df["Sales_Name"] = df["Sales_Name"].fillna("UNCATEGORIZED").astype(str).str.strip().str.upper()

        # Pembatasan Akses Sales
        if "role" in st.session_state and st.session_state.role == "sales":
            if "nama_sales" in st.session_state:
                df = df[df["Sales_Name"] == st.session_state.nama_sales.strip().upper()]

        # 4. DETEKSI DAN EKSTRAKSI PERIODE
        if "Periode" in df.columns:
            df["Periode_Bulan"] = df["Periode"].astype(str).str.strip()
        else:
            date_col = None
            for c in ["Order_Date", "Date", "Tgl", "Tanggal"]:
                if c in df.columns:
                    date_col = c
                    break
            if date_col:
                df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
                df["Periode_Bulan"] = df[date_col].dt.to_period("M").astype(str)
            else:
                df["Periode_Bulan"] = "2026-08"

        df["Net_Margin_COGM"] = (df["Net_Sales_Amnt_Excl_Ppn"] - df["Total_COGM"]).round(2)

        # ==========================================
        # FILTER UTAMA (DEFAULT TERTUTUP / COLLAPSED)
        # ==========================================
        with st.expander("🔍 Filter Data Dashboard", expanded=False):
            f_col1, f_col2 = st.columns(2)
            
            if "Branch" in df.columns:
                all_branches = sorted(df["Branch"].dropna().astype(str).unique().tolist())
                with f_col1:
                    selected_branches = st.multiselect("Filter Branch:", options=all_branches, default=[], placeholder="Pilih Cabang...")
                if selected_branches:
                    df = df[df["Branch"].isin(selected_branches)]

            if "Sales_Name" in df.columns and (not ("role" in st.session_state and st.session_state.role == "sales")):
                all_sales = sorted(df["Sales_Name"].dropna().unique().tolist())
                with f_col2:
                    selected_sales = st.multiselect("Filter Sales Name:", options=all_sales, default=[], placeholder="Pilih Sales...")
                if selected_sales:
                    df = df[df["Sales_Name"].isin(selected_sales)]

            f_col3, f_col4 = st.columns(2)
            
            if "Cust_Name" in df.columns:
                all_cust = sorted(df["Cust_Name"].dropna().astype(str).unique().tolist())
                with f_col3:
                    selected_cust = st.multiselect("Filter Customer:", options=all_cust, default=[], placeholder="Pilih Customer...")
                if selected_cust:
                    df = df[df["Cust_Name"].isin(selected_cust)]
                    
            if "Periode_Bulan" in df.columns:
                all_periode = sorted(df["Periode_Bulan"].dropna().unique().tolist())
                with f_col4:
                    selected_periode = st.multiselect("Filter Periode:", options=all_periode, default=[], placeholder="Pilih Periode...")
                if selected_periode:
                    df = df[df["Periode_Bulan"].isin(selected_periode)]

        st.caption(f"ℹ️ Total baris data dimuat (Periode Tgl_Inv 08-14 Agustus 2026): **{format_id(len(df), 0)} baris**")
        st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True)

        # 5. KARTU METRIK UTAMA
        total_net_sales = df["Net_Sales_Amnt_Excl_Ppn"].sum()
        total_cogm = df["Total_COGM"].sum()
        total_net_margin_cogm = df["Net_Margin_COGM"].sum()

        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Net Sales Excl PPN", f"Rp {format_id(total_net_sales, 2)}")
        m2.metric("📦 Total COGM", f"Rp {format_id(total_cogm, 2)}")
        m3.metric("📈 Net Margin COGM", f"Rp {format_id(total_net_margin_cogm, 2)}")

        st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

        # 6. TABEL RINGKASAN PERFORMA PER SALES
        if "Sales_Name" in df.columns and not df.empty:
            df_target_per_bulan = df.groupby(["Sales_Name", "Periode_Bulan"])["Target"].max().reset_index()
            df_total_target = df_target_per_bulan.groupby("Sales_Name")["Target"].sum().reset_index()

            df_sales_agg = df.groupby("Sales_Name").agg({
                "Net_Sales_Amnt_Excl_Ppn": "sum",
                "Total_COGM": "sum",
                "Total_COGS": "sum"
            }).reset_index()

            df_summary = pd.merge(df_sales_agg, df_total_target, on="Sales_Name", how="left").fillna(0)

            df_summary["Gross_Margin_COGM"] = df_summary["Net_Sales_Amnt_Excl_Ppn"] - df_summary["Total_COGM"]
            df_summary["Gross_Margin_COGS"] = df_summary["Net_Sales_Amnt_Excl_Ppn"] - df_summary["Total_COGS"]
            
            df_summary["Net_Margin_COGM (%)"] = df_summary.apply(
                lambda row: ((row["Net_Sales_Amnt_Excl_Ppn"] - row["Total_COGM"]) / row["Net_Sales_Amnt_Excl_Ppn"] * 100) 
                if row["Net_Sales_Amnt_Excl_Ppn"] != 0 else 0, axis=1
            )
            df_summary["Net_Margin_COGS (%)"] = df_summary.apply(
                lambda row: ((row["Net_Sales_Amnt_Excl_Ppn"] - row["Total_COGS"]) / row["Net_Sales_Amnt_Excl_Ppn"] * 100) 
                if row["Net_Sales_Amnt_Excl_Ppn"] != 0 else 0, axis=1
            )

            df_summary = df_summary.sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=False)

            df_display = pd.DataFrame()
            df_display["Sales Name"] = df_summary["Sales_Name"]
            df_display["Net Sales Amnt Excl Ppn"] = df_summary["Net_Sales_Amnt_Excl_Ppn"].apply(lambda x: f"Rp {format_id(x, 2)}")
            df_display["Gross Margin COGM"] = df_summary["Gross_Margin_COGM"].apply(lambda x: f"Rp {format_id(x, 2)}")
            df_display["Gross Margin COGS"] = df_summary["Gross_Margin_COGS"].apply(lambda x: f"Rp {format_id(x, 2)}")
            df_display["Net Margin COGM"] = df_summary["Net_Margin_COGM (%)"].apply(lambda x: f"{format_id(x, 2)}%")
            df_display["Net Margin COGS"] = df_summary["Net_Margin_COGS (%)"].apply(lambda x: f"{format_id(x, 2)}%")

            df_display.index = range(1, len(df_display) + 1)

            with st.container(border=True):
                st.subheader("📋 Ringkasan Performa Per Sales")
                st.dataframe(
                    df_display, 
                    use_container_width=True,
                    column_config={
                        "Sales Name": st.column_config.TextColumn("Sales Name", width="medium", alignment="left"),
                        "Net Sales Amnt Excl Ppn": st.column_config.TextColumn("Net Sales Amnt Excl Ppn", alignment="right"),
                        "Gross Margin COGM": st.column_config.TextColumn("Gross Margin COGM", alignment="right"),
                        "Gross Margin COGS": st.column_config.TextColumn("Gross Margin COGS", alignment="right"),
                        "Net Margin COGM": st.column_config.TextColumn("Net Margin COGM", alignment="center"),
                        "Net Margin COGS": st.column_config.TextColumn("Net Margin COGS", alignment="center"),
                    }
                )

        st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

        # 7. GRAFIK PENCAPAIAN SALES VS TARGET
        if "Sales_Name" in df.columns and not df.empty:
            df_t1 = df.groupby(["Sales_Name", "Periode_Bulan"])["Target"].max().reset_index()
            df_target_final = df_t1.groupby("Sales_Name")["Target"].sum().reset_index()

            df_sales_val = df.groupby("Sales_Name")["Net_Sales_Amnt_Excl_Ppn"].sum().reset_index()
            df_target = pd.merge(df_sales_val, df_target_final, on="Sales_Name", how="left").fillna(0)
            
            df_target = df_target.sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=False)
            sales_order = df_target["Sales_Name"].tolist()

            df_melted = df_target.melt(id_vars="Sales_Name", value_vars=["Target", "Net_Sales_Amnt_Excl_Ppn"], 
                                       var_name="Kategori", value_name="Nominal")
            
            df_melted["Kategori"] = df_melted["Kategori"].replace({
                "Target": "Target",
                "Net_Sales_Amnt_Excl_Ppn": "Net Sales"
            })
            
            fig_target = px.bar(
                df_melted, 
                x="Sales_Name", 
                y="Nominal", 
                color="Kategori", 
                barmode="group",
                category_orders={"Sales_Name": sales_order},
                labels={"Nominal": "Nominal (Rp)", "Sales_Name": "Sales Name", "Kategori": "Keterangan"},
                color_discrete_map={"Target": "#FF6B6B", "Net Sales": "#4D96FF"},
                template="plotly_white"
            )
            
            fig_target.update_layout(
                font=dict(family="sans-serif", size=12, color="#333333"),
                legend=dict(
                    orientation="h", y=1.12, x=0.5, xanchor="center",
                    bgcolor="rgba(255,255,255,0.8)", bordercolor="rgba(0,0,0,0.1)", borderwidth=1
                ),
                margin=dict(l=20, r=20, t=30, b=20),
                hovermode="x unified",
                xaxis=dict(showgrid=False, showline=True, linewidth=1, linecolor='lightgray'),
                yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.08)", showline=True, linewidth=1, linecolor='lightgray', tickformat=',.0f')
            )
            fig_target.update_traces(hovertemplate="<b>%{x}</b><br>%{legendgroup}: Rp %{y:,.2f}<extra></extra>")

            with st.container(border=True):
                st.subheader("🎯 Pencapaian Sales vs Target (Mingguan)")
                st.plotly_chart(fig_target, use_container_width=True, config={"displayModeBar": False})

        # 8. 10 PRODUK TERATAS & 10 CUSTOMER TERTINGGI
        c1, c2 = st.columns(2)

        with c1:
            item_col = "KeyItem" if "KeyItem" in df.columns else ("Item_Name_Vam" if "Item_Name_Vam" in df.columns else None)
            
            if item_col:
                top_products = df.groupby(item_col)["Tot_Qty_Kg"].sum().reset_index()
                top_products = top_products.sort_values(by="Tot_Qty_Kg", ascending=False).head(10)
                
                fig_prod = px.bar(
                    top_products, 
                    x=item_col, 
                    y="Tot_Qty_Kg", 
                    labels={item_col: "Nama Produk", "Tot_Qty_Kg": "Total Qty (Kg)"},
                    template="plotly_white",
                    color="Tot_Qty_Kg",
                    color_continuous_scale="Viridis"
                )
                fig_prod.update_layout(
                    height=450,
                    bargap=0.3,
                    xaxis=dict(tickangle=-35, showgrid=False, showline=True, linewidth=1, linecolor='lightgray'),
                    yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.08)", showline=True, linewidth=1, linecolor='lightgray', tickformat=',.0f'),
                    margin=dict(l=20, r=20, t=10, b=80),
                    coloraxis_showscale=False
                )
                fig_prod.update_traces(hovertemplate="<b>%{x}</b><br>Total Qty: %{y:,.2f} Kg<extra></extra>")
                
                with st.container(border=True):
                    st.subheader("🔥 10 Produk Teratas (Best Seller)")
                    st.plotly_chart(fig_prod, use_container_width=True, config={"displayModeBar": False})
            else:
                st.warning("Kolom produk ('KeyItem' atau 'Item_Name_Vam') tidak ditemukan.")

        with c2:
            if "Cust_Name" in df.columns:
                top_cust = df.groupby("Cust_Name")["Net_Sales_Amnt_Excl_Ppn"].sum().reset_index()
                top_cust = top_cust.sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=False).head(10)
                top_cust = top_cust.sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=True) 
                
                fig_cust = px.bar(
                    top_cust, 
                    x="Net_Sales_Amnt_Excl_Ppn", 
                    y="Cust_Name", 
                    orientation="h",
                    labels={"Cust_Name": "Customer Name", "Net_Sales_Amnt_Excl_Ppn": "Net Sales (Rp)"},
                    template="plotly_white",
                    color="Net_Sales_Amnt_Excl_Ppn",
                    color_continuous_scale="Tealgrn"
                )
                fig_cust.update_layout(
                    height=450,
                    bargap=0.3,
                    xaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.08)", showline=True, linewidth=1, linecolor='lightgray', tickformat=',.0f'),
                    yaxis=dict(showgrid=False, showline=True, linewidth=1, linecolor='lightgray', categoryorder='total ascending'),
                    margin=dict(l=20, r=20, t=10, b=40),
                    coloraxis_showscale=False
                )
                fig_cust.update_traces(hovertemplate="<b>%{y}</b><br>Net Sales: Rp %{x:,.2f}<extra></extra>")
                
                with st.container(border=True):
                    st.subheader("👑 10 Customer Pembelian Tertinggi")
                    st.plotly_chart(fig_cust, use_container_width=True, config={"displayModeBar": False})
            else:
                st.warning("Kolom 'Cust_Name' tidak ditemukan.")

        # 9. TOTAL PENJUALAN PER CABANG
        if "Branch" in df.columns:
            df_branch = df.groupby("Branch")["Net_Sales_Amnt_Excl_Ppn"].sum().reset_index()
            df_branch = df_branch.sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=False)
            
            fig_branch = px.pie(
                df_branch, 
                names="Branch", 
                values="Net_Sales_Amnt_Excl_Ppn", 
                hole=0.45,
                labels={"Branch": "Branch", "Net_Sales_Amnt_Excl_Ppn": "Total Sales"},
                template="plotly_white",
                color_discrete_sequence=px.colors.qualitative.Prism
            )
            fig_branch.update_traces(
                textinfo='value', 
                texttemplate='%{value:,.0f}',
                hoverinfo='label+value+percent',
                hovertemplate="<b>Cabang: %{label}</b><br>Total Sales: Rp %{value:,.0f}<br>Persentase: %{percent}<extra></extra>",
                marker=dict(line=dict(color='#ffffff', width=2))
            )
            fig_branch.update_layout(
                margin=dict(l=20, r=20, t=10, b=10),
                legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center")
            )
            
            with st.container(border=True):
                st.subheader("🏢 Total Penjualan per Cabang")
                st.plotly_chart(fig_branch, use_container_width=True, config={"displayModeBar": False})
        else:
            st.warning("Kolom 'Branch' tidak ditemukan pada data.")
