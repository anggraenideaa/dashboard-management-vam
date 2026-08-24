import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.io as pio
from decimal import Decimal
import re
from db import load_sales_report, check_role_access

# Library untuk ReportLab (Export PDF)
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io

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
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        return formatted
    except Exception:
        return val

# INFORMASI PERIODE UPDATE DATA
LAST_UPDATE_DATE = "24 Agustus 2026"

def clean_to_decimal(val):
    try:
        if pd.isna(val):
            return Decimal('0')
        s = str(val).replace("Rp", "").replace("(", "-").replace(")", "").replace(",", "")
        s = re.sub(r'[^0-9.\-]', '', s)
        return Decimal(s) if s and s != "-" else Decimal('0')
    except Exception:
        return Decimal('0')

df = load_sales_report()

if df is not None and not df.empty:
    df.columns = df.columns.astype(str).str.strip()
    if "Sales_Name" in df.columns:
        df["Sales_Name"] = df["Sales_Name"].fillna("UNCATEGORIZED").astype(str).str.strip().str.upper()
    df = check_role_access(df, sales_column_name="Sales_Name")

    # Konversi kolom numerik utama ke Decimal murni untuk akurasi sum()
    if "Net_Sales_Amnt_Excl_Ppn" in df.columns:
        df["Net_Sales_Amnt_Excl_Ppn_Dec"] = df["Net_Sales_Amnt_Excl_Ppn"].apply(clean_to_decimal)
        df["Net_Sales_Amnt_Excl_Ppn"] = df["Net_Sales_Amnt_Excl_Ppn_Dec"].astype(float)
    else:
        df["Net_Sales_Amnt_Excl_Ppn_Dec"] = Decimal('0')
        df["Net_Sales_Amnt_Excl_Ppn"] = 0.0

    for c_col in ["Total_COGM", "Total_COGS"]:
        if c_col in df.columns:
            df[f"{c_col}_Dec"] = df[c_col].apply(clean_to_decimal)
            df[c_col] = df[f"{c_col}_Dec"].astype(float)
        else:
            df[f"{c_col}_Dec"] = Decimal('0')
            df[c_col] = 0.0

    other_numeric_cols = ["Tot_Qty_Kg", "Target"]
    for col in other_numeric_cols:
        if col in df.columns:
            if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace("(", "-", regex=False).str.replace(")", "", regex=False)
                    .str.replace(",", "", regex=False).str.replace(r'[^0-9.\-]', '', regex=True), 
                    errors="coerce"
                ).fillna(0)
            else:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col] = 0

    date_col = None
    for c in ["Order_Date", "Date", "Tgl", "Tanggal", "Periode"]:
        if c in df.columns:
            date_col = c
            break
            
    if date_col:
        clean_date = df[date_col].astype(str).str.replace(r'[^0-9]', '', regex=True)
        year, month = clean_date.str[:4], clean_date.str[4:6]
        df["Periode_Bulan"] = year + "-" + month
        df.loc[(month == "") | (month.str.len() < 2), "Periode_Bulan"] = clean_date.str[:6]
    else:
        df["Periode_Bulan"] = "Unknown"

user_role = str(st.session_state.get("role", "sales")).lower()
active_cost_col = "Total_COGM" if user_role in ["admin", "direksi"] else "Total_COGS"
active_cost_dec_col = f"{active_cost_col}_Dec"
cost_label = "COGM" if user_role in ["admin", "direksi"] else "COGS"

# --- FUNGSI GENERATE PDF FULL DASHBOARD ---
def generate_full_pdf(summary_df, t_net_sales, t_cost, t_margin, c_label, role, figures_dict, update_date):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('ReportTitle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1f2937'), spaceAfter=4)
    subtitle_style = ParagraphStyle('ReportSubtitle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#6b7280'), spaceAfter=15)
    
    elements.append(Paragraph("Sales Performance Dashboard Report", title_style))
    elements.append(Paragraph(f"Role Akses: {role.upper()} | Last Update Data: {update_date}", subtitle_style))
    
    # Metrik Utama
    metrics_data = [
        ["Metrik Utama", "Total Nilai (Rp)"],
        ["Net Sales Excl PPN", f"Rp {format_id(t_net_sales, 2)}"],
        [f"Total {c_label}", f"Rp {format_id(t_cost, 2)}"],
        [f"Net Margin {c_label}", f"Rp {format_id(t_margin, 2)}"]
    ]
    
    t_metrics = Table(metrics_data, colWidths=[250, 302])
    t_metrics.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f4f6')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#111827')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#d1d5db')),
    ]))
    elements.append(t_metrics)
    elements.append(Spacer(1, 15))
    
    # Tabel Ringkasan Per Sales
    if not summary_df.empty:
        elements.append(Paragraph("Ringkasan Performa Per Sales", styles['Heading2']))
        elements.append(Spacer(1, 6))
        table_data = [list(summary_df.columns)] + summary_df.astype(str).values.tolist()
        t_summary = Table(table_data, repeatRows=1)
        t_summary.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4f46e5')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 8),
            ('BOTTOMPADDING', (0,0), (-1,0), 5),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f9fafb')]),
            ('FONTSIZE', (0,1), (-1,-1), 7),
        ]))
        elements.append(t_summary)
        elements.append(Spacer(1, 15))
        
    # Grafik PDF
    for title, fig in figures_dict.items():
        if fig:
            try:
                img_bytes = pio.to_image(fig, format="png", width=700, height=350, scale=2)
                img_stream = io.BytesIO(img_bytes)
                elements.append(Paragraph(title, styles['Heading2']))
                elements.append(Spacer(1, 4))
                elements.append(RLImage(img_stream, width=480, height=240))
                elements.append(Spacer(1, 12))
            except Exception as e:
                print(f"Gagal memuat grafik {title}: {e}")
                    
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

# --- HEADER UTAMA & TOMBOL PDF ---
header_col1, header_col2 = st.columns([4, 1])
with header_col1:
    st.title("📊 Sales Performance Dashboard")
    st.caption(f"🕒 **Last Update Data:** {LAST_UPDATE_DATE}")
with header_col2:
    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
    if df is not None and not df.empty:
        df_target_per_bulan = df.groupby(["Sales_Name", "Periode_Bulan"])["Target"].max().reset_index()
        df_total_target = df_target_per_bulan.groupby("Sales_Name")["Target"].sum().reset_index()
        
        df_sales_agg = df.groupby("Sales_Name").agg({
            "Net_Sales_Amnt_Excl_Ppn_Dec": lambda x: sum(x, Decimal('0')),
            "Total_COGM_Dec": lambda x: sum(x, Decimal('0')),
            "Total_COGS_Dec": lambda x: sum(x, Decimal('0'))
        }).reset_index()
        
        df_summary_pdf = pd.merge(df_sales_agg, df_total_target, on="Sales_Name", how="left").fillna(0)
        df_summary_pdf = df_summary_pdf.sort_values(by="Net_Sales_Amnt_Excl_Ppn_Dec", ascending=False)
        
        df_pdf_disp = pd.DataFrame()
        df_pdf_disp["Sales Name"] = df_summary_pdf["Sales_Name"]
        df_pdf_disp["Net Sales"] = df_summary_pdf["Net_Sales_Amnt_Excl_Ppn_Dec"].apply(lambda x: f"Rp {format_id(x, 2)}")
        if user_role in ["admin", "direksi"]:
            m_cogm = df_summary_pdf.apply(lambda row: row["Net_Sales_Amnt_Excl_Ppn_Dec"] - row["Total_COGM_Dec"], axis=1)
            df_pdf_disp["Gross Margin COGM"] = m_cogm.apply(lambda x: f"Rp {format_id(x, 2)}")
        m_cogs = df_summary_pdf.apply(lambda row: row["Net_Sales_Amnt_Excl_Ppn_Dec"] - row["Total_COGS_Dec"], axis=1)
        df_pdf_disp["Gross Margin COGS"] = m_cogs.apply(lambda x: f"Rp {format_id(x, 2)}")
        df_pdf_disp.index = range(1, len(df_pdf_disp) + 1)

        figures_to_export = {}
        
        try:
            df_t1 = df.groupby(["Sales_Name", "Periode_Bulan"])["Target"].max().reset_index()
            df_tf = df_t1.groupby("Sales_Name")["Target"].sum().reset_index()
            df_sval = df.groupby("Sales_Name")["Net_Sales_Amnt_Excl_Ppn"].sum().reset_index()
            df_tg = pd.merge(df_sval, df_tf, on="Sales_Name", how="left").fillna(0).sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=False)
            df_ml = df_tg.melt(id_vars="Sales_Name", value_vars=["Target", "Net_Sales_Amnt_Excl_Ppn"], var_name="Kategori", value_name="Nominal")
            df_ml["Kategori"] = df_ml["Kategori"].replace({"Target": "Target", "Net_Sales_Amnt_Excl_Ppn": "Net Sales"})
            fig_t = px.bar(
                df_ml, x="Sales_Name", y="Nominal", color="Kategori", barmode="group", 
                color_discrete_map={"Target": "#FF6B6B", "Net Sales": "#4D96FF"}, 
                template="plotly_white", text="Nominal"
            )
            fig_t.update_traces(texttemplate='Rp %{text:,.0f}', textposition='outside')
            figures_to_export["Pencapaian Sales vs Target"] = fig_t
        except Exception:
            pass

        try:
            item_col_pdf = "KeyItem" if "KeyItem" in df.columns else ("Item_Name_Vam" if "Item_Name_Vam" in df.columns else None)
            if item_col_pdf:
                top_p = df.groupby(item_col_pdf)["Tot_Qty_Kg"].sum().reset_index().sort_values(by="Tot_Qty_Kg", ascending=False).head(10)
                fig_p = px.bar(top_p, x=item_col_pdf, y="Tot_Qty_Kg", template="plotly_white", color="Tot_Qty_Kg", color_continuous_scale="Viridis", text="Tot_Qty_Kg")
                fig_p.update_traces(texttemplate='%{text:,.2f} Kg', textposition='outside')
                figures_to_export["10 Produk Teratas (Best Seller)"] = fig_p
        except Exception:
            pass

        try:
            if "Cust_Name" in df.columns:
                top_c = df.groupby("Cust_Name")["Net_Sales_Amnt_Excl_Ppn"].sum().reset_index().sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=False).head(10).sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=True)
                fig_c = px.bar(top_c, x="Net_Sales_Amnt_Excl_Ppn", y="Cust_Name", orientation="h", template="plotly_white", color="Net_Sales_Amnt_Excl_Ppn", color_continuous_scale="Tealgrn", text="Net_Sales_Amnt_Excl_Ppn")
                fig_c.update_traces(texttemplate='Rp %{text:,.0f}', textposition='outside')
                figures_to_export["10 Customer Pembelian Tertinggi"] = fig_c
        except Exception:
            pass

        try:
            if "Branch" in df.columns:
                df_b = df.groupby("Branch")["Net_Sales_Amnt_Excl_Ppn"].sum().reset_index().sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=False)
                fig_b = px.pie(df_b, names="Branch", values="Net_Sales_Amnt_Excl_Ppn", hole=0.45, template="plotly_white", color_discrete_sequence=px.colors.qualitative.Prism)
                fig_b.update_traces(textinfo='value+percent', texttemplate='Rp %{value:,.0f}<br>(%{percent})')
                figures_to_export["Total Penjualan per Cabang"] = fig_b
        except Exception:
            pass

        # Perhitungan Decimal Akurat untuk Ringkasan PDF
        t_ns_pdf = sum(df["Net_Sales_Amnt_Excl_Ppn_Dec"], Decimal('0')) if not df.empty else Decimal('0')
        t_cost_pdf = sum(df[active_cost_dec_col], Decimal('0')) if not df.empty else Decimal('0')
        t_margin_pdf = t_ns_pdf - t_cost_pdf

        pdf_data = generate_full_pdf(
            df_pdf_disp, 
            t_ns_pdf, 
            t_cost_pdf, 
            t_margin_pdf, 
            cost_label, 
            user_role, 
            figures_to_export,
            LAST_UPDATE_DATE
        )
        st.download_button(
            label="📥 Export PDF",
            data=pdf_data,
            file_name="full_sales_dashboard_report.pdf",
            mime="application/pdf",
            use_container_width=True
        )

st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

if df is None:
    st.error("Fungsi `load_sales_report()` mengembalikan nilai `None`.")
elif df.empty:
    st.error("DataFrame kosong (`df.empty` bernilai True).")
else:
    df.columns = df.columns.astype(str).str.strip()

    if "Sales_Name" in df.columns:
        df["Sales_Name"] = df["Sales_Name"].fillna("UNCATEGORIZED").astype(str).str.strip().str.upper()

    df = check_role_access(df, sales_column_name="Sales_Name")

    with st.expander("🔍 Filter Data Dashboard", expanded=False):
        f_col1, f_col2 = st.columns(2)
        if "Branch" in df.columns:
            all_branches = sorted(df["Branch"].dropna().astype(str).unique().tolist())
            with f_col1:
                selected_branches = st.multiselect("Filter Branch:", options=all_branches, default=[], placeholder="Pilih Cabang...")
            if selected_branches:
                df = df[df["Branch"].isin(selected_branches)]

        if "Sales_Name" in df.columns and user_role in ["admin", "direksi"]:
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
            all_periode = sorted(df["Periode_Bulan"].dropna().unique().tolist(), reverse=True)
            with f_col4:
                selected_periode = st.multiselect("Filter Periode:", options=all_periode, default=[], placeholder="Pilih Periode...")
            if selected_periode:
                df = df[df["Periode_Bulan"].isin(selected_periode)]

    st.caption(f"ℹ️ Total baris data dimuat (setelah filter): **{format_id(len(df), 0)} baris**")
    st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True)

    # --- HITUNG METRIK UTAMA DENGAN DECIMAL (MEMBAWA PRESISI AKURAT) ---
    total_net_sales_dec = sum(df["Net_Sales_Amnt_Excl_Ppn_Dec"], Decimal('0'))
    total_cost_dec = sum(df[active_cost_dec_col], Decimal('0'))
    total_net_margin_dec = total_net_sales_dec - total_cost_dec

    m1, m2, m3 = st.columns(3)
    m1.metric("💰 Net Sales Excl PPN", f"Rp {format_id(total_net_sales_dec, 2)}")
    m2.metric(f"📦 Total {cost_label}", f"Rp {format_id(total_cost_dec, 2)}")
    m3.metric(f"📈 Net Margin {cost_label}", f"Rp {format_id(total_net_margin_dec, 2)}")

    st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

    if "Sales_Name" in df.columns and not df.empty:
        df_target_per_bulan = df.groupby(["Sales_Name", "Periode_Bulan"])["Target"].max().reset_index()
        df_total_target = df_target_per_bulan.groupby("Sales_Name")["Target"].sum().reset_index()

        df_sales_agg = df.groupby("Sales_Name").agg({
            "Net_Sales_Amnt_Excl_Ppn_Dec": lambda x: sum(x, Decimal('0')),
            "Total_COGM_Dec": lambda x: sum(x, Decimal('0')),
            "Total_COGS_Dec": lambda x: sum(x, Decimal('0'))
        }).reset_index()

        df_summary = pd.merge(df_sales_agg, df_total_target, on="Sales_Name", how="left").fillna(0)
        df_summary = df_summary.sort_values(by="Net_Sales_Amnt_Excl_Ppn_Dec", ascending=False)

        df_display = pd.DataFrame()
        df_display["Sales Name"] = df_summary["Sales_Name"]
        df_display["Net Sales Amnt Excl Ppn"] = df_summary["Net_Sales_Amnt_Excl_Ppn_Dec"].apply(lambda x: f"Rp {format_id(x, 2)}")

        column_config_dict = {
            "Sales Name": st.column_config.TextColumn("Sales Name", width="medium", alignment="left"),
            "Net Sales Amnt Excl Ppn": st.column_config.TextColumn("Net Sales Amnt Excl Ppn", alignment="right"),
        }

        if user_role in ["admin", "direksi"]:
            df_summary["Gross_Margin_COGM"] = df_summary.apply(lambda row: row["Net_Sales_Amnt_Excl_Ppn_Dec"] - row["Total_COGM_Dec"], axis=1)
            df_summary["Net_Margin_COGM (%)"] = df_summary.apply(
                lambda row: float((row["Net_Sales_Amnt_Excl_Ppn_Dec"] - row["Total_COGM_Dec"]) / row["Net_Sales_Amnt_Excl_Ppn_Dec"] * Decimal('100'))
                if row["Net_Sales_Amnt_Excl_Ppn_Dec"] != Decimal('0') else 0.0, axis=1
            )
            df_display["Gross Margin COGM"] = df_summary["Gross_Margin_COGM"].apply(lambda x: f"Rp {format_id(x, 2)}")
            df_display["Net Margin COGM"] = df_summary["Net_Margin_COGM (%)"].apply(lambda x: f"{format_id(x, 2)}%")
            column_config_dict["Gross Margin COGM"] = st.column_config.TextColumn("Gross Margin COGM", alignment="right")
            column_config_dict["Net Margin COGM"] = st.column_config.TextColumn("Net Margin COGM", alignment="center")

        df_summary["Gross_Margin_COGS"] = df_summary.apply(lambda row: row["Net_Sales_Amnt_Excl_Ppn_Dec"] - row["Total_COGS_Dec"], axis=1)
        df_summary["Net_Margin_COGS (%)"] = df_summary.apply(
            lambda row: float((row["Net_Sales_Amnt_Excl_Ppn_Dec"] - row["Total_COGS_Dec"]) / row["Net_Sales_Amnt_Excl_Ppn_Dec"] * Decimal('100'))
            if row["Net_Sales_Amnt_Excl_Ppn_Dec"] != Decimal('0') else 0.0, axis=1
        )
        df_display["Gross Margin COGS"] = df_summary["Gross_Margin_COGS"].apply(lambda x: f"Rp {format_id(x, 2)}")
        df_display["Net Margin COGS"] = df_summary["Net_Margin_COGS (%)"].apply(lambda x: f"{format_id(x, 2)}%")
        column_config_dict["Gross Margin COGS"] = st.column_config.TextColumn("Gross Margin COGS", alignment="right")
        column_config_dict["Net Margin COGS"] = st.column_config.TextColumn("Net Margin COGS", alignment="center")

        df_display.index = range(1, len(df_display) + 1)

        with st.container(border=True):
            st.subheader("📋 Ringkasan Performa Per Sales")
            st.dataframe(df_display, use_container_width=True, column_config=column_config_dict)

    st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

    if "Sales_Name" in df.columns and not df.empty:
        df_t1 = df.groupby(["Sales_Name", "Periode_Bulan"])["Target"].max().reset_index()
        df_target_final = df_t1.groupby("Sales_Name")["Target"].sum().reset_index()
        df_sales_val = df.groupby("Sales_Name")["Net_Sales_Amnt_Excl_Ppn"].sum().reset_index()
        df_target = pd.merge(df_sales_val, df_target_final, on="Sales_Name", how="left").fillna(0)
        df_target = df_target.sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=False)
        sales_order = df_target["Sales_Name"].tolist()

        df_melted = df_target.melt(id_vars="Sales_Name", value_vars=["Target", "Net_Sales_Amnt_Excl_Ppn"], var_name="Kategori", value_name="Nominal")
        df_melted["Kategori"] = df_melted["Kategori"].replace({"Target": "Target", "Net_Sales_Amnt_Excl_Ppn": "Net Sales"})
        
        fig_target = px.bar(
            df_melted, x="Sales_Name", y="Nominal", color="Kategori", barmode="group", 
            category_orders={"Sales_Name": sales_order}, 
            labels={"Nominal": "Nominal (Rp)", "Sales_Name": "Sales Name", "Kategori": "Keterangan"}, 
            color_discrete_map={"Target": "#FF6B6B", "Net Sales": "#4D96FF"}, 
            template="plotly_white",
            text="Nominal"
        )
        fig_target.update_traces(
            texttemplate='Rp %{text:,.0f}', 
            textposition='outside',
            hovertemplate="<b>%{x}</b><br>%{legendgroup}: Rp %{y:,.2f}<extra></extra>"
        )
        fig_target.update_layout(
            font=dict(family="sans-serif", size=12, color="#333333"), 
            legend=dict(orientation="h", y=1.15, x=0.5, xanchor="center", bgcolor="rgba(255,255,255,0.8)", bordercolor="rgba(0,0,0,0.1)", borderwidth=1), 
            margin=dict(l=20, r=20, t=50, b=20), 
            hovermode="x unified", 
            xaxis=dict(showgrid=False, showline=True, linewidth=1, linecolor='lightgray'), 
            yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.08)", showline=True, linewidth=1, linecolor='lightgray')
        )

        with st.container(border=True):
            st.subheader("🎯 Pencapaian Sales vs Target (Per Bulan)")
            st.plotly_chart(fig_target, use_container_width=True, config={"displayModeBar": False})

    c1, c2 = st.columns(2)
    with c1:
        item_col = "KeyItem" if "KeyItem" in df.columns else ("Item_Name_Vam" if "Item_Name_Vam" in df.columns else None)
        if item_col:
            top_products = df.groupby(item_col)["Tot_Qty_Kg"].sum().reset_index().sort_values(by="Tot_Qty_Kg", ascending=False).head(10)
            fig_prod = px.bar(
                top_products, x=item_col, y="Tot_Qty_Kg", 
                labels={item_col: "Nama Produk", "Tot_Qty_Kg": "Total Qty (Kg)"}, 
                template="plotly_white", color="Tot_Qty_Kg", color_continuous_scale="Viridis",
                text="Tot_Qty_Kg"
            )
            fig_prod.update_traces(
                texttemplate='%{text:,.2f} Kg', 
                textposition='outside',
                hovertemplate="<b>%{x}</b><br>Total Qty: %{y:,.2f} Kg<extra></extra>"
            )
            fig_prod.update_layout(
                height=450, 
                bargap=0.3, 
                xaxis=dict(tickangle=-35, showgrid=False, showline=True, linewidth=1, linecolor='lightgray'), 
                yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.08)", showline=True, linewidth=1, linecolor='lightgray'), 
                margin=dict(l=20, r=20, t=30, b=80), 
                coloraxis_showscale=False
            )
            with st.container(border=True):
                st.subheader("🔥 10 Produk Teratas (Best Seller)")
                st.plotly_chart(fig_prod, use_container_width=True, config={"displayModeBar": False})

    with c2:
        if "Cust_Name" in df.columns:
            top_cust = df.groupby("Cust_Name")["Net_Sales_Amnt_Excl_Ppn"].sum().reset_index().sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=False).head(10).sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=True)
            fig_cust = px.bar(
                top_cust, x="Net_Sales_Amnt_Excl_Ppn", y="Cust_Name", orientation="h", 
                labels={"Cust_Name": "Customer Name", "Net_Sales_Amnt_Excl_Ppn": "Net Sales (Rp)"}, 
                template="plotly_white", color="Net_Sales_Amnt_Excl_Ppn", color_continuous_scale="Tealgrn",
                text="Net_Sales_Amnt_Excl_Ppn"
            )
            fig_cust.update_traces(
                texttemplate='Rp %{text:,.0f}', 
                textposition='outside',
                hovertemplate="<b>%{y}</b><br>Net Sales: Rp %{x:,.2f}<extra></extra>"
            )
            fig_cust.update_layout(
                height=450, 
                bargap=0.3, 
                xaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.08)", showline=True, linewidth=1, linecolor='lightgray'), 
                yaxis=dict(showgrid=False, showline=True, linewidth=1, linecolor='lightgray', categoryorder='total ascending'), 
                margin=dict(l=20, r=50, t=10, b=40), 
                coloraxis_showscale=False
            )
            with st.container(border=True):
                st.subheader("👑 10 Customer Pembelian Tertinggi")
                st.plotly_chart(fig_cust, use_container_width=True, config={"displayModeBar": False})

    if "Branch" in df.columns:
        df_branch = df.groupby("Branch")["Net_Sales_Amnt_Excl_Ppn"].sum().reset_index().sort_values(by="Net_Sales_Amnt_Excl_Ppn", ascending=False)
        fig_branch = px.pie(df_branch, names="Branch", values="Net_Sales_Amnt_Excl_Ppn", hole=0.45, labels={"Branch": "Branch", "Net_Sales_Amnt_Excl_Ppn": "Total Sales"}, template="plotly_white", color_discrete_sequence=px.colors.qualitative.Prism)
        fig_branch.update_traces(textinfo='value+percent', texttemplate='Rp %{value:,.0f}<br>(%{percent})', hoverinfo='label+value+percent', hovertemplate="<b>Cabang: %{label}</b><br>Total Sales: Rp %{value:,.0f}<br>Persentase: %{percent}<extra></extra>", marker=dict(line=dict(color='#ffffff', width=2)))
        fig_branch.update_layout(margin=dict(l=20, r=20, t=10, b=10), legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"))
        with st.container(border=True):
            st.subheader("🏢 Total Penjualan per Cabang")
            st.plotly_chart(fig_branch, use_container_width=True, config={"displayModeBar": False})