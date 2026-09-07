from decimal import Decimal
import re
from db import load_sales_report
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Sales Performance Dashboard", layout="wide")


# Fungsi untuk memuat file CSS eksternal (terpusat) & CSS Responsif Tabel
def load_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(
            f"File CSS '{file_name}' tidak ditemukan. Pastikan folder 'assets' dan file 'style.css' sudah dibuat."
        )


load_css("assets/style.css")

# CSS tambahan untuk memaksa responsivitas mobile
st.markdown(
    """
    <style>
    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.8rem;
            padding-right: 0.8rem;
        }
    }
    </style>
""",
    unsafe_allow_html=True,
)


# Fungsi untuk memformat angka ke standar Indonesia (titik=ribuan, koma=desimal, 2 digit desimal)
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


st.title("📊 Sales Performance Dashboard")
st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

# Tentukan Role Pengguna
user_role = str(st.session_state.get("role", "sales")).lower()

# Load Data dari db.py
df = load_sales_report()

if df is None:
    st.error(
        "Fungsi `load_sales_report()` mengembalikan nilai `None`. Periksa koneksi database/Google Sheets Anda."
    )
elif df.empty:
    st.error(
        "DataFrame kosong (`df.empty` bernilai True). Pastikan sumber data memiliki isi."
    )
else:
    # 1. BERSIHKAN NAMA KOLOM DARI SPASI TERSEMBUNYI
    df.columns = df.columns.astype(str).str.strip()

    # --- 1.1 FILTER TANGGAL BERDASARKAN Tgl_Inv (MINGGUAN DEFAULT) ---
    col_tgl_inv = "Tgl_Inv"
    if col_tgl_inv in df.columns:
        df[col_tgl_inv] = pd.to_datetime(df[col_tgl_inv], errors="coerce")

        # Rentang tanggal mingguan default
        start_date = pd.to_datetime("2026-08-29")
        end_date = pd.to_datetime("2026-09-04")

        df = df[
            (df[col_tgl_inv] >= start_date) & (df[col_tgl_inv] <= end_date)
        ]
    else:
        st.warning(
            f"Kolom tanggal invoice ('{col_tgl_inv}') tidak ditemukan pada data. Filter tanggal mingguan dilewati."
        )

    if df.empty:
        st.warning(
            "Tidak ada data sales yang ditemukan pada rentang tanggal tersebut (29 Agustus - 04 September 2026)."
        )
    else:
        # 2. PEMBERSIHAN DATA NET SALES
        if "Net_Sales_Amnt_Excl_Ppn" in df.columns:

            def clean_to_decimal(val):
                try:
                    if pd.isna(val):
                        return Decimal("0")
                    s = str(val)
                    s = (
                        s.replace("Rp", "")
                        .replace("(", "-")
                        .replace(")", "")
                        .replace(",", "")
                    )
                    s = re.sub(r"[^0-9.\-]", "", s)
                    if s == "" or s == "-":
                        return Decimal("0")
                    return Decimal(s)
                except Exception:
                    return Decimal("0")

            df["Net_Sales_Amnt_Excl_Ppn_Dec"] = df[
                "Net_Sales_Amnt_Excl_Ppn"
            ].apply(clean_to_decimal)
            df["Net_Sales_Amnt_Excl_Ppn"] = df[
                "Net_Sales_Amnt_Excl_Ppn_Dec"
            ].astype(float)
        else:
            df["Net_Sales_Amnt_Excl_Ppn_Dec"] = Decimal("0")
            df["Net_Sales_Amnt_Excl_Ppn"] = 0.0

        # 3. PEMBERSIHAN KOLOM NUMERIK LAINNYA
        other_numeric_cols = ["Total_COGM", "Total_COGS", "Tot_Qty_Kg", "Target"]
        for col in other_numeric_cols:
            if col in df.columns:
                if df[col].dtype == object or pd.api.types.is_string_dtype(
                    df[col]
                ):
                    df[col] = pd.to_numeric(
                        df[col]
                        .astype(str)
                        .str.replace("(", "-", regex=False)
                        .str.replace(")", "", regex=False)
                        .str.replace(",", "", regex=False)
                        .str.replace(r"[^0-9.\-]", "", regex=True),
                        errors="coerce",
                    ).fillna(0)
                else:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            else:
                df[col] = 0

        # Simpan versi Decimal untuk COGM & COGS agar akurat
        for c_col in ["Total_COGM", "Total_COGS"]:
            if c_col in df.columns:
                df[f"{c_col}_Dec"] = df[c_col].apply(
                    lambda x: Decimal(str(x))
                )
            else:
                df[f"{c_col}_Dec"] = Decimal("0")

        if "Sales_Name" in df.columns:
            df["Sales_Name"] = (
                df["Sales_Name"]
                .fillna("UNCATEGORIZED")
                .astype(str)
                .str.strip()
                .str.upper()
            )

        # Pembatasan Akses Sales
        if user_role == "sales":
            if "nama_sales" in st.session_state:
                df = df[
                    df["Sales_Name"]
                    == str(st.session_state.nama_sales).strip().upper()
                ]

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
                df["Periode_Bulan"] = (
                    df[date_col].dt.to_period("M").astype(str)
                )
            else:
                df["Periode_Bulan"] = "2026-08"

        # TENTUKAN KOLOM BIAYA UTAMA (METRIK) BERDASARKAN ROLE
        if user_role in ["admin", "direksi"]:
            active_cost_col = "Total_COGM"
            active_cost_dec_col = "Total_COGM_Dec"
            cost_label = "COGM"
        else:  # sales
            active_cost_col = "Total_COGS"
            active_cost_dec_col = "Total_COGS_Dec"
            cost_label = "COGS"

        df[f"Net_Margin_{cost_label}"] = (
            df["Net_Sales_Amnt_Excl_Ppn"] - df[active_cost_col]
        ).round(2)

        # ==========================================
        # FILTER UTAMA (DEFAULT TERTUTUP / COLLAPSED)
        # ==========================================
        with st.expander("🔍 Filter Data Dashboard", expanded=False):
            f_col1, f_col2 = st.columns(2)

            if "Branch" in df.columns:
                all_branches = sorted(
                    df["Branch"].dropna().astype(str).unique().tolist()
                )
                with f_col1:
                    selected_branches = st.multiselect(
                        "Filter Branch:",
                        options=all_branches,
                        default=[],
                        placeholder="Pilih Cabang...",
                    )
                if selected_branches:
                    df = df[df["Branch"].isin(selected_branches)]

            if "Sales_Name" in df.columns and user_role in ["admin", "direksi"]:
                all_sales = sorted(df["Sales_Name"].dropna().unique().tolist())
                with f_col2:
                    selected_sales = st.multiselect(
                        "Filter Sales Name:",
                        options=all_sales,
                        default=[],
                        placeholder="Pilih Sales...",
                    )
                if selected_sales:
                    df = df[df["Sales_Name"].isin(selected_sales)]

            f_col3, f_col4 = st.columns(2)

            if "Cust_Name" in df.columns:
                all_cust = sorted(
                    df["Cust_Name"].dropna().astype(str).unique().tolist()
                )
                with f_col3:
                    selected_cust = st.multiselect(
                        "Filter Customer:",
                        options=all_cust,
                        default=[],
                        placeholder="Pilih Customer...",
                    )
                if selected_cust:
                    df = df[df["Cust_Name"].isin(selected_cust)]

            if "Periode_Bulan" in df.columns:
                all_periode = sorted(
                    df["Periode_Bulan"].dropna().unique().tolist()
                )
                with f_col4:
                    selected_periode = st.multiselect(
                        "Filter Periode:",
                        options=all_periode,
                        default=[],
                        placeholder="Pilih Periode...",
                    )
                if selected_periode:
                    df = df[df["Periode_Bulan"].isin(selected_periode)]

        st.caption(
            f"ℹ️ Total baris data dimuat (Periode Tgl_Inv 29 Agustus - 04 September 2026): **{format_id(len(df), 0)} baris**"
        )
        st.markdown(
            "<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True
        )

        # 5. KARTU METRIK UTAMA
        total_net_sales = df["Net_Sales_Amnt_Excl_Ppn"].sum()
        total_cost = df[active_cost_col].sum()
        total_net_margin = df[f"Net_Margin_{cost_label}"].sum()

        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Net Sales Excl PPN", f"Rp {format_id(total_net_sales, 2)}")
        m2.metric(f"📦 Total {cost_label}", f"Rp {format_id(total_cost, 2)}")
        m3.metric(
            f"📈 Net Margin {cost_label}", f"Rp {format_id(total_net_margin, 2)}"
        )

        st.markdown(
            "<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True
        )

        # 6. TABEL RINGKASAN PERFORMA PER SALES (RESPONSIF / NOWRAP MENGGUNAKAN HTML NATIVE)
        if "Sales_Name" in df.columns and not df.empty:
            df_target_per_bulan = (
                df.groupby(["Sales_Name", "Periode_Bulan"])["Target"]
                .max()
                .reset_index()
            )
            df_total_target = (
                df_target_per_bulan.groupby("Sales_Name")["Target"]
                .sum()
                .reset_index()
            )

            df_sales_agg = (
                df.groupby("Sales_Name")
                .agg(
                    {
                        "Net_Sales_Amnt_Excl_Ppn": "sum",
                        "Total_COGM": "sum",
                        "Total_COGS": "sum",
                    }
                )
                .reset_index()
            )

            df_summary = pd.merge(
                df_sales_agg, df_total_target, on="Sales_Name", how="left"
            ).fillna(0)
            df_summary = df_summary.sort_values(
                by="Net_Sales_Amnt_Excl_Ppn", ascending=False
            )

            if user_role in ["admin", "direksi"]:
                df_summary["Gross_Margin_COGM"] = (
                    df_summary["Net_Sales_Amnt_Excl_Ppn"]
                    - df_summary["Total_COGM"]
                )
                df_summary["Net_Margin_COGM (%)"] = df_summary.apply(
                    lambda row: (
                        (
                            row["Net_Sales_Amnt_Excl_Ppn"]
                            - row["Total_COGM"]
                        )
                        / row["Net_Sales_Amnt_Excl_Ppn"]
                        * 100
                    )
                    if row["Net_Sales_Amnt_Excl_Ppn"] != 0
                    else 0,
                    axis=1,
                )

            df_summary["Gross_Margin_COGS"] = (
                df_summary["Net_Sales_Amnt_Excl_Ppn"] - df_summary["Total_COGS"]
            )
            df_summary["Net_Margin_COGS (%)"] = df_summary.apply(
                lambda row: (
                    (row["Net_Sales_Amnt_Excl_Ppn"] - row["Total_COGS"])
                    / row["Net_Sales_Amnt_Excl_Ppn"]
                    * 100
                )
                if row["Net_Sales_Amnt_Excl_Ppn"] != 0
                else 0,
                axis=1,
            )

            # Buat baris data tabel secara aman
            rows_list = []
            for idx, row in enumerate(df_summary.iterrows(), start=1):
                r = row[1]
                s_name = str(r["Sales_Name"])
                net_sales = f"Rp {format_id(r['Net_Sales_Amnt_Excl_Ppn'], 2)}"

                extra_tds = ""
                if user_role in ["admin", "direksi"]:
                    g_cogm = f"Rp {format_id(r['Gross_Margin_COGM'], 2)}"
                    n_cogm = f"{format_id(r['Net_Margin_COGM (%)'], 2)}%"
                    extra_tds += f"<td style='text-align: right;'>{g_cogm}</td><td style='text-align: center;'>{n_cogm}</td>"

                g_cogs = f"Rp {format_id(r['Gross_Margin_COGS'], 2)}"
                n_cogs = f"{format_id(r['Net_Margin_COGS (%)'], 2)}%"
                extra_tds += f"<td style='text-align: right;'>{g_cogs}</td><td style='text-align: center;'>{n_cogs}</td>"

                row_html = f"<tr><td style='text-align: center;'>{idx}</td><td style='text-align: left;'>{s_name}</td><td style='text-align: right;'>{net_sales}</td>{extra_tds}</tr>"
                rows_list.append(row_html)

            rows_html_str = "".join(rows_list)

            # Buat header tabel secara aman
            if user_role in ["admin", "direksi"]:
                header_extra = "<th>Gross Margin COGM</th><th>Net Margin COGM (%)</th><th>Gross Margin COGS</th><th>Net Margin COGS (%)</th>"
            else:
                header_extra = "<th>Gross Margin COGS</th><th>Net Margin COGS (%)</th>"

            # Render HTML lengkap dengan nowrap agar rapi dan bisa scroll horizontal
            table_responsive_html = f"""
            <div style="width: 100%; overflow-x: auto; border-radius: 8px; border: 1px solid #e6e6e6;">
                <style>
                    .custom-resp-table {{
                        width: 100%;
                        border-collapse: collapse;
                        font-family: sans-serif;
                        font-size: 13px;
                        background-color: white;
                    }}
                    .custom-resp-table th {{
                        background-color: #f8f9fa;
                        color: #333333;
                        font-weight: 600;
                        padding: 12px 10px;
                        border-bottom: 2px solid #dee2e6;
                        white-space: nowrap;
                        text-align: center;
                    }}
                    .custom-resp-table td {{
                        padding: 10px;
                        border-bottom: 1px solid #eee;
                        color: #444444;
                        white-space: nowrap;
                    }}
                    .custom-resp-table tr:hover {{
                        background-color: #f1f3f5;
                    }}
                </style>
                <table class="custom-resp-table">
                    <thead>
                        <tr>
                            <th style="width: 50px;">No</th>
                            <th style="text-align: left;">Sales Name</th>
                            <th style="text-align: right;">Net Sales Excl Ppn</th>
                            {header_extra}
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html_str}
                    </tbody>
                </table>
            </div>
            """

            with st.container(border=True):
                st.subheader("📋 Ringkasan Performa Per Sales")
                st.markdown(table_responsive_html, unsafe_allow_html=True)

        st.markdown(
            "<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True
        )

        # 7. GRAFIK PENCAPAIAN SALES VS TARGET (SUMBU Y TANPA DESIMAL, TOOLTIP DENGAN DESIMAL)
        if "Sales_Name" in df.columns and not df.empty:
            df_t1 = (
                df.groupby(["Sales_Name", "Periode_Bulan"])["Target"]
                .max()
                .reset_index()
            )
            df_target_final = (
                df_t1.groupby("Sales_Name")["Target"].sum().reset_index()
            )

            df_sales_val = (
                df.groupby("Sales_Name")["Net_Sales_Amnt_Excl_Ppn"]
                .sum()
                .reset_index()
            )
            df_target = pd.merge(
                df_sales_val, df_target_final, on="Sales_Name", how="left"
            ).fillna(0)

            df_target = df_target.sort_values(
                by="Net_Sales_Amnt_Excl_Ppn", ascending=False
            )
            sales_order = df_target["Sales_Name"].tolist()

            # Konversi nilai ke dalam satuan Juta (M) untuk sumbu Y
            df_target["Target_in_M"] = df_target["Target"] / 1_000_000
            df_target["Sales_in_M"] = (
                df_target["Net_Sales_Amnt_Excl_Ppn"] / 1_000_000
            )

            df_melted = df_target.melt(
                id_vars="Sales_Name",
                value_vars=["Target_in_M", "Sales_in_M"],
                var_name="Kategori",
                value_name="Nominal_M",
            )
            df_melted["Kategori"] = df_melted["Kategori"].replace(
                {"Target_in_M": "Target", "Sales_in_M": "Net Sales"}
            )

            df_melted["Nominal_Asli"] = df_melted.apply(
                lambda row: (
                    df_target.loc[
                        df_target["Sales_Name"] == row["Sales_Name"], "Target"
                    ].values[0]
                    if row["Kategori"] == "Target"
                    else df_target.loc[
                        df_target["Sales_Name"] == row["Sales_Name"],
                        "Net_Sales_Amnt_Excl_Ppn",
                    ].values[0]
                ),
                axis=1,
            )
            df_melted["Formatted_Nominal"] = df_melted["Nominal_Asli"].apply(
                lambda x: format_id(x, 2)
            )

            fig_target = px.bar(
                df_melted,
                x="Sales_Name",
                y="Nominal_M",
                color="Kategori",
                barmode="group",
                category_orders={"Sales_Name": sales_order},
                labels={
                    "Nominal_M": "Nominal (Juta Rp)",
                    "Sales_Name": "Sales Name",
                    "Kategori": "Keterangan",
                },
                color_discrete_map={"Target": "#FF6B6B", "Net Sales": "#4D96FF"},
                template="plotly_white",
                text="Formatted_Nominal",
                custom_data=["Formatted_Nominal"],
            )

            fig_target.update_traces(
                texttemplate="Rp %{text}",
                textposition="outside",
                textangle=-90,
                hovertemplate="<b>%{x}</b><br>%{legendgroup}: Rp %{customdata[0]}<extra></extra>",
            )

            num_sales = len(sales_order)

            fig_target.update_layout(
                height=480,
                font=dict(family="sans-serif", size=11, color="#333333"),
                legend=dict(
                    orientation="h",
                    y=-0.25,
                    x=0.5,
                    xanchor="center",
                    bgcolor="rgba(255,255,255,0.8)",
                    bordercolor="rgba(0,0,0,0.1)",
                    borderwidth=1,
                ),
                margin=dict(l=20, r=20, t=40, b=80),
                xaxis=dict(
                    type="category",
                    tickangle=-35,
                    tickfont=dict(size=10),
                    showgrid=True,
                    gridcolor="rgba(0,0,0,0.15)",
                    gridwidth=1,
                    tickvals=[i - 0.5 for i in range(1, num_sales + 1)],
                    showline=True,
                    linewidth=1,
                    linecolor="lightgray",
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor="rgba(0,0,0,0.08)",
                    showline=True,
                    linewidth=1,
                    linecolor="lightgray",
                    tickformat=",.0f",
                    ticksuffix=" M",
                ),
            )

            with st.container(border=True):
                st.subheader("🎯 Pencapaian Sales vs Target (Mingguan)")
                st.plotly_chart(
                    fig_target,
                    use_container_width=True,
                    config={"displayModeBar": False},
                )

        # 8. 10 PRODUK TERATAS & 10 CUSTOMER TERTINGGI (SUMBU Y TANPA DESIMAL)
        c1, c2 = st.columns(2)

        with c1:
            item_col = (
                "KeyItem"
                if "KeyItem" in df.columns
                else (
                    "Item_Name_Vam" if "Item_Name_Vam" in df.columns else None
                )
            )

            if item_col:
                top_products = (
                    df.groupby(item_col)["Tot_Qty_Kg"].sum().reset_index()
                )
                top_products = top_products.sort_values(
                    by="Tot_Qty_Kg", ascending=False
                ).head(10)
                top_products["Formatted_Qty"] = top_products[
                    "Tot_Qty_Kg"
                ].apply(lambda x: format_id(x, 2))

                fig_prod = px.bar(
                    top_products,
                    x=item_col,
                    y="Tot_Qty_Kg",
                    labels={
                        item_col: "Nama Produk",
                        "Tot_Qty_Kg": "Total Qty (Kg)",
                    },
                    template="plotly_white",
                    color="Tot_Qty_Kg",
                    color_continuous_scale="Viridis",
                    text="Formatted_Qty",
                    custom_data=["Formatted_Qty"],
                )
                fig_prod.update_traces(
                    texttemplate="%{text} Kg",
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>Total Qty: %{customdata[0]} Kg<extra></extra>",
                )
                fig_prod.update_layout(
                    height=420,
                    bargap=0.3,
                    xaxis=dict(
                        tickangle=-45,
                        tickfont=dict(size=9),
                        showgrid=False,
                        showline=True,
                        linewidth=1,
                        linecolor="lightgray",
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor="rgba(0,0,0,0.08)",
                        showline=True,
                        linewidth=1,
                        linecolor="lightgray",
                        tickformat=",.0f",
                    ),
                    margin=dict(l=10, r=10, t=20, b=90),
                    coloraxis_showscale=False,
                )

                with st.container(border=True):
                    st.subheader("🔥 10 Produk Teratas (Best Seller)")
                    st.plotly_chart(
                        fig_prod,
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
            else:
                st.warning(
                    "Kolom produk ('KeyItem' atau 'Item_Name_Vam') tidak ditemukan."
                )

        with c2:
            if "Cust_Name" in df.columns:
                top_cust = (
                    df.groupby("Cust_Name")["Net_Sales_Amnt_Excl_Ppn"]
                    .sum()
                    .reset_index()
                )
                top_cust = top_cust.sort_values(
                    by="Net_Sales_Amnt_Excl_Ppn", ascending=False
                ).head(10)

                # Konversi nilai ke dalam satuan Juta (M) untuk sumbu Y
                top_cust["Sales_in_M"] = (
                    top_cust["Net_Sales_Amnt_Excl_Ppn"] / 1_000_000
                )
                top_cust["Formatted_Sales"] = top_cust[
                    "Net_Sales_Amnt_Excl_Ppn"
                ].apply(lambda x: format_id(x, 2))

                fig_cust = px.bar(
                    top_cust,
                    x="Cust_Name",
                    y="Sales_in_M",
                    labels={
                        "Cust_Name": "Customer Name",
                        "Sales_in_M": "Net Sales (Juta Rp)",
                    },
                    template="plotly_white",
                    color="Sales_in_M",
                    color_continuous_scale="Tealgrn",
                    text=top_cust["Net_Sales_Amnt_Excl_Ppn"].apply(
                        lambda x: format_id(x, 2)
                    ),
                    custom_data=["Formatted_Sales"],
                )
                fig_cust.update_traces(
                    texttemplate="Rp %{text}",
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>Net Sales: Rp %{customdata[0]}<extra></extra>",
                )
                fig_cust.update_layout(
                    height=420,
                    bargap=0.3,
                    xaxis=dict(
                        tickangle=-45,
                        tickfont=dict(size=9),
                        showgrid=False,
                        showline=True,
                        linewidth=1,
                        linecolor="lightgray",
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor="rgba(0,0,0,0.08)",
                        showline=True,
                        linewidth=1,
                        linecolor="lightgray",
                        tickformat=",.0f",
                        ticksuffix=" M",
                    ),
                    margin=dict(l=10, r=10, t=20, b=90),
                    coloraxis_showscale=False,
                )

                with st.container(border=True):
                    st.subheader("👑 10 Customer Pembelian Tertinggi")
                    st.plotly_chart(
                        fig_cust,
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
            else:
                st.warning("Kolom 'Cust_Name' tidak ditemukan.")

        # 9. TOTAL PENJUALAN PER CABANG
        if "Branch" in df.columns:
            df_branch = (
                df.groupby("Branch")["Net_Sales_Amnt_Excl_Ppn"]
                .sum()
                .reset_index()
            )
            df_branch = df_branch.sort_values(
                by="Net_Sales_Amnt_Excl_Ppn", ascending=False
            )
            df_branch["Formatted_Sales"] = df_branch[
                "Net_Sales_Amnt_Excl_Ppn"
            ].apply(lambda x: format_id(x, 2))

            fig_branch = px.pie(
                df_branch,
                names="Branch",
                values="Net_Sales_Amnt_Excl_Ppn",
                hole=0.45,
                labels={
                    "Branch": "Branch",
                    "Net_Sales_Amnt_Excl_Ppn": "Total Sales",
                },
                template="plotly_white",
                color_discrete_sequence=px.colors.qualitative.Prism,
                custom_data=["Formatted_Sales"],
            )
            fig_branch.update_traces(
                textinfo="text+percent",
                texttemplate="Rp %{customdata[0]}<br>(%{percent})",
                hovertemplate="<b>Cabang: %{label}</b><br>Total Sales: Rp %{customdata[0]}<br>Persentase: %{percent}<extra></extra>",
                marker=dict(line=dict(color="#ffffff", width=2)),
            )
            fig_branch.update_layout(
                margin=dict(l=20, r=20, t=10, b=30),
                legend=dict(
                    orientation="h",
                    y=-0.2,
                    x=0.5,
                    xanchor="center",
                    font=dict(size=10),
                ),
            )

            with st.container(border=True):
                st.subheader("🏢 Total Penjualan per Cabang")
                st.plotly_chart(
                    fig_branch,
                    use_container_width=True,
                    config={"displayModeBar": False},
                )
        else:
            st.warning("Kolom 'Branch' tidak ditemukan pada data.")