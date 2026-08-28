from db import load_hpp_pricelist
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Pricelist & HPP Barang", layout="wide", initial_sidebar_state="auto"
)


def load_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass


load_css("assets/style.css")


def format_id(val, decimal=2):
    try:
        if decimal == 0:
            formatted = f"{float(val):,.0f}"
        else:
            formatted = f"{float(val):,.{decimal}f}"
        formatted = (
            formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        )
        return formatted
    except Exception:
        return val


# CSS: HEADER FREEZE (STICKY) + SCROLL HORIZONTAL AKTIF + MAX-HEIGHT
responsive_table_css = """
<style>
.responsive-table-container {
    width: 100% !important;
    max-height: 480px !important;    
    overflow-x: auto !important;    
    overflow-y: auto !important;    
    border-radius: 8px;
    border: 1px solid #e2e8f0;
    background-color: #ffffff;
    position: relative;
    margin-bottom: 25px !important;
}

.responsive-table-container table {
    width: 100%;
    border-collapse: collapse;
    font-family: inherit;
    font-size: 14px;
    color: #1e293b;
    margin-bottom: 0px !important;
}

.responsive-table-container th:nth-child(1), .responsive-table-container td:nth-child(1) { 
    width: 6%; 
    text-align: center; 
}
.responsive-table-container th:nth-child(1) {
    white-space: nowrap !important;
}

.responsive-table-container th:nth-child(2), .responsive-table-container td:nth-child(2) { 
    width: 44%; 
    text-align: left; 
} 

.responsive-table-container th:nth-child(3), .responsive-table-container td:nth-child(3) { 
    width: 25%; 
    text-align: center !important; 
}

.responsive-table-container th:nth-child(4), .responsive-table-container td:nth-child(4) { 
    width: 25%; 
    text-align: right; 
}

.responsive-table-container th {
    background-color: #f8f9fb !important;
    color: #0f172a !important;
    font-weight: bold;
    text-align: center !important;
    padding: 12px 10px;
    border-bottom: 2px solid #e2e8f0;
    position: sticky !important;
    top: 0 !important;
    z-index: 10 !important;
}

.responsive-table-container td {
    padding: 12px 10px; 
    border-bottom: 1px solid #f1f5f9;
}

@media (min-width: 769px) {
    .responsive-table-container td {
        white-space: nowrap;
    }
}

@media (max-width: 768px) {
    .responsive-table-container table {
        font-size: 12px;
    }
    .responsive-table-container td, .responsive-table-container th {
        padding: 10px 6px;
        white-space: normal !important;
        word-break: break-word !important;
    }
    .responsive-table-container td:nth-child(3) {
        text-align: center !important;
    }
    .responsive-table-container th:nth-child(1) {
        white-space: nowrap !important;
    }
}

.responsive-table-container tr:hover {
    background-color: #f8fafc;
}
</style>
"""

st.markdown(responsive_table_css, unsafe_allow_html=True)

st.title("🏷️ Pricelist & HPP Barang")
st.markdown("<div class='spacer-15'></div>", unsafe_allow_html=True)

# AMBIL DATA DARI SHEET "HPP Berlaku"
try:
    df = load_hpp_pricelist(sheet_name="HPP Berlaku")
except TypeError:
    try:
        df = load_hpp_pricelist("HPP Berlaku")
    except Exception:
        df = load_hpp_pricelist()

if df is None:
    st.error("Fungsi `load_hpp_pricelist()` mengembalikan nilai `None`.")
elif df.empty:
    st.warning("Data Pricelist / HPP dari sheet 'HPP Berlaku' belum tersedia.")
else:
    df.columns = df.columns.astype(str).str.strip()

    col_item = "Item_Name" if "Item_Name" in df.columns else df.columns[0]
    cat_col_opts = [
        c
        for c in df.columns
        if "kategori" in c.lower() or "cat" in c.lower()
    ]
    col_kat = cat_col_opts[0] if cat_col_opts else None

    hpp_col_opts = [
        c for c in df.columns if "hpp" in c.lower() or "hpp/kg" in c.lower()
    ]
    col_hpp = hpp_col_opts[0] if hpp_col_opts else None

    # --- PEMBERSIHAN DATA EKSTREM (BUANG BARIS KOSONG & HPP <= 0) ---
    # 1. Buang baris yang nama barangnya kosong / NaN / None dari Excel
    df = df.dropna(subset=[col_item])
    df = df[df[col_item].astype(str).str.strip().str.lower().isin(["", "nan", "none", "nat"]) == False]

    # 2. Bersihkan kolom HPP
    if col_hpp:
        cleaned_series = (
            df[col_hpp]
            .astype(str)
            .str.replace("Rp", "", case=False, regex=True)
            .str.strip()
        )
        cleaned_series = (
            cleaned_series.str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.replace(r"[^0-9.\-]", "", regex=True)
        )
        df[col_hpp] = pd.to_numeric(cleaned_series, errors="coerce")

        # 3. BUANG SEMUA BARIS YANG HPP-NYA NaN ATAU <= 0
        df = df.dropna(subset=[col_hpp])
        df = df[df[col_hpp] > 0]

    with st.expander("🔍 Filter & Pencarian Pricelist", expanded=False):
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            search_query = st.text_input(
                "Cari Barang / Item Name:",
                placeholder="Ketik nama barang...",
            )

        selected_kat = []
        if col_kat:
            all_categories = sorted(
                df[col_kat].dropna().astype(str).unique().tolist()
            )
            with f_col2:
                selected_kat = st.multiselect(
                    "Filter Kategori:",
                    options=all_categories,
                    placeholder="Pilih Kategori...",
                )

    if search_query:
        df = df[
            df[col_item]
            .astype(str)
            .str.contains(search_query, case=False, na=False)
        ]
    if selected_kat and col_kat:
        df = df[df[col_kat].astype(str).isin(selected_kat)]

    # Reset index supaya nomor urutnya rapi berurutan mulai dari 0 tanpa loncat-loncat
    df = df.reset_index(drop=True)

    st.markdown("<div class='spacer-5'></div>", unsafe_allow_html=True)
    st.caption(
        f"ℹ️ Total produk ditemukan dari sheet **HPP Berlaku**: **{format_id(len(df), 0)} baris**"
    )

    df_display = pd.DataFrame()
    df_display["No."] = range(1, len(df) + 1)
    df_display["Item Name"] = (
        df[col_item] if col_item in df.columns else "-"
    )
    df_display["Kategori"] = (
        df[col_kat] if col_kat and col_kat in df.columns else "-"
    )

    if col_hpp in df.columns:
        df_display["HPP"] = df[col_hpp].apply(
            lambda x: format_id(x, decimal=2)
        )
    else:
        df_display["HPP"] = "-"

    st.markdown("<div class='spacer-10'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("📋 Tabel Pricelist & HPP Berlaku")
        st.markdown("<div class='spacer-5'></div>", unsafe_allow_html=True)

        html_table = df_display.to_html(index=False, escape=False)

        spacer_row = '<tr style="height: 40px; border: none;"><td colspan="4" style="border: none; background: transparent;"></td></tr>'
        html_table_with_spacer = html_table.replace("</tbody>", f"{spacer_row}</tbody>")

        wrapped_html = f"""
        <div class="responsive-table-container">
            {html_table_with_spacer}
        </div>
        """

        st.markdown(wrapped_html, unsafe_allow_html=True)