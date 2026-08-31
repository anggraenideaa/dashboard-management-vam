import io
import re
from decimal import Decimal
import pandas as pd
import plotly.express as px
import plotly.io as pio
import streamlit as st

# Database / modul kustom Anda
from db import check_role_access, load_sales_report

# Library untuk ReportLab (Export PDF)
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

st.set_page_config(page_title="Sales Performance Dashboard", layout="wide")


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
        return (
            formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        )
    except Exception:
        return val


LAST_UPDATE_DATE = "31 Agustus 2026"


def clean_to_decimal(val):
    try:
        if pd.isna(val):
            return Decimal("0")
        s = (
            str(val)
            .replace("Rp", "")
            .replace("(", "-")
            .replace(")", "")
            .replace(",", "")
        )
        s = re.sub(r"[^0-9.\-]", "", s)
        return Decimal(s) if s and s != "-" else Decimal("0")
    except Exception:
        return Decimal("0")


# --- HELPER FUNCTION UNTUK MEMBUAT TABEL PDF ---
def create_pdf_table(df_sub, col_widths=None):
    table_data = [list(df_sub.columns)] + df_sub.astype(str).values.tolist()
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#374151")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f9fafb")],
                ),
                ("FONTSIZE", (0, 1), (-1, -1), 7),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    return t


# --- FUNGSI UTAMA GENERATE PDF ---
def generate_full_pdf(
    summary_df,
    t_net_sales,
    t_cost,
    t_margin,
    c_label,
    role,
    figures_dict,
    tables_dict,
    update_date,
):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=15,
        textColor=colors.HexColor("#1f2937"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#6b7280"),
        spaceAfter=15,
    )

    elements.append(
        Paragraph("Sales Performance Dashboard Report", title_style)
    )
    elements.append(
        Paragraph(
            f"Role Akses: {role.upper()} | Last Update Data: {update_date}",
            subtitle_style,
        )
    )

    # Metrik Utama
    metrics_data = [
        ["Metrik Utama", "Total Nilai (Rp)"],
        ["Net Sales Excl PPN", f"Rp {format_id(t_net_sales, 2)}"],
        [f"Total {c_label}", f"Rp {format_id(t_cost, 2)}"],
        [f"Net Margin {c_label}", f"Rp {format_id(t_margin, 2)}"],
    ]
    t_metrics = Table(metrics_data, colWidths=[250, 302])
    t_metrics.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ]
        )
    )
    elements.append(t_metrics)
    elements.append(Spacer(1, 15))

    # Ringkasan Per Sales
    if not summary_df.empty:
        elements.append(
            Paragraph("Ringkasan Performa Per Sales", styles["Heading2"])
        )
        elements.append(Spacer(1, 6))
        table_data = [list(summary_df.columns)] + summary_df.astype(
            str
        ).values.tolist()
        t_summary = Table(table_data, repeatRows=1)
        t_summary.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        colors.HexColor("#e5e7eb"),
                    ),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f9fafb")],
                    ),
                    ("FONTSIZE", (0, 1), (-1, -1), 7),
                ]
            )
        )
        elements.append(t_summary)
        elements.append(Spacer(1, 15))

    # Looping Grafik & Tabel Pendukung
    for title, fig in figures_dict.items():
        if fig:
            try:
                img_bytes = pio.to_image(
                    fig, format="png", width=700, height=350, scale=2
                )
                elements.append(Paragraph(title, styles["Heading2"]))
                elements.append(Spacer(1, 4))
                elements.append(
                    RLImage(io.BytesIO(img_bytes), width=480, height=240)
                )
                elements.append(Spacer(1, 8))

                if title in tables_dict and not tables_dict[title].empty:
                    elements.append(create_pdf_table(tables_dict[title]))
                    elements.append(Spacer(1, 15))
            except Exception as e:
                print(f"Gagal memuat komponen {title}: {e}")

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# --- LOAD & PREPROCESSING DATA ---
df = load_sales_report()

if df is not None and not df.empty:
    df.columns = df.columns.astype(str).str.strip()
    if "Sales_Name" in df.columns:
        df["Sales_Name"] = (
            df["Sales_Name"]
            .fillna("UNCATEGORIZED")
            .astype(str)
            .str.strip()
            .str.upper()
        )
    df = check_role_access(df, sales_column_name="Sales_Name")

    if "Net_Sales_Amnt_Excl_Ppn" in df.columns:
        df["Net_Sales_Amnt_Excl_Ppn_Dec"] = df[
            "Net_Sales_Amnt_Excl_Ppn"
        ].apply(clean_to_decimal)
        df["Net_Sales_Amnt_Excl_Ppn"] = df[
            "Net_Sales_Amnt_Excl_Ppn_Dec"
        ].astype(float)
    else:
        df["Net_Sales_Amnt_Excl_Ppn_Dec"] = Decimal("0")
        df["Net_Sales_Amnt_Excl_Ppn"] = 0.0

    for c_col in ["Total_COGM", "Total_COGS"]:
        if c_col in df.columns:
            df[f"{c_col}_Dec"] = df[c_col].apply(clean_to_decimal)
            df[c_col] = df[f"{c_col}_Dec"].astype(float)
        else:
            df[f"{c_col}_Dec"] = Decimal("0")
            df[c_col] = 0.0

    for col in ["Tot_Qty_Kg", "Target"]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col]
                .astype(str)
                .str.replace(r"[^0-9.\-]", "", regex=True),
                errors="coerce",
            ).fillna(0)
        else:
            df[col] = 0

    date_col = next(
        (
            c
            for c in ["Order_Date", "Date", "Tgl", "Tanggal", "Periode"]
            if c in df.columns
        ),
        None,
    )
    if date_col:
        clean_date = (
            df[date_col].astype(str).str.replace(r"[^0-9]", "", regex=True)
        )
        df["Periode_Bulan"] = clean_date.str[:4] + "-" + clean_date.str[4:6]
    else:
        df["Periode_Bulan"] = "Unknown"

user_role = str(st.session_state.get("role", "sales")).lower()
active_cost_col = (
    "Total_COGM" if user_role in ["admin", "direksi"] else "Total_COGS"
)
active_cost_dec_col = f"{active_cost_col}_Dec"
cost_label = "COGM" if user_role in ["admin", "direksi"] else "COGS"


# --- HEADER UTAMA & EXPORT PDF ---
header_col1, header_col2 = st.columns([4, 1])
with header_col1:
    st.title("📊 Sales Performance Dashboard")
    st.caption(f"🕒 **Last Update Data:** {LAST_UPDATE_DATE}")

with header_col2:
    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
    if df is not None and not df.empty:
        df_t_bln = (
            df.groupby(["Sales_Name", "Periode_Bulan"])["Target"]
            .max()
            .reset_index()
        )
        df_tot_tgt = df_t_bln.groupby("Sales_Name")["Target"].sum().reset_index()
        df_s_agg = (
            df.groupby("Sales_Name")
            .agg(
                {
                    "Net_Sales_Amnt_Excl_Ppn_Dec": lambda x: sum(
                        x, Decimal("0")
                    ),
                    "Total_COGM_Dec": lambda x: sum(x, Decimal("0")),
                    "Total_COGS_Dec": lambda x: sum(x, Decimal("0")),
                }
            )
            .reset_index()
        )
        df_sum_pdf = pd.merge(
            df_s_agg, df_tot_tgt, on="Sales_Name", how="left"
        ).fillna(0)
        df_sum_pdf = df_sum_pdf.sort_values(
            by="Net_Sales_Amnt_Excl_Ppn_Dec", ascending=False
        )

        df_pdf_disp = pd.DataFrame()
        df_pdf_disp["Sales Name"] = df_sum_pdf["Sales_Name"]
        df_pdf_disp["Net Sales"] = df_sum_pdf[
            "Net_Sales_Amnt_Excl_Ppn_Dec"
        ].apply(lambda x: f"Rp {format_id(x, 2)}")
        if user_role in ["admin", "direksi"]:
            df_pdf_disp["Gross Margin COGM"] = (
                df_sum_pdf["Net_Sales_Amnt_Excl_Ppn_Dec"]
                - df_sum_pdf["Total_COGM_Dec"]
            ).apply(lambda x: f"Rp {format_id(x, 2)}")
        df_pdf_disp["Gross Margin COGS"] = (
            df_sum_pdf["Net_Sales_Amnt_Excl_Ppn_Dec"]
            - df_sum_pdf["Total_COGS_Dec"]
        ).apply(lambda x: f"Rp {format_id(x, 2)}")
        df_pdf_disp.index = range(1, len(df_pdf_disp) + 1)

        figures_to_export = {}
        tables_to_export = {}

        # 1. Target vs Sales
        try:
            df_tg = (
                pd.merge(
                    df.groupby("Sales_Name")["Net_Sales_Amnt_Excl_Ppn"]
                    .sum()
                    .reset_index(),
                    df.groupby(["Sales_Name", "Periode_Bulan"])["Target"]
                    .max()
                    .reset_index()
                    .groupby("Sales_Name")["Target"]
                    .sum()
                    .reset_index(),
                    on="Sales_Name",
                    how="left",
                )
                .fillna(0)
                .sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=False)
            )

            df_ml = df_tg.melt(
                id_vars="Sales_Name",
                value_vars=["Target", "Net_Sales_Amnt_Excl_Ppn"],
                var_name="Kategori",
                value_name="Nominal",
            )
            df_ml["Kategori"] = df_ml["Kategori"].replace(
                {"Target": "Target", "Net_Sales_Amnt_Excl_Ppn": "Net Sales"}
            )
            df_ml["Formatted_Nominal"] = df_ml["Nominal"].apply(
                lambda x: format_id(x, 2)
            )

            fig_t = px.bar(
                df_ml,
                x="Sales_Name",
                y="Nominal",
                color="Kategori",
                barmode="group",
                category_orders={"Sales_Name": df_tg["Sales_Name"].tolist()},
                color_discrete_map={
                    "Target": "#FF6B6B",
                    "Net Sales": "#4D96FF",
                },
                template="plotly_white",
                text="Formatted_Nominal",
                custom_data=["Formatted_Nominal"],
            )
            fig_t.update_traces(
                texttemplate="Rp %{text}",
                textposition="outside",
                hovertemplate="Sales: %{x}<br>Kategori: %{legendgroup}<br>Nominal: Rp %{customdata[0]}<extra></extra>",
            )

            key_t = "🎯 Pencapaian Sales vs Target (Per Bulan)"
            figures_to_export[key_t] = fig_t
            tables_to_export[key_t] = pd.DataFrame(
                {
                    "Sales Name": df_tg["Sales_Name"],
                    "Target (Rp)": df_tg["Target"].apply(
                        lambda x: f"Rp {format_id(x, 2)}"
                    ),
                    "Net Sales (Rp)": df_tg["Net_Sales_Amnt_Excl_Ppn"].apply(
                        lambda x: f"Rp {format_id(x, 2)}"
                    ),
                },
                index=range(1, len(df_tg) + 1),
            )
        except Exception:
            pass

        # 2. Produk Teratas
        try:
            item_col_pdf = next(
                (
                    c
                    for c in ["KeyItem", "Item_Name_Vam"]
                    if c in df.columns
                ),
                None,
            )
            if item_col_pdf:
                top_p = (
                    df.groupby(item_col_pdf)["Tot_Qty_Kg"]
                    .sum()
                    .reset_index()
                    .sort_values(by="Tot_Qty_Kg", ascending=False)
                    .head(10)
                )
                top_p[item_col_pdf] = (
                    top_p[item_col_pdf]
                    .fillna("UNKNOWN")
                    .astype(str)
                    .str.strip()
                )
                top_p = top_p[
                    (top_p[item_col_pdf] != "")
                    & (top_p[item_col_pdf].str.lower() != "nan")
                ]
                top_p["Formatted_Qty"] = top_p["Tot_Qty_Kg"].apply(
                    lambda x: format_id(x, 2)
                )

                fig_p = px.bar(
                    top_p,
                    x=item_col_pdf,
                    y="Tot_Qty_Kg",
                    template="plotly_white",
                    color="Tot_Qty_Kg",
                    color_continuous_scale="Viridis",
                    text="Formatted_Qty",
                    custom_data=["Formatted_Qty"],
                )
                fig_p.update_traces(
                    texttemplate="%{text} Kg",
                    textposition="outside",
                    hovertemplate="Produk: %{x}<br>Total Qty: %{customdata[0]} Kg<extra></extra>",
                )
                fig_p.update_layout(coloraxis_showscale=False)

                key_p = "🔥 10 Produk Teratas (Best Seller)"
                figures_to_export[key_p] = fig_p
                tables_to_export[key_p] = pd.DataFrame(
                    {
                        "Nama Produk": top_p[item_col_pdf].values,
                        "Total Qty (Kg)": top_p["Tot_Qty_Kg"]
                        .apply(lambda x: f"{format_id(x, 2)}")
                        .values,
                    },
                    index=range(1, len(top_p) + 1),
                )
        except Exception:
            pass

        # 3. Customer Tertinggi
        try:
            if "Cust_Name" in df.columns:
                top_c = (
                    df.groupby("Cust_Name")["Net_Sales_Amnt_Excl_Ppn"]
                    .sum()
                    .reset_index()
                    .sort_values(
                        by="Net_Sales_Amnt_Excl_Ppn", ascending=False
                    )
                    .head(10)
                )
                top_c["Cust_Name"] = (
                    top_c["Cust_Name"]
                    .fillna("UNKNOWN CUST")
                    .astype(str)
                    .str.strip()
                )
                top_c = top_c[
                    (top_c["Cust_Name"] != "")
                    & (top_c["Cust_Name"].str.lower() != "nan")
                ]
                top_c["Formatted_Sales"] = top_c[
                    "Net_Sales_Amnt_Excl_Ppn"
                ].apply(lambda x: format_id(x, 2))

                fig_c = px.bar(
                    top_c.sort_values(
                        by="Net_Sales_Amnt_Excl_Ppn", ascending=True
                    ),
                    x="Net_Sales_Amnt_Excl_Ppn",
                    y="Cust_Name",
                    orientation="h",
                    template="plotly_white",
                    color="Net_Sales_Amnt_Excl_Ppn",
                    color_continuous_scale="Tealgrn",
                    text="Formatted_Sales",
                    custom_data=["Formatted_Sales"],
                )
                fig_c.update_traces(
                    texttemplate="Rp %{text}",
                    textposition="outside",
                    hovertemplate="Customer: %{y}<br>Net Sales: Rp %{customdata[0]}<extra></extra>",
                )
                fig_c.update_layout(coloraxis_showscale=False)

                key_c = "👑 10 Customer Pembelian Tertinggi"
                figures_to_export[key_c] = fig_c
                tables_to_export[key_c] = pd.DataFrame(
                    {
                        "Customer Name": top_c["Cust_Name"].values,
                        "Net Sales (Rp)": top_c["Net_Sales_Amnt_Excl_Ppn"]
                        .apply(lambda x: f"Rp {format_id(x, 2)}")
                        .values,
                    },
                    index=range(1, len(top_c) + 1),
                )
        except Exception:
            pass

        # 4. Penjualan per Cabang
        try:
            if "Branch" in df.columns:
                df_b = (
                    df.groupby("Branch")["Net_Sales_Amnt_Excl_Ppn"]
                    .sum()
                    .reset_index()
                    .sort_values(
                        by="Net_Sales_Amnt_Excl_Ppn", ascending=False
                    )
                )
                df_b["Branch"] = (
                    df_b["Branch"].fillna("UNCATEGORIZED").astype(str)
                )
                df_b["Formatted_Sales"] = df_b[
                    "Net_Sales_Amnt_Excl_Ppn"
                ].apply(lambda x: format_id(x, 2))

                fig_b = px.pie(
                    df_b,
                    names="Branch",
                    values="Net_Sales_Amnt_Excl_Ppn",
                    hole=0.45,
                    template="plotly_white",
                    color_discrete_sequence=px.colors.qualitative.Prism,
                    custom_data=["Formatted_Sales"],
                )
                fig_b.update_traces(
                    textinfo="text+percent",
                    texttemplate="Rp %{customdata[0]}<br>(%{percent})",
                    hovertemplate="Branch: %{label}<br>Net Sales: Rp %{customdata[0]}<br>Persentase: %{percent}<extra></extra>",
                )

                key_b = "🏢 Total Penjualan per Cabang"
                figures_to_export[key_b] = fig_b
                tables_to_export[key_b] = pd.DataFrame(
                    {
                        "Branch": df_b["Branch"].values,
                        "Net Sales (Rp)": df_b["Net_Sales_Amnt_Excl_Ppn"]
                        .apply(lambda x: f"Rp {format_id(x, 2)}")
                        .values,
                    },
                    index=range(1, len(df_b) + 1),
                )
        except Exception:
            pass

        t_ns_pdf = sum(df["Net_Sales_Amnt_Excl_Ppn_Dec"], Decimal("0"))
        t_cost_pdf = sum(df[active_cost_dec_col], Decimal("0"))

        pdf_data = generate_full_pdf(
            df_pdf_disp,
            t_ns_pdf,
            t_cost_pdf,
            t_ns_pdf - t_cost_pdf,
            cost_label,
            user_role,
            figures_to_export,
            tables_to_export,
            LAST_UPDATE_DATE,
        )
        st.download_button(
            label="📥 Export PDF",
            data=pdf_data,
            file_name="full_sales_dashboard_report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

# --- BODY DASHBOARD STREAMLIT ---
if df is None or df.empty:
    st.error("Data tidak ditemukan atau kosong.")
else:
    with st.expander("🔍 Filter Data Dashboard", expanded=False):
        f1, f2 = st.columns(2)
        if "Branch" in df.columns:
            with f1:
                sel_b = st.multiselect(
                    "Filter Branch:",
                    options=sorted(
                        df["Branch"].dropna().astype(str).unique()
                    ),
                )
            if sel_b:
                df = df[df["Branch"].isin(sel_b)]

        if "Sales_Name" in df.columns and user_role in ["admin", "direksi"]:
            with f2:
                sel_s = st.multiselect(
                    "Filter Sales Name:",
                    options=sorted(df["Sales_Name"].dropna().unique()),
                )
            if sel_s:
                df = df[df["Sales_Name"].isin(sel_s)]

        f3, f4 = st.columns(2)
        if "Cust_Name" in df.columns:
            with f3:
                sel_c = st.multiselect(
                    "Filter Customer:",
                    options=sorted(
                        df["Cust_Name"].dropna().astype(str).unique()
                    ),
                )
            if sel_c:
                df = df[df["Cust_Name"].isin(sel_c)]

        if "Periode_Bulan" in df.columns:
            with f4:
                sel_p = st.multiselect(
                    "Filter Periode:",
                    options=sorted(
                        df["Periode_Bulan"].dropna().unique(), reverse=True
                    ),
                )
            if sel_p:
                df = df[df["Periode_Bulan"].isin(sel_p)]

    st.caption(
        f"ℹ️ Total baris data dimuat: **{format_id(len(df), 0)} baris**"
    )

    # Metrik Utama Tampilan Web
    ns_dec = sum(df["Net_Sales_Amnt_Excl_Ppn_Dec"], Decimal("0"))
    cost_dec = sum(df[active_cost_dec_col], Decimal("0"))

    m1, m2, m3 = st.columns(3)
    m1.metric("💰 Net Sales Excl PPN", f"Rp {format_id(ns_dec, 2)}")
    m2.metric(f"📦 Total {cost_label}", f"Rp {format_id(cost_dec, 2)}")
    m3.metric(
        f"📈 Net Margin {cost_label}", f"Rp {format_id(ns_dec - cost_dec, 2)}"
    )

    st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

    # Tabel Ringkasan Web
    if "Sales_Name" in df.columns and not df.empty:
        df_tb_bln = (
            df.groupby(["Sales_Name", "Periode_Bulan"])["Target"]
            .max()
            .reset_index()
        )
        df_tb_tgt = df_tb_bln.groupby("Sales_Name")["Target"].sum().reset_index()
        df_tb_agg = (
            df.groupby("Sales_Name")
            .agg(
                {
                    "Net_Sales_Amnt_Excl_Ppn_Dec": lambda x: sum(
                        x, Decimal("0")
                    ),
                    "Total_COGM_Dec": lambda x: sum(x, Decimal("0")),
                    "Total_COGS_Dec": lambda x: sum(x, Decimal("0")),
                }
            )
            .reset_index()
        )
        df_sum_web = pd.merge(
            df_tb_agg, df_tb_tgt, on="Sales_Name", how="left"
        ).fillna(0)
        df_sum_web = df_sum_web.sort_values(
            by="Net_Sales_Amnt_Excl_Ppn_Dec", ascending=False
        )

        df_web_disp = pd.DataFrame()
        df_web_disp["Sales Name"] = df_sum_web["Sales_Name"]
        df_web_disp["Net Sales Amnt Excl Ppn"] = df_sum_web[
            "Net_Sales_Amnt_Excl_Ppn_Dec"
        ].apply(lambda x: f"Rp {format_id(x, 2)}")

        cfg = {
            "Sales Name": st.column_config.TextColumn(
                "Sales Name", width="medium"
            ),
            "Net Sales Amnt Excl Ppn": st.column_config.TextColumn(
                "Net Sales Amnt Excl Ppn", alignment="right"
            ),
        }

        if user_role in ["admin", "direksi"]:
            df_web_disp["Gross Margin COGM"] = (
                df_sum_web["Net_Sales_Amnt_Excl_Ppn_Dec"]
                - df_sum_web["Total_COGM_Dec"]
            ).apply(lambda x: f"Rp {format_id(x, 2)}")
            df_web_disp["Net Margin COGM"] = df_sum_web.apply(
                lambda r: f"{format_id(float((r['Net_Sales_Amnt_Excl_Ppn_Dec'] - r['Total_COGM_Dec']) / r['Net_Sales_Amnt_Excl_Ppn_Dec'] * Decimal('100')) if r['Net_Sales_Amnt_Excl_Ppn_Dec'] else 0, 2)}%",
                axis=1,
            )
            cfg["Gross Margin COGM"] = st.column_config.TextColumn(
                "Gross Margin COGM", alignment="right"
            )
            cfg["Net Margin COGM"] = st.column_config.TextColumn(
                "Net Margin COGM", alignment="center"
            )

        df_web_disp["Gross Margin COGS"] = (
            df_sum_web["Net_Sales_Amnt_Excl_Ppn_Dec"]
            - df_sum_web["Total_COGS_Dec"]
        ).apply(lambda x: f"Rp {format_id(x, 2)}")
        df_web_disp["Net Margin COGS"] = df_sum_web.apply(
            lambda r: f"{format_id(float((r['Net_Sales_Amnt_Excl_Ppn_Dec'] - r['Total_COGS_Dec']) / r['Net_Sales_Amnt_Excl_Ppn_Dec'] * Decimal('100')) if r['Net_Sales_Amnt_Excl_Ppn_Dec'] else 0, 2)}%",
            axis=1,
        )
        cfg["Gross Margin COGS"] = st.column_config.TextColumn(
            "Gross Margin COGS", alignment="right"
        )
        cfg["Net Margin COGS"] = st.column_config.TextColumn(
            "Net Margin COGS", alignment="center"
        )

        df_web_disp.index = range(1, len(df_web_disp) + 1)
        with st.container(border=True):
            st.subheader("📋 Ringkasan Performa Per Sales")
            st.dataframe(
                df_web_disp, use_container_width=True, column_config=cfg
            )

    st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

    # Grafik Target vs Sales
    if "Sales_Name" in df.columns and not df.empty:
        df_t_web = (
            pd.merge(
                df.groupby("Sales_Name")["Net_Sales_Amnt_Excl_Ppn"]
                .sum()
                .reset_index(),
                df.groupby(["Sales_Name", "Periode_Bulan"])["Target"]
                .max()
                .reset_index()
                .groupby("Sales_Name")["Target"]
                .sum()
                .reset_index(),
                on="Sales_Name",
                how="left",
            )
            .fillna(0)
            .sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=False)
        )

        df_ml_web = df_t_web.melt(
            id_vars="Sales_Name",
            value_vars=["Target", "Net_Sales_Amnt_Excl_Ppn"],
            var_name="Kategori",
            value_name="Nominal",
        )
        df_ml_web["Kategori"] = df_ml_web["Kategori"].replace(
            {"Target": "Target", "Net_Sales_Amnt_Excl_Ppn": "Net Sales"}
        )
        df_ml_web["Formatted_Nominal"] = df_ml_web["Nominal"].apply(
            lambda x: format_id(x, 2)
        )

        fig_target = px.bar(
            df_ml_web,
            x="Sales_Name",
            y="Nominal",
            color="Kategori",
            barmode="group",
            category_orders={"Sales_Name": df_t_web["Sales_Name"].tolist()},
            color_discrete_map={"Target": "#FF6B6B", "Net Sales": "#4D96FF"},
            template="plotly_white",
            text="Formatted_Nominal",
            custom_data=["Formatted_Nominal"],
        )
        fig_target.update_traces(
            texttemplate="Rp %{text}",
            textposition="outside",
            hovertemplate="Sales: %{x}<br>Kategori: %{legendgroup}<br>Nominal: Rp %{customdata[0]}<extra></extra>",
        )
        fig_target.update_layout(
            legend=dict(orientation="h", y=1.15, x=0.5, xanchor="center"),
            margin=dict(l=20, r=20, t=50, b=20),
        )

        with st.container(border=True):
            st.subheader("🎯 Pencapaian Sales vs Target (Per Bulan)")
            st.plotly_chart(
                fig_target,
                use_container_width=True,
                config={"displayModeBar": False},
            )

    # Grafik Produk & Customer Teratas
    col_prod, col_cust = st.columns(2)
    with col_prod:
        item_col_web = next(
            (c for c in ["KeyItem", "Item_Name_Vam"] if c in df.columns), None
        )
        if item_col_web:
            tp_web = (
                df.groupby(item_col_web)["Tot_Qty_Kg"]
                .sum()
                .reset_index()
                .sort_values(by="Tot_Qty_Kg", ascending=False)
                .head(10)
            )
            tp_web["Formatted_Qty"] = tp_web["Tot_Qty_Kg"].apply(
                lambda x: format_id(x, 2)
            )

            fig_p = px.bar(
                tp_web,
                x=item_col_web,
                y="Tot_Qty_Kg",
                template="plotly_white",
                color="Tot_Qty_Kg",
                color_continuous_scale="Viridis",
                text="Formatted_Qty",
                custom_data=["Formatted_Qty"],
            )
            fig_p.update_traces(
                texttemplate="%{text} Kg",
                textposition="outside",
                hovertemplate="Produk: %{x}<br>Total Qty: %{customdata[0]} Kg<extra></extra>",
            )
            fig_p.update_layout(
                height=450,
                xaxis=dict(tickangle=-35),
                coloraxis_showscale=False,
            )
            with st.container(border=True):
                st.subheader("🔥 10 Produk Teratas (Best Seller)")
                st.plotly_chart(
                    fig_p,
                    use_container_width=True,
                    config={"displayModeBar": False},
                )

    with col_cust:
        if "Cust_Name" in df.columns:
            tc_web = (
                df.groupby("Cust_Name")["Net_Sales_Amnt_Excl_Ppn"]
                .sum()
                .reset_index()
                .sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=False)
                .head(10)
                .sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=True)
            )
            tc_web["Formatted_Sales"] = tc_web["Net_Sales_Amnt_Excl_Ppn"].apply(
                lambda x: format_id(x, 2)
            )

            fig_c = px.bar(
                tc_web,
                x="Net_Sales_Amnt_Excl_Ppn",
                y="Cust_Name",
                orientation="h",
                template="plotly_white",
                color="Net_Sales_Amnt_Excl_Ppn",
                color_continuous_scale="Tealgrn",
                text="Formatted_Sales",
                custom_data=["Formatted_Sales"],
            )
            fig_c.update_traces(
                texttemplate="Rp %{text}",
                textposition="outside",
                hovertemplate="Customer: %{y}<br>Net Sales: Rp %{customdata[0]}<extra></extra>",
            )
            fig_c.update_layout(
                height=450,
                yaxis=dict(categoryorder="total ascending"),
                coloraxis_showscale=False,
            )
            with st.container(border=True):
                st.subheader("👑 10 Customer Pembelian Tertinggi")
                st.plotly_chart(
                    fig_c,
                    use_container_width=True,
                    config={"displayModeBar": False},
                )

    # Grafik Cabang
    if "Branch" in df.columns:
        df_b_web = (
            df.groupby("Branch")["Net_Sales_Amnt_Excl_Ppn"]
            .sum()
            .reset_index()
            .sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=False)
        )
        df_b_web["Formatted_Sales"] = df_b_web["Net_Sales_Amnt_Excl_Ppn"].apply(
            lambda x: format_id(x, 2)
        )

        fig_b = px.pie(
            df_b_web,
            names="Branch",
            values="Net_Sales_Amnt_Excl_Ppn",
            hole=0.45,
            template="plotly_white",
            color_discrete_sequence=px.colors.qualitative.Prism,
            custom_data=["Formatted_Sales"],
        )
        fig_b.update_traces(
            textinfo="text+percent",
            texttemplate="Rp %{customdata[0]}<br>(%{percent})",
            hovertemplate="Branch: %{label}<br>Net Sales: Rp %{customdata[0]}<br>Persentase: %{percent}<extra></extra>",
        )
        fig_b.update_layout(
            legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center")
        )
        with st.container(border=True):
            st.subheader("🏢 Total Penjualan per Cabang")
            st.plotly_chart(
                fig_b,
                use_container_width=True,
                config={"displayModeBar": False},
            )