import io
import re
from decimal import Decimal

import pandas as pd
import plotly.express as px
import plotly.io as pio
import streamlit as st

from db import check_role_access, load_sales_report

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)

st.set_page_config(page_title="Sales Performance Dashboard", layout="wide")


# ============================================================
# CSS & HELPER
# ============================================================

def load_css(file_name):
    try:
        with open(file_name, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass


load_css("assets/style.css")

st.markdown("""
<style>
@media (max-width: 768px) {
    .block-container {
        padding-left: .8rem;
        padding-right: .8rem;
    }

    .js-plotly-plot,
    .plot-container {
        width: 100% !important;
        max-width: 100% !important;
    }

    /* Jangan biarkan area Plotly melebar keluar card di HP. */
    .js-plotly-plot .plotly,
    .js-plotly-plot .main-svg {
        max-width: 100% !important;
    }
}

/* =========================================================
   RESPONSIVE TABLE
   - Horizontal scroll on desktop/mobile
   - Sticky/frozen header while scrolling vertically
   - Sticky first column (No) while scrolling horizontally
   ========================================================= */

.custom-resp-table-wrapper {
    /* Desktop: tabel mengikuti penuh lebar container.
       Mobile: tabel boleh lebih lebar dan digeser horizontal. */
    width: 100%;
    max-width: 100%;
    max-height: 420px;
    overflow-x: auto;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    overscroll-behavior: contain;
    border: 1px solid #e6e6e6;
    border-radius: 8px;
    background: #ffffff;
    position: relative;
    box-sizing: border-box;

    /* Jangan sisakan ruang kosong di bawah tabel. */
    padding: 0;
    margin: 0;
}

/* Scrollbar */
.custom-resp-table-wrapper::-webkit-scrollbar {
    width: 7px;
    height: 7px;
}

.custom-resp-table-wrapper::-webkit-scrollbar-track {
    background: #f1f3f5;
    border-radius: 8px;
}

.custom-resp-table-wrapper::-webkit-scrollbar-thumb {
    background: #b8bec6;
    border-radius: 8px;
}

.custom-resp-table-wrapper::-webkit-scrollbar-thumb:hover {
    background: #9299a3;
}

/*
   RESPONSIVE WIDTH:
   - width: max-content membuat tabel boleh melebar mengikuti kolom.
   - min-width: 100% membuatnya tetap memenuhi card pada desktop.
   - Jika isi lebih lebar dari layar HP, wrapper akan horizontal scroll.
*/
.custom-resp-table {
    width: max-content;
    min-width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-family: sans-serif;
    font-size: 13px;
    background: #ffffff;
    margin: 0;
}

/* FREEZE HEADER */
.custom-resp-table thead th {
    position: sticky;
    top: 0;
    z-index: 20;
    background: #f8f9fa;
    color: #333333;
    font-weight: 600;
    padding: 10px 9px;
    border-bottom: 2px solid #dee2e6;
    border-right: 1px solid #eeeeee;
    white-space: nowrap;
    text-align: center;
    box-shadow: 0 2px 3px rgba(0, 0, 0, 0.06);
}

/* FREEZE KOLOM NO */
.custom-resp-table thead th:first-child {
    position: sticky;
    left: 0;
    z-index: 30;
    background: #f8f9fa;
}

/* FREEZE KOLOM NO PADA BODY */
.custom-resp-table tbody td:first-child {
    position: sticky;
    left: 0;
    z-index: 10;
    background: #ffffff;
    box-shadow: 2px 0 3px rgba(0, 0, 0, 0.04);
}

.custom-resp-table tbody td {
    padding: 9px;
    border-bottom: 1px solid #eeeeee;
    border-right: 1px solid #f0f0f0;
    color: #444444;
    white-space: nowrap;
    background: #ffffff;
}

/* Hilangkan garis bawah tambahan setelah row terakhir,
   supaya baris terakhir tidak terlihat "mengambang" jauh
   dari border wrapper. */
.custom-resp-table tbody tr:last-child td {
    border-bottom: 0;
}

.custom-resp-table tbody tr:hover td {
    background: #f8fafc;
}

.custom-resp-table tbody tr:hover td:first-child {
    background: #f8fafc;
}

/* Pastikan wrapper tidak membuat ruang kosong vertikal
   ketika isi tabel sebenarnya lebih pendek dari max-height. */
.custom-resp-table-wrapper:has(.custom-resp-table) {
    height: auto;
}

/* Mobile */
@media (max-width: 768px) {
    /* Grafik Sales vs Target: legenda horizontal di atas grafik. */
    div[data-testid="stPlotlyChart"] {
        max-width: 100%;
        overflow: hidden;
    }

    .custom-resp-table-wrapper {
        max-height: 380px;
        border-radius: 7px;
    }

    .custom-resp-table {
        /* Lebar mengikuti isi; horizontal scroll aktif jika
           jumlah kolom tidak muat di layar. */
        min-width: 760px;
        font-size: 12px;
    }

    .custom-resp-table thead th {
        padding: 9px 8px;
        font-size: 12px;
    }

    .custom-resp-table tbody td {
        padding: 8px;
        font-size: 12px;
    }
}
</style>
""", unsafe_allow_html=True)


def format_id(val, decimal=2):
    try:
        formatted = f"{float(val):,.{decimal}f}" if decimal else f"{float(val):,.0f}"
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return val


def clean_to_decimal(val):
    try:
        if pd.isna(val):
            return Decimal("0")
        s = str(val).replace("Rp", "").replace("(", "-").replace(")", "").replace(",", "")
        s = re.sub(r"[^0-9.\-]", "", s)
        return Decimal(s) if s and s != "-" else Decimal("0")
    except Exception:
        return Decimal("0")


def safe_margin(sales, cost):
    try:
        return (sales - cost) / sales * Decimal("100") if sales else Decimal("0")
    except Exception:
        return Decimal("0")


def chart_layout(fig, height=420, bottom=90, right=20):
    fig.update_layout(
        height=height,
        template="plotly_white",
        font=dict(family="sans-serif", size=11, color="#333333"),
        margin=dict(l=10, r=right, t=20, b=bottom),
    )
    return fig


# ============================================================
# PDF
# ============================================================

def create_pdf_table(df_sub, col_widths=None):
    data = [list(df_sub.columns)] + df_sub.astype(str).values.tolist()
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#374151")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 8),
        ("BOTTOMPADDING", (0,0), (-1,0), 4),
        ("GRID", (0,0), (-1,-1), .5, colors.HexColor("#e5e7eb")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1),
         [colors.white, colors.HexColor("#f9fafb")]),
        ("FONTSIZE", (0,1), (-1,-1), 7),
        ("ALIGN", (1,1), (-1,-1), "RIGHT"),
    ]))
    return table


def generate_full_pdf(summary_df, t_net_sales, t_cost, t_margin, c_label,
                      role, figures_dict, tables_dict, update_date):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
    )
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Heading1"], fontSize=15,
        textColor=colors.HexColor("#1f2937"), spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle", parent=styles["Normal"], fontSize=9,
        textColor=colors.HexColor("#6b7280"), spaceAfter=15
    )

    elements += [
        Paragraph("Sales Performance Dashboard Report", title_style),
        Paragraph(
            f"Role Akses: {role.upper()} | Last Update Data: {update_date}",
            subtitle_style
        ),
    ]

    metrics = [
        ["Metrik Utama", "Total Nilai (Rp)"],
        ["Net Sales Excl PPN", f"Rp {format_id(t_net_sales, 2)}"],
        [f"Total {c_label}", f"Rp {format_id(t_cost, 2)}"],
        [f"Net Margin {c_label}", f"Rp {format_id(t_margin, 2)}"],
    ]
    mt = Table(metrics, colWidths=[250, 302])
    mt.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#f3f4f6")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.HexColor("#111827")),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),9),
        ("ALIGN",(0,0),(0,-1),"LEFT"),
        ("ALIGN",(1,0),(1,-1),"RIGHT"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),6),
        ("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("GRID",(0,0),(-1,-1),.5,colors.HexColor("#d1d5db")),
    ]))
    elements += [mt, Spacer(1, 15)]

    if not summary_df.empty:
        elements += [
            Paragraph("Ringkasan Performa Per Sales", styles["Heading2"]),
            Spacer(1, 6)
        ]
        elements.append(create_pdf_table(summary_df))
        elements.append(Spacer(1, 15))

    for title, fig in figures_dict.items():
        if fig is None:
            continue
        try:
            img = pio.to_image(fig, format="png", width=700, height=350, scale=2)
            elements += [
                Paragraph(title, styles["Heading2"]),
                Spacer(1, 4),
                RLImage(io.BytesIO(img), width=480, height=240),
                Spacer(1, 8),
            ]
            if title in tables_dict and not tables_dict[title].empty:
                elements += [create_pdf_table(tables_dict[title]), Spacer(1, 15)]
        except Exception as e:
            print(f"Gagal memuat komponen {title}: {e}")

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


LAST_UPDATE_DATE = "14 September 2026"

# Pagination grafik Sales vs Target:
# 6 Sales per slide agar grafik tetap lega, terutama di mobile.
SALES_PER_SLIDE = 6
if "sales_target_slide" not in st.session_state:
    st.session_state.sales_target_slide = 0


# ============================================================
# LOAD & PREPROCESSING
# ============================================================

df = load_sales_report()

if df is not None and not df.empty:
    df.columns = df.columns.astype(str).str.strip()

    if "Sales_Name" in df.columns:
        df["Sales_Name"] = (
            df["Sales_Name"].fillna("UNCATEGORIZED")
            .astype(str).str.strip().str.upper()
        )

    df = check_role_access(df, sales_column_name="Sales_Name")

    if "Net_Sales_Amnt_Excl_Ppn" in df.columns:
        df["Net_Sales_Amnt_Excl_Ppn_Dec"] = (
            df["Net_Sales_Amnt_Excl_Ppn"].apply(clean_to_decimal)
        )
        df["Net_Sales_Amnt_Excl_Ppn"] = (
            df["Net_Sales_Amnt_Excl_Ppn_Dec"].astype(float)
        )
    else:
        df["Net_Sales_Amnt_Excl_Ppn_Dec"] = Decimal("0")
        df["Net_Sales_Amnt_Excl_Ppn"] = 0.0

    for col in ["Total_COGM", "Total_COGS"]:
        if col in df.columns:
            df[f"{col}_Dec"] = df[col].apply(clean_to_decimal)
            df[col] = df[f"{col}_Dec"].astype(float)
        else:
            df[f"{col}_Dec"] = Decimal("0")
            df[col] = 0.0

    for col in ["Tot_Qty_Kg", "Target"]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(r"[^0-9.\-]", "", regex=True),
                errors="coerce"
            ).fillna(0)
        else:
            df[col] = 0

    date_col = next(
        (c for c in ["Order_Date", "Date", "Tgl", "Tanggal", "Periode"]
         if c in df.columns), None
    )
    if date_col:
        clean_date = df[date_col].astype(str).str.replace(r"[^0-9]", "", regex=True)
        df["Periode_Bulan"] = clean_date.str[:4] + "-" + clean_date.str[4:6]
    else:
        df["Periode_Bulan"] = "Unknown"


user_role = str(st.session_state.get("role", "sales")).lower()

active_cost_col = (
    "Total_COGM" if user_role in ["admin", "direksi"] else "Total_COGS"
)
active_cost_dec_col = f"{active_cost_col}_Dec"
cost_label = "COGM" if user_role in ["admin", "direksi"] else "COGS"


# ============================================================
# HEADER + PDF EXPORT
# ============================================================

header_col1, header_col2 = st.columns([4, 1])

with header_col1:
    st.title("📊 Sales Performance Dashboard")
    st.caption(f"🕒 **Last Update Data:** {LAST_UPDATE_DATE}")

with header_col2:
    st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)

    if df is not None and not df.empty:
        df_t_bln = (
            df.groupby(["Sales_Name", "Periode_Bulan"])["Target"]
            .max().reset_index()
        )
        df_tot_tgt = (
            df_t_bln.groupby("Sales_Name")["Target"]
            .sum().reset_index()
        )

        df_s_agg = (
            df.groupby("Sales_Name")
            .agg({
                "Net_Sales_Amnt_Excl_Ppn_Dec":
                    lambda x: sum(x, Decimal("0")),
                "Total_COGM_Dec":
                    lambda x: sum(x, Decimal("0")),
                "Total_COGS_Dec":
                    lambda x: sum(x, Decimal("0")),
            }).reset_index()
        )

        df_sum_pdf = pd.merge(
            df_s_agg, df_tot_tgt, on="Sales_Name", how="left"
        ).fillna(0)

        df_sum_pdf = df_sum_pdf.sort_values(
            "Net_Sales_Amnt_Excl_Ppn_Dec", ascending=False
        )

        df_pdf_disp = pd.DataFrame({
            "Sales Name": df_sum_pdf["Sales_Name"],
            "Net Sales": df_sum_pdf["Net_Sales_Amnt_Excl_Ppn_Dec"].apply(
                lambda x: f"Rp {format_id(x, 2)}"
            ),
            "Gross Margin COGS": (
                df_sum_pdf["Net_Sales_Amnt_Excl_Ppn_Dec"]
                - df_sum_pdf["Total_COGS_Dec"]
            ).apply(lambda x: f"Rp {format_id(x, 2)}"),
        })

        if user_role in ["admin", "direksi"]:
            df_pdf_disp["Gross Margin COGM"] = (
                df_sum_pdf["Net_Sales_Amnt_Excl_Ppn_Dec"]
                - df_sum_pdf["Total_COGM_Dec"]
            ).apply(lambda x: f"Rp {format_id(x, 2)}")

        df_pdf_disp.index = range(1, len(df_pdf_disp) + 1)

        figures_to_export = {}
        tables_to_export = {}

        # PDF Target vs Sales - desain mengikuti kode Sales Per Minggu
        try:
            df_tg = pd.merge(
                df.groupby("Sales_Name")["Net_Sales_Amnt_Excl_Ppn"].sum().reset_index(),
                df.groupby(["Sales_Name", "Periode_Bulan"])["Target"]
                .max().reset_index()
                .groupby("Sales_Name")["Target"].sum().reset_index(),
                on="Sales_Name", how="left"
            ).fillna(0).sort_values(
                "Net_Sales_Amnt_Excl_Ppn", ascending=False
            )

            df_tg["Target_in_M"] = df_tg["Target"] / 1_000_000
            df_tg["Sales_in_M"] = df_tg["Net_Sales_Amnt_Excl_Ppn"] / 1_000_000

            df_ml = df_tg.melt(
                id_vars="Sales_Name",
                value_vars=["Target_in_M", "Sales_in_M"],
                var_name="Kategori", value_name="Nominal_M"
            )
            df_ml["Kategori"] = df_ml["Kategori"].replace({
                "Target_in_M": "Target", "Sales_in_M": "Net Sales"
            })
            df_ml["Nominal_Asli"] = df_ml.apply(
                lambda r: df_tg.loc[
                    df_tg["Sales_Name"] == r["Sales_Name"],
                    "Target" if r["Kategori"] == "Target"
                    else "Net_Sales_Amnt_Excl_Ppn"
                ].values[0], axis=1
            )
            df_ml["Formatted_Nominal"] = df_ml["Nominal_Asli"].apply(
                lambda x: format_id(x, 2)
            )

            fig_t = px.bar(
                df_ml, x="Sales_Name", y="Nominal_M", color="Kategori",
                barmode="group",
                category_orders={"Sales_Name": df_tg["Sales_Name"].tolist()},
                labels={
                    "Nominal_M": "Nominal (Rp)",
                    "Sales_Name": "Sales Name",
                    "Kategori": "Keterangan",
                },
                color_discrete_map={
                    "Target": "#FF6B6B", "Net Sales": "#4D96FF"
                },
                template="plotly_white",
                text="Formatted_Nominal",
                custom_data=["Formatted_Nominal"]
            )
            fig_t.update_traces(
                texttemplate="Rp %{text}", textposition="outside",
                textangle=-90, cliponaxis=False,
                hovertemplate=(
                    "<b>%{x}</b><br>%{legendgroup}: Rp "
                    "%{customdata[0]}<extra></extra>"
                )
            )
            chart_layout(fig_t, 480, 80)
            fig_t.update_layout(
                legend=dict(
                    orientation="h", y=-.25, x=.5, xanchor="center",
                    bgcolor="rgba(255,255,255,.8)",
                    bordercolor="rgba(0,0,0,.1)", borderwidth=1
                ),
                xaxis=dict(
                    type="category", tickangle=-35, tickfont=dict(size=10),
                    showgrid=True, gridcolor="rgba(0,0,0,.15)",
                    showline=True, linecolor="lightgray"
                ),
                yaxis=dict(
                    showgrid=True, gridcolor="rgba(0,0,0,.08)",
                    showline=True, linecolor="lightgray",
                    tickformat=",.0f", ticksuffix=" M"
                )
            )

            key = "🎯 Pencapaian Sales vs Target (Per Bulan)"
            figures_to_export[key] = fig_t
            tables_to_export[key] = pd.DataFrame({
                "Sales Name": df_tg["Sales_Name"],
                "Target (Rp)": df_tg["Target"].apply(
                    lambda x: f"Rp {format_id(x, 2)}"
                ),
                "Net Sales (Rp)": df_tg["Net_Sales_Amnt_Excl_Ppn"].apply(
                    lambda x: f"Rp {format_id(x, 2)}"
                )
            })
        except Exception:
            pass

        # PDF Produk
        try:
            item_col = next(
                (c for c in ["KeyItem", "Item_Name_Vam"] if c in df.columns),
                None
            )
            if item_col:
                top_p = (
                    df.groupby(item_col)["Tot_Qty_Kg"].sum().reset_index()
                    .sort_values("Tot_Qty_Kg", ascending=False).head(10)
                )
                top_p[item_col] = (
                    top_p[item_col].fillna("UNKNOWN").astype(str).str.strip()
                )
                top_p = top_p[
                    (top_p[item_col] != "") &
                    (top_p[item_col].str.lower() != "nan")
                ]
                top_p["Formatted_Qty"] = top_p["Tot_Qty_Kg"].apply(
                    lambda x: format_id(x, 2)
                )

                fig_p = px.bar(
                    top_p, x=item_col, y="Tot_Qty_Kg",
                    template="plotly_white",
                    color="Tot_Qty_Kg",
                    color_continuous_scale="Viridis",
                    text="Formatted_Qty",
                    custom_data=["Formatted_Qty"]
                )
                fig_p.update_traces(
                    texttemplate="%{text} Kg", textposition="outside",
                    cliponaxis=False,
                    hovertemplate=(
                        "<b>%{x}</b><br>Total Qty: "
                        "%{customdata[0]} Kg<extra></extra>"
                    )
                )
                chart_layout(fig_p, 420, 90)
                fig_p.update_layout(
                    bargap=.3,
                    xaxis=dict(tickangle=-45, tickfont=dict(size=9),
                               showgrid=False, showline=True,
                               linecolor="lightgray"),
                    yaxis=dict(showgrid=True,
                               gridcolor="rgba(0,0,0,.08)",
                               showline=True, linecolor="lightgray",
                               tickformat=",.0f"),
                    coloraxis_showscale=False
                )
                key = "🔥 10 Produk Teratas (Best Seller)"
                figures_to_export[key] = fig_p
                tables_to_export[key] = pd.DataFrame({
                    "Nama Produk": top_p[item_col].values,
                    "Total Qty (Kg)": top_p["Tot_Qty_Kg"].apply(
                        lambda x: format_id(x, 2)
                    ).values
                })
        except Exception:
            pass

        # PDF Customer
        try:
            if "Cust_Name" in df.columns:
                top_c = (
                    df.groupby("Cust_Name")["Net_Sales_Amnt_Excl_Ppn"]
                    .sum().reset_index()
                    .sort_values("Net_Sales_Amnt_Excl_Ppn", ascending=False)
                    .head(10)
                )
                top_c["Cust_Name"] = (
                    top_c["Cust_Name"].fillna("UNKNOWN CUST")
                    .astype(str).str.strip()
                )
                top_c = top_c[
                    (top_c["Cust_Name"] != "") &
                    (top_c["Cust_Name"].str.lower() != "nan")
                ]
                top_c["Sales_in_M"] = (
                    top_c["Net_Sales_Amnt_Excl_Ppn"] / 1_000_000
                )
                top_c["Formatted_Sales"] = top_c[
                    "Net_Sales_Amnt_Excl_Ppn"
                ].apply(lambda x: format_id(x, 2))

                fig_c = px.bar(
                    top_c.sort_values(
                        "Net_Sales_Amnt_Excl_Ppn", ascending=True
                    ),
                    x="Sales_in_M", y="Cust_Name", orientation="h",
                    template="plotly_white", color="Sales_in_M",
                    color_continuous_scale="Tealgrn",
                    text="Formatted_Sales",
                    custom_data=["Formatted_Sales"]
                )
                fig_c.update_traces(
                    texttemplate="Rp %{text}", textposition="outside",
                    cliponaxis=False,
                    hovertemplate=(
                        "<b>%{y}</b><br>Net Sales: Rp "
                        "%{customdata[0]}<extra></extra>"
                    )
                )
                chart_layout(fig_c, 420, 35, 70)
                fig_c.update_layout(
                    bargap=.3,
                    xaxis=dict(showgrid=True,
                               gridcolor="rgba(0,0,0,.08)",
                               showline=True, linecolor="lightgray",
                               tickformat=",.0f", ticksuffix=" M"),
                    yaxis=dict(categoryorder="total ascending",
                               tickfont=dict(size=9), showgrid=False,
                               showline=True, linecolor="lightgray"),
                    coloraxis_showscale=False
                )
                key = "👑 10 Customer Pembelian Tertinggi"
                figures_to_export[key] = fig_c
                tables_to_export[key] = pd.DataFrame({
                    "Customer Name": top_c["Cust_Name"].values,
                    "Net Sales (Rp)": top_c["Net_Sales_Amnt_Excl_Ppn"].apply(
                        lambda x: f"Rp {format_id(x, 2)}"
                    ).values
                })
        except Exception:
            pass

        # PDF Branch
        try:
            if "Branch" in df.columns:
                df_b = (
                    df.groupby("Branch")["Net_Sales_Amnt_Excl_Ppn"]
                    .sum().reset_index()
                    .sort_values("Net_Sales_Amnt_Excl_Ppn", ascending=False)
                )
                df_b["Branch"] = (
                    df_b["Branch"].fillna("UNCATEGORIZED").astype(str)
                )
                df_b["Formatted_Sales"] = df_b[
                    "Net_Sales_Amnt_Excl_Ppn"
                ].apply(lambda x: format_id(x, 2))

                fig_b = px.pie(
                    df_b, names="Branch",
                    values="Net_Sales_Amnt_Excl_Ppn",
                    hole=.50, template="plotly_white",
                    color_discrete_sequence=px.colors.qualitative.Prism,
                    custom_data=["Formatted_Sales"]
                )
                fig_b.update_traces(
                    textinfo="text+percent",
                    texttemplate="Rp %{customdata[0]}<br>(%{percent})",
                    marker=dict(line=dict(color="#ffffff", width=2)),
                    hovertemplate=(
                        "<b>Cabang: %{label}</b><br>"
                        "Net Sales: Rp %{customdata[0]}<br>"
                        "Persentase: %{percent}<extra></extra>"
                    )
                )
                fig_b.update_layout(
                    height=440, margin=dict(l=20,r=20,t=20,b=100),
                    legend=dict(
                        orientation="h", y=-.18, x=.5, xanchor="center",
                        font=dict(size=10)
                    )
                )
                key = "🏢 Total Penjualan per Cabang"
                figures_to_export[key] = fig_b
                tables_to_export[key] = pd.DataFrame({
                    "Branch": df_b["Branch"].values,
                    "Net Sales (Rp)": df_b["Net_Sales_Amnt_Excl_Ppn"].apply(
                        lambda x: f"Rp {format_id(x, 2)}"
                    ).values
                })
        except Exception:
            pass

        pdf_data = generate_full_pdf(
            df_pdf_disp,
            sum(df["Net_Sales_Amnt_Excl_Ppn_Dec"], Decimal("0")),
            sum(df[active_cost_dec_col], Decimal("0")),
            sum(df["Net_Sales_Amnt_Excl_Ppn_Dec"], Decimal("0"))
            - sum(df[active_cost_dec_col], Decimal("0")),
            cost_label, user_role, figures_to_export,
            tables_to_export, LAST_UPDATE_DATE
        )

        st.download_button(
            "📥 Export PDF", pdf_data,
            "full_sales_dashboard_report.pdf",
            "application/pdf", use_container_width=True
        )


# ============================================================
# BODY DASHBOARD
# ============================================================

st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)

if df is None or df.empty:
    st.error("Data tidak ditemukan atau kosong.")
else:
    with st.expander("🔍 Filter Data Dashboard", expanded=False):
        f1, f2 = st.columns(2)

        if "Branch" in df.columns:
            with f1:
                sel_b = st.multiselect(
                    "Filter Branch:",
                    sorted(df["Branch"].dropna().astype(str).unique()),
                    placeholder="Pilih Cabang..."
                )
            if sel_b:
                df = df[df["Branch"].isin(sel_b)]

        if "Sales_Name" in df.columns and user_role in ["admin", "direksi"]:
            with f2:
                sel_s = st.multiselect(
                    "Filter Sales Name:",
                    sorted(df["Sales_Name"].dropna().unique()),
                    placeholder="Pilih Sales..."
                )
            if sel_s:
                df = df[df["Sales_Name"].isin(sel_s)]

        f3, f4 = st.columns(2)

        if "Cust_Name" in df.columns:
            with f3:
                sel_c = st.multiselect(
                    "Filter Customer:",
                    sorted(df["Cust_Name"].dropna().astype(str).unique()),
                    placeholder="Pilih Customer..."
                )
            if sel_c:
                df = df[df["Cust_Name"].isin(sel_c)]

        if "Periode_Bulan" in df.columns:
            with f4:
                sel_p = st.multiselect(
                    "Filter Periode:",
                    sorted(df["Periode_Bulan"].dropna().unique(), reverse=True),
                    placeholder="Pilih Periode..."
                )
            if sel_p:
                df = df[df["Periode_Bulan"].isin(sel_p)]

    st.caption(
        f"ℹ️ Total baris data dimuat: **{format_id(len(df), 0)} baris**"
    )

    ns_dec = sum(
        df["Net_Sales_Amnt_Excl_Ppn_Dec"], Decimal("0")
    )
    cost_dec = sum(
        df[active_cost_dec_col], Decimal("0")
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("💰 Net Sales Excl PPN", f"Rp {format_id(ns_dec, 2)}")
    m2.metric(f"📦 Total {cost_label}", f"Rp {format_id(cost_dec, 2)}")
    m3.metric(
        f"📈 Net Margin {cost_label}",
        f"Rp {format_id(ns_dec - cost_dec, 2)}"
    )

    st.markdown(
        "<div style='margin-bottom:10px;'></div>",
        unsafe_allow_html=True
    )

    # ========================================================
    # TABEL RINGKASAN
    # ========================================================

    if "Sales_Name" in df.columns and not df.empty:
        df_tb_bln = (
            df.groupby(["Sales_Name", "Periode_Bulan"])["Target"]
            .max().reset_index()
        )
        df_tb_tgt = (
            df_tb_bln.groupby("Sales_Name")["Target"]
            .sum().reset_index()
        )
        df_tb_agg = (
            df.groupby("Sales_Name")
            .agg({
                "Net_Sales_Amnt_Excl_Ppn_Dec":
                    lambda x: sum(x, Decimal("0")),
                "Total_COGM_Dec":
                    lambda x: sum(x, Decimal("0")),
                "Total_COGS_Dec":
                    lambda x: sum(x, Decimal("0")),
            }).reset_index()
        )

        df_sum_web = pd.merge(
            df_tb_agg, df_tb_tgt, on="Sales_Name", how="left"
        ).fillna(0).sort_values(
            "Net_Sales_Amnt_Excl_Ppn_Dec", ascending=False
        )

        rows = []
        for idx, (_, r) in enumerate(df_sum_web.iterrows(), 1):
            sales = str(r["Sales_Name"])
            net = f"Rp {format_id(r['Net_Sales_Amnt_Excl_Ppn_Dec'], 2)}"
            extra = ""

            if user_role in ["admin", "direksi"]:
                gm = r["Net_Sales_Amnt_Excl_Ppn_Dec"] - r["Total_COGM_Dec"]
                nm = safe_margin(
                    r["Net_Sales_Amnt_Excl_Ppn_Dec"], r["Total_COGM_Dec"]
                )
                extra += (
                    f"<td style='text-align:right'>Rp {format_id(gm,2)}</td>"
                    f"<td style='text-align:center'>{format_id(nm,2)}%</td>"
                )

            gm = r["Net_Sales_Amnt_Excl_Ppn_Dec"] - r["Total_COGS_Dec"]
            nm = safe_margin(
                r["Net_Sales_Amnt_Excl_Ppn_Dec"], r["Total_COGS_Dec"]
            )
            extra += (
                f"<td style='text-align:right'>Rp {format_id(gm,2)}</td>"
                f"<td style='text-align:center'>{format_id(nm,2)}%</td>"
            )

            rows.append(
                f"<tr><td style='text-align:center'>{idx}</td>"
                f"<td style='text-align:left'>{sales}</td>"
                f"<td style='text-align:right'>{net}</td>{extra}</tr>"
            )

        header_extra = (
            "<th>Gross Margin COGM</th><th>Net Margin COGM (%)</th>"
            "<th>Gross Margin COGS</th><th>Net Margin COGS (%)</th>"
            if user_role in ["admin", "direksi"]
            else "<th>Gross Margin COGS</th><th>Net Margin COGS (%)</th>"
        )

        table_html = f"""
        <div class="custom-resp-table-wrapper" title="Geser horizontal untuk melihat kolom lainnya">
            <table class="custom-resp-table" role="table">
                <thead>
                    <tr>
                        <th style="width:50px">No</th>
                        <th style="text-align:left">Sales Name</th>
                        <th style="text-align:right">Net Sales Excl Ppn</th>
                        {header_extra}
                    </tr>
                </thead>
                <tbody>{''.join(rows)}</tbody>
            </table>
        </div>
        """

        with st.container(border=True):
            st.subheader("📋 Ringkasan Performa Per Sales")
            st.markdown(table_html, unsafe_allow_html=True)

    st.markdown(
        "<div style='margin-bottom:10px;'></div>",
        unsafe_allow_html=True
    )

    # ========================================================
    # TARGET VS SALES — PAGINATION 6 SALES PER SLIDE
    # ========================================================

    if "Sales_Name" in df.columns and not df.empty:
        # Target dihitung per Sales + Periode, kemudian dijumlahkan.
        df_t1 = (
            df.groupby(["Sales_Name", "Periode_Bulan"])["Target"]
            .max()
            .reset_index()
        )

        df_target_final = (
            df_t1.groupby("Sales_Name")["Target"]
            .sum()
            .reset_index()
        )

        df_sales_val = (
            df.groupby("Sales_Name")["Net_Sales_Amnt_Excl_Ppn"]
            .sum()
            .reset_index()
        )

        df_target = pd.merge(
            df_sales_val,
            df_target_final,
            on="Sales_Name",
            how="left"
        ).fillna(0)

        # Ranking tetap berdasarkan Net Sales tertinggi.
        df_target = df_target.sort_values(
            "Net_Sales_Amnt_Excl_Ppn",
            ascending=False
        ).reset_index(drop=True)

        total_sales = len(df_target)
        total_slides = max(
            1,
            (total_sales + SALES_PER_SLIDE - 1) // SALES_PER_SLIDE
        )

        # Jika filter mengurangi jumlah Sales, pastikan slide tidak
        # berada di halaman yang sudah tidak tersedia.
        st.session_state.sales_target_slide = min(
            st.session_state.sales_target_slide,
            total_slides - 1
        )

        current_slide = st.session_state.sales_target_slide

        start_idx = current_slide * SALES_PER_SLIDE
        end_idx = min(start_idx + SALES_PER_SLIDE, total_sales)

        df_slide = df_target.iloc[start_idx:end_idx].copy()

        sales_order = df_slide["Sales_Name"].tolist()

        df_slide["Target_in_M"] = df_slide["Target"] / 1_000_000
        df_slide["Sales_in_M"] = (
            df_slide["Net_Sales_Amnt_Excl_Ppn"] / 1_000_000
        )

        df_melted = df_slide.melt(
            id_vars="Sales_Name",
            value_vars=["Target_in_M", "Sales_in_M"],
            var_name="Kategori",
            value_name="Nominal_M"
        )

        df_melted["Kategori"] = df_melted["Kategori"].replace({
            "Target_in_M": "Target",
            "Sales_in_M": "Net Sales"
        })

        # Nilai asli digunakan untuk label dan tooltip.
        target_lookup = df_slide.set_index("Sales_Name")["Target"].to_dict()
        sales_lookup = df_slide.set_index(
            "Sales_Name"
        )["Net_Sales_Amnt_Excl_Ppn"].to_dict()

        df_melted["Nominal_Asli"] = df_melted.apply(
            lambda r: (
                target_lookup.get(r["Sales_Name"], 0)
                if r["Kategori"] == "Target"
                else sales_lookup.get(r["Sales_Name"], 0)
            ),
            axis=1
        )

        df_melted["Formatted_Nominal"] = df_melted[
            "Nominal_Asli"
        ].apply(lambda x: format_id(x, 2))

        fig_target = px.bar(
            df_melted,
            x="Sales_Name",
            y="Nominal_M",
            color="Kategori",
            barmode="group",
            category_orders={"Sales_Name": sales_order},
            labels={
                "Nominal_M": "Nominal (Rp)",
                "Sales_Name": "Sales Name",
                "Kategori": "Keterangan"
            },
            color_discrete_map={
                "Target": "#FF6B6B",
                "Net Sales": "#4D96FF"
            },
            template="plotly_white",
            text="Formatted_Nominal",
            custom_data=["Formatted_Nominal"]
        )

        fig_target.update_traces(
            texttemplate="Rp %{text}",
            textposition="outside",
            textangle=-90,
            cliponaxis=False,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "%{legendgroup}: Rp %{customdata[0]}"
                "<extra></extra>"
            )
        )

        chart_layout(
            fig_target,
            height=430,
            bottom=80,
            right=20
        )

        fig_target.update_layout(
            legend=dict(
                orientation="h",
                y=1.08,
                x=0.5,
                xanchor="center",
                yanchor="bottom",
                bgcolor="rgba(255,255,255,.92)",
                bordercolor="rgba(0,0,0,.08)",
                borderwidth=1,
                font=dict(size=10),
                traceorder="normal"
            ),
            xaxis=dict(
                type="category",
                tickangle=-25,
                tickfont=dict(size=10),
                # Grid bawaan X dimatikan. Batas antar Sales dibuat
                # manual di posisi DI ANTARA kelompok batang.
                showgrid=False,
                showline=True,
                linecolor="lightgray",
                fixedrange=True
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor="rgba(0,0,0,.08)",
                showline=False,
                tickformat=",.0f",
                ticksuffix=" M",
                fixedrange=True
            ),
            bargap=0.30,
            bargroupgap=0.08
        )

        # ====================================================
        # BATAS VERTIKAL ANTAR SALES
        # ====================================================
        # Garis ditempatkan di antara Sales ke-1 & ke-2,
        # ke-2 & ke-3, dst. Jadi setiap Sales mempunyai
        # "area" visual sendiri, sesuai contoh yang diminta.
        if len(sales_order) > 1:
            separator_shapes = []

            for i in range(len(sales_order) - 1):
                separator_shapes.append(
                    dict(
                        type="line",
                        xref="x",
                        yref="paper",
                        x0=i + 0.5,
                        x1=i + 0.5,
                        y0=0,
                        y1=1,
                        line=dict(
                            color="rgba(120,120,120,0.28)",
                            width=1,
                            dash="solid"
                        ),
                        layer="below"
                    )
                )

            fig_target.update_layout(
                shapes=separator_shapes
            )

        # ====================================================
        # CARD GRAFIK
        # Border mengelilingi seluruh area grafik, seperti pada
        # desain "Pencapaian Sales vs Target (Mingguan)".
        # ====================================================

        with st.container(border=True):
            title_col, info_col = st.columns([4, 2])

            with title_col:
                st.subheader(
                    "🎯 Pencapaian Sales vs Target (Per Bulan)"
                )

            with info_col:
                st.markdown(
                    f"<div style='text-align:right; "
                    f"padding-top:8px; color:#6b7280; font-size:13px;'>"
                    f"Menampilkan <b>{start_idx + 1}–{end_idx}</b> "
                    f"dari <b>{total_sales}</b> Sales"
                    f"</div>",
                    unsafe_allow_html=True
                )

            st.plotly_chart(
                fig_target,
                use_container_width=True,
                config={
                    "displayModeBar": False,
                    "responsive": True
                }
            )

            # Kontrol pagination diletakkan DI BAWAH grafik,
            # bukan menjadi bagian dari border/card.
            nav_left, nav_mid, nav_right = st.columns(
                [1.2, 2, 1.2]
            )

            with nav_left:
                if st.button(
                    "← Sebelumnya",
                    key="sales_target_prev",
                    use_container_width=True,
                    disabled=(current_slide == 0)
                ):
                    st.session_state.sales_target_slide -= 1
                    st.rerun()

            with nav_mid:
                st.markdown(
                    f"<div style='text-align:center; "
                    f"padding-top:7px; font-weight:600; "
                    f"color:#374151;'>"
                    f"Slide {current_slide + 1} / {total_slides}"
                    f"</div>",
                    unsafe_allow_html=True
                )

            with nav_right:
                if st.button(
                    "Berikutnya →",
                    key="sales_target_next",
                    use_container_width=True,
                    disabled=(current_slide >= total_slides - 1)
                ):
                    st.session_state.sales_target_slide += 1
                    st.rerun()

            # Indicator kecil agar user langsung tahu posisi.
            if total_slides > 1:
                dots = []
                for i in range(total_slides):
                    if i == current_slide:
                        dots.append("●")
                    else:
                        dots.append("○")

                st.markdown(
                    f"<div style='text-align:center; "
                    f"margin-top:4px; color:#6b7280; "
                    f"font-size:12px; letter-spacing:3px;'>"
                    f"{' '.join(dots)}"
                    f"</div>",
                    unsafe_allow_html=True
                )


    # ========================================================
    # PRODUK & CUSTOMER
    # ========================================================

    col_prod, col_cust = st.columns(2)

    with col_prod:
        item_col = next(
            (c for c in ["KeyItem", "Item_Name_Vam"] if c in df.columns),
            None
        )

        if item_col:
            tp = (
                df.groupby(item_col)["Tot_Qty_Kg"].sum().reset_index()
                .sort_values("Tot_Qty_Kg", ascending=False).head(10)
            )
            tp[item_col] = (
                tp[item_col].fillna("UNKNOWN").astype(str).str.strip()
            )
            tp = tp[
                (tp[item_col] != "") &
                (tp[item_col].str.lower() != "nan")
            ]
            tp["Formatted_Qty"] = tp["Tot_Qty_Kg"].apply(
                lambda x: format_id(x, 2)
            )

            fig_p = px.bar(
                tp, x=item_col, y="Tot_Qty_Kg",
                labels={
                    item_col: "Nama Produk",
                    "Tot_Qty_Kg": "Total Qty (Kg)"
                },
                template="plotly_white",
                color="Tot_Qty_Kg",
                color_continuous_scale="Viridis",
                text="Formatted_Qty",
                custom_data=["Formatted_Qty"]
            )
            fig_p.update_traces(
                texttemplate="%{text} Kg",
                textposition="outside",
                cliponaxis=False,
                hovertemplate=(
                    "<b>%{x}</b><br>Total Qty: "
                    "%{customdata[0]} Kg<extra></extra>"
                )
            )
            chart_layout(fig_p, 420, 90)
            fig_p.update_layout(
                bargap=.3,
                xaxis=dict(
                    tickangle=-45, tickfont=dict(size=9),
                    showgrid=False, showline=True,
                    linecolor="lightgray"
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor="rgba(0,0,0,.08)",
                    showline=True, linecolor="lightgray",
                    tickformat=",.0f"
                ),
                coloraxis_showscale=False
            )

            with st.container(border=True):
                st.subheader("🔥 10 Produk Teratas (Best Seller)")
                st.plotly_chart(
                    fig_p, use_container_width=True,
                    config={"displayModeBar": False}
                )
        else:
            st.warning(
                "Kolom produk ('KeyItem' atau 'Item_Name_Vam') tidak ditemukan."
            )

    with col_cust:
        if "Cust_Name" in df.columns:
            tc = (
                df.groupby("Cust_Name")["Net_Sales_Amnt_Excl_Ppn"]
                .sum().reset_index()
                .sort_values(
                    "Net_Sales_Amnt_Excl_Ppn", ascending=False
                ).head(10)
            )
            tc["Cust_Name"] = (
                tc["Cust_Name"].fillna("UNKNOWN CUST")
                .astype(str).str.strip()
            )
            tc = tc[
                (tc["Cust_Name"] != "") &
                (tc["Cust_Name"].str.lower() != "nan")
            ]
            tc["Sales_in_M"] = (
                tc["Net_Sales_Amnt_Excl_Ppn"] / 1_000_000
            )
            tc["Formatted_Sales"] = tc[
                "Net_Sales_Amnt_Excl_Ppn"
            ].apply(lambda x: format_id(x, 2))
            tc = tc.sort_values(
                "Net_Sales_Amnt_Excl_Ppn", ascending=True
            )

            # Customer diletakkan pada sumbu X agar lebih nyaman
            # dibaca di layar mobile.
            tc = tc.sort_values(
                "Net_Sales_Amnt_Excl_Ppn", ascending=False
            ).reset_index(drop=True)

            fig_c = px.bar(
                tc,
                x="Cust_Name",
                y="Sales_in_M",
                labels={
                    "Cust_Name": "Customer Name",
                    "Sales_in_M": "Net Sales (Rp)"
                },
                template="plotly_white",
                color="Sales_in_M",
                color_continuous_scale="Tealgrn",
                text="Formatted_Sales",
                custom_data=["Formatted_Sales"]
            )

            fig_c.update_traces(
                texttemplate="Rp %{text}",
                textposition="outside",
                cliponaxis=False,
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Net Sales: Rp %{customdata[0]}"
                    "<extra></extra>"
                )
            )

            chart_layout(fig_c, 420, 95, 20)

            fig_c.update_layout(
                bargap=.28,
                xaxis=dict(
                    type="category",
                    tickangle=-38,
                    tickfont=dict(size=8),
                    showgrid=False,
                    showline=True,
                    linecolor="lightgray",
                    automargin=True
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor="rgba(0,0,0,.08)",
                    showline=True,
                    linecolor="lightgray",
                    tickformat=",.0f",
                    ticksuffix=" M",
                    automargin=True
                ),
                coloraxis_showscale=False
            )

            with st.container(border=True):
                st.subheader("👑 10 Customer Pembelian Tertinggi")
                st.plotly_chart(
                    fig_c, use_container_width=True,
                    config={"displayModeBar": False}
                )
        else:
            st.warning("Kolom 'Cust_Name' tidak ditemukan.")

    # ========================================================
    # DONUT BRANCH
    # ========================================================

    if "Branch" in df.columns:
        df_b = (
            df.groupby("Branch")["Net_Sales_Amnt_Excl_Ppn"]
            .sum().reset_index()
            .sort_values(
                "Net_Sales_Amnt_Excl_Ppn", ascending=False
            )
        )
        df_b["Branch"] = (
            df_b["Branch"].fillna("UNCATEGORIZED")
            .astype(str).str.strip()
        )
        df_b["Formatted_Sales"] = df_b[
            "Net_Sales_Amnt_Excl_Ppn"
        ].apply(lambda x: format_id(x, 2))

        fig_b = px.pie(
            df_b,
            names="Branch",
            values="Net_Sales_Amnt_Excl_Ppn",
            hole=.50,
            labels={
                "Branch": "Branch",
                "Net_Sales_Amnt_Excl_Ppn": "Total Sales"
            },
            template="plotly_white",
            color_discrete_sequence=px.colors.qualitative.Prism,
            custom_data=["Formatted_Sales"]
        )
        fig_b.update_traces(
            textinfo="text+percent",
            texttemplate="Rp %{customdata[0]}<br>(%{percent})",
            marker=dict(line=dict(color="#ffffff", width=2)),
            hovertemplate=(
                "<b>Cabang: %{label}</b><br>"
                "Net Sales: Rp %{customdata[0]}<br>"
                "Persentase: %{percent}<extra></extra>"
            )
        )
        fig_b.update_layout(
            height=440,
            margin=dict(l=20, r=20, t=20, b=100),
            legend=dict(
                orientation="h", y=-.18, x=.5, xanchor="center",
                font=dict(size=10)
            )
        )

        with st.container(border=True):
            st.subheader("🏢 Total Penjualan per Cabang")
            st.plotly_chart(
                fig_b, use_container_width=True,
                config={"displayModeBar": False}
            )
    else:
        st.warning("Kolom 'Branch' tidak ditemukan pada data.")
