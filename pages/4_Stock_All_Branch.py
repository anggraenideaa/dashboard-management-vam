import streamlit as st
import pandas as pd
from db import load_stock_branch

st.set_page_config(page_title="Stock All Branch", layout="wide")

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

st.title("📦 Stock All Branch")
st.markdown("<div class='spacer-15'></div>", unsafe_allow_html=True)

df = load_stock_branch()

if df is not None and not df.empty:
    df.columns = df.columns.astype(str).str.strip()
    
    col_kg_tabel = "KG"
    col_total_kg = "TOTAL KG"
    col_stock_akhir = "STOCK AKHIR"
    col_item = "ITEM"
    col_branch = "BRANCH"
    col_gudang = "GUDANG"
    col_packaging = "PACKAGING"
    
    # Deteksi kolom kategori secara fleksibel
    cat_col_opts = [c for c in df.columns if "kategori" in c.lower() or "cat" in c.lower()]
    col_kat = cat_col_opts[0] if cat_col_opts else None
    
    def clean_indo_numeric(series):
        return pd.to_numeric(
            series.astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False).str.strip(),
            errors='coerce'
        ).fillna(0)

    if col_total_kg in df.columns: df[col_total_kg] = clean_indo_numeric(df[col_total_kg])
    if col_stock_akhir in df.columns: df[col_stock_akhir] = clean_indo_numeric(df[col_stock_akhir])
    if col_kg_tabel in df.columns: df[col_kg_tabel] = clean_indo_numeric(df[col_kg_tabel])

    # --- KECUALIKAN PACKAGING BERISI "PD" ---
    if col_packaging in df.columns:
        df = df[~df[col_packaging].astype(str).str.upper().str.contains("PD", na=False)]

    # --- KECUALIKAN KATEGORI YANG BERISI "SAMPLE" ---
    if col_kat in df.columns:
        df = df[~df[col_kat].astype(str).str.upper().str.contains("SAMPLE", na=False)]

    df_display = df.copy()

    with st.expander("🔍 Filter Data Stock All Branch", expanded=False):
        f1, f2, f3, f4 = st.columns(4)

        if col_branch in df.columns:
            branch_options = sorted(df[col_branch].dropna().astype(str).unique().tolist())
            selected_branch = f1.multiselect("Filter Branch:", branch_options, placeholder="Pilih Cabang...")
            if selected_branch:
                df_display = df_display[df_display[col_branch].astype(str).isin(selected_branch)]

        if col_gudang in df.columns:
            gudang_options = sorted(df_display[col_gudang].dropna().astype(str).unique().tolist())
            selected_gudang = f2.multiselect("Filter Gudang:", gudang_options, placeholder="Pilih Gudang...")
            if selected_gudang:
                df_display = df_display[df_display[col_gudang].astype(str).isin(selected_gudang)]

        if col_packaging in df.columns:
            pkg_options = sorted(df_display[col_packaging].dropna().astype(str).unique().tolist())
            selected_pkg = f3.multiselect("Filter Packaging:", pkg_options, placeholder="Pilih Packaging...")
            if selected_pkg:
                df_display = df_display[df_display[col_packaging].astype(str).isin(selected_pkg)]

        if col_item in df.columns:
            item_options = sorted(df_display[col_item].dropna().astype(str).unique().tolist())
            selected_item = f4.multiselect("Cari/Filter Item:", item_options, placeholder="Ketik nama item...")
            if selected_item:
                df_display = df_display[df_display[col_item].astype(str).isin(selected_item)]

    st.markdown("<div class='spacer-5'></div>", unsafe_allow_html=True)
    st.caption(f"ℹ️ Total baris data stock dimuat: **{format_id(len(df_display), 0)} baris**")

    total_item = df_display[col_item].nunique() if col_item in df_display.columns else 0
    total_kg_sum = df_display[col_total_kg].sum() if col_total_kg in df_display.columns else 0
    total_stock_akhir = df_display[col_stock_akhir].sum() if col_stock_akhir in df_display.columns else 0

    m1, m2, m3 = st.columns(3)
    m1.metric("📦 Total Item", f"{format_id(total_item, 0)}")
    m2.metric("⚖️ Total KG", f"{format_id(total_kg_sum, 2)}")
    m3.metric("📊 Stock Akhir", f"{format_id(total_stock_akhir, 2)}")

    st.markdown("<div class='spacer-10'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("📋 Tabel Stok Barang")
        
        # Kolom kategori sengaja tidak dimasukkan ke dalam list agar tidak tampil di tabel
        cols_to_show = [col_branch, col_item, col_packaging, col_kg_tabel, col_stock_akhir]
        available_cols = [c for c in cols_to_show if c in df_display.columns]
        df_final = df_display[available_cols].sort_values(by=col_branch).reset_index(drop=True)
        df_final.index = df_final.index + 1
        
        # Render tabel dengan st.dataframe
        st.dataframe(
            df_final, 
            use_container_width=True,
            hide_index=False,
            column_config={
                "_index": st.column_config.Column("No.", width="small", alignment="center"),
                col_branch: st.column_config.TextColumn(col_branch, width="small", alignment="center"),
                col_item: st.column_config.TextColumn(col_item, width="large", alignment="left"),
                col_packaging: st.column_config.TextColumn(col_packaging, width="small", alignment="center"),
                col_kg_tabel: st.column_config.NumberColumn(col_kg_tabel, width="small", alignment="center"),
                col_stock_akhir: st.column_config.NumberColumn(col_stock_akhir, width="small", alignment="center")
            }
        )
else:
    st.warning("Data Stock belum tersedia atau gagal dimuat.")