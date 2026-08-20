import streamlit as st
import pandas as pd
from db import load_hpp_pricelist

st.set_page_config(page_title="Pricelist & HPP Barang", layout="wide")

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

st.title("🏷️ Pricelist & HPP Barang")
st.markdown("<div class='spacer-15'></div>", unsafe_allow_html=True)

df = load_hpp_pricelist()

if df is None:
    st.error("Fungsi `load_hpp_pricelist()` mengembalikan nilai `None`.")
elif df.empty:
    st.warning("Data Pricelist / HPP belum tersedia.")
else:
    df.columns = df.columns.astype(str).str.strip()

    col_item = "Item_Name" if "Item_Name" in df.columns else df.columns[0]
    cat_col_opts = [c for c in df.columns if "kategori" in c.lower() or "cat" in c.lower()]
    col_kat = cat_col_opts[0] if cat_col_opts else None
    hpp_col_opts = [c for c in df.columns if "hpp" in c.lower()]
    col_hpp = hpp_col_opts[0] if hpp_col_opts else None

    # --- PEMBERSIHAN DATA HPP YANG BENAR ---
    if col_hpp:
        # 1. Ubah ke string dan hapus teks "Rp" serta spasi
        cleaned_series = df[col_hpp].astype(str).str.replace("Rp", "", case=False, regex=True).str.strip()
        
        # 2. Jika formatnya Indonesia (misal: 15.000,50), titik ribuan dibuang, koma diubah jadi titik desimal
        # Cek apakah menggunakan koma sebagai desimal
        cleaned_series = cleaned_series.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        
        # 3. Konversi ke numeric
        df[col_hpp] = pd.to_numeric(cleaned_series, errors="coerce").fillna(0)
        df = df[df[col_hpp] > 0]

    with st.expander("🔍 Filter & Pencarian Pricelist", expanded=False):
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            search_query = st.text_input("Cari Barang / Item Name:", placeholder="Ketik nama barang...")

        selected_kat = []
        if col_kat:
            all_categories = sorted(df[col_kat].dropna().astype(str).unique().tolist())
            with f_col2:
                selected_kat = st.multiselect("Filter Kategori:", options=all_categories, placeholder="Pilih Kategori...")

    if search_query:
        df = df[df[col_item].astype(str).str.contains(search_query, case=False, na=False)]
    if selected_kat and col_kat:
        df = df[df[col_kat].astype(str).isin(selected_kat)]

    st.markdown("<div class='spacer-5'></div>", unsafe_allow_html=True)
    st.caption(f"ℹ️ Total produk ditemukan: **{format_id(len(df), 0)} baris**")

    df_display = pd.DataFrame()
    df_display["Item Name"] = df[col_item] if col_item in df.columns else "-"
    df_display["Kategori"] = df[col_kat] if col_kat and col_kat in df.columns else "-"
    
    if col_hpp in df.columns:
        df_display["HPP"] = df[col_hpp].apply(lambda x: format_id(x, decimal=2))
    else:
        df_display["HPP"] = "0,00"

    df_display.index = range(1, len(df_display) + 1)

    st.markdown("<div class='spacer-10'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("📋 Tabel Pricelist & HPP")
        
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=False,
            column_config={
                "_index": st.column_config.Column("No.", width="small", alignment="center"),
                "Item Name": st.column_config.TextColumn("Item Name", width="large", alignment="left"),
                "Kategori": st.column_config.TextColumn("Kategori", width="medium", alignment="center"),
                "HPP": st.column_config.TextColumn("HPP", width="small", alignment="right")
            }
        )