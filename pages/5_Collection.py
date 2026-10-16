"""Dashboard Collection — khusus Direksi. Sumber: db.load_sales_report().

Definisi KPI:
- Piutang Jatuh Tempo: saldo SAAT INI dengan Jth_Tempo <= akhir bulan pilihan.
- Collection Aktual: Payment_Amnt dengan Payment_Date pada bulan pilihan.
- Outstanding Saat Ini: seluruh saldo SAAT INI, termasuk belum jatuh tempo.
- Collection Tanpa PPN: pembayaran bulan pilihan * (penjualan sebelum PPN / penjualan termasuk PPN).

Catatan: saldo historis akhir bulan tidak dapat direkonstruksi tanpa histori pembayaran lengkap.
"""
import re
import pandas as pd
import streamlit as st
from db import load_sales_report

if not st.session_state.get("logged_in", False):
    st.error("Silakan login terlebih dahulu.")
    st.stop()
if str(st.session_state.get("role", "")).strip().lower() not in ("direksi", "direktur"):
    st.error("Halaman Collection hanya dapat diakses Direksi.")
    st.stop()


def rupiah(value):
    value = 0 if pd.isna(value) else float(value)
    formatted = f"{value:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"Rp {formatted}"


def to_number(value):
    """Menangani 3599999.996; 3,600,000.00; 3.600.000,00; dan angka asli."""
    if value is None or pd.isna(value) or str(value).strip() == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = re.sub(r"[^\d,.\-]", "", str(value).strip())
    if s in ("", "-", ".", ","):
        return 0.0
    dots, commas = s.count("."), s.count(",")
    if dots and commas:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        sep = "," if dec == "." else "."
        s = s.replace(sep, "").replace(dec, ".")
    elif dots > 1 or commas > 1:
        sep = "." if dots else ","
        parts = s.split(sep)
        if all(len(p) == 3 for p in parts[1:]):
            s = "".join(parts)
        else:
            s = "".join(parts[:-1]) + "." + parts[-1]
    elif dots or commas:
        sep = "." if dots else ","
        left, right = s.split(sep, 1)
        # 3.600 = 3600; 3599999.996 = 3599999.996 (bukan 3599999996)
        if len(right) == 3 and len(left.lstrip("-")) <= 3:
            s = left + right
        else:
            s = left + "." + right
    try:
        return float(s)
    except ValueError:
        return 0.0


def to_dates(series):
    vals = series.astype("string").str.strip()
    result = pd.to_datetime(vals, format="%m/%d/%Y", errors="coerce")
    missing = result.isna()
    result.loc[missing] = pd.to_datetime(vals.loc[missing], format="%Y-%m-%d", errors="coerce")
    nums = pd.to_numeric(vals, errors="coerce")
    excel = result.isna() & nums.between(20000, 80000)
    result.loc[excel] = pd.to_datetime(nums.loc[excel], origin="1899-12-30", unit="D", errors="coerce")
    return result


def prepare(source):
    d = source.copy()
    d.columns = d.columns.map(lambda x: str(x).strip())
    needed = ["Cust_Name", "Net_Ar", "Balance", "Jth_Tempo", "Payment_Date", "Payment_Amnt", "Net_Sales_Amnt_Excl_Ppn", "Net_Sales_Amnt_Incl_Ppn"]
    absent = [x for x in needed if x not in d]
    if absent:
        raise ValueError("Kolom wajib tidak ditemukan: " + ", ".join(absent))
    text_cols = ["No_Inv", "No_SJ", "Cust_Name", "Company", "Branch", "Sales_Name", "Item_Name_Vam", "KeyItem", "Acc_Bank", "Ket_Bayar", "Tanda"]
    for col in text_cols:
        if col not in d:
            d[col] = ""
        d[col] = d[col].fillna("").astype(str).str.strip()
    for col in ["Net_Ar", "Balance", "Payment_Amnt", "Net_Sales_Amnt_Excl_Ppn", "Net_Sales_Amnt_Incl_Ppn"]:
        d[col] = d[col].map(to_number)
    for col in ["Payment_Date", "Jth_Tempo", "Tgl_Inv"]:
        d[col] = to_dates(d[col]) if col in d else pd.NaT
    d = d[d["Cust_Name"].ne("") & d["Tanda"].str.upper().isin(("", "V", "VAM"))].copy()
    d["Customer"] = d["Cust_Name"].str.upper().str.replace(r"\s+", " ", regex=True).str.strip()
    for col in ["Branch", "Sales_Name", "Company"]:
        d[col] = d[col].str.upper()
    valid_inv = ~d["No_Inv"].str.upper().isin(("", "-", "NAN", "NONE"))
    valid_sj = ~d["No_SJ"].str.upper().isin(("", "-", "NAN", "NONE"))
    d["Invoice_ID"] = d["No_Inv"]
    d.loc[~valid_inv & valid_sj, "Invoice_ID"] = "SJ: " + d.loc[~valid_inv & valid_sj, "No_SJ"]
    neither = ~valid_inv & ~valid_sj
    d.loc[neither, "Invoice_ID"] = "BARIS: " + d.index[neither].astype(str)
    d["Tagihan"] = d["Net_Ar"].clip(lower=0)
    d["Outstanding"] = d["Balance"].clip(lower=0)
    d.loc[d["Outstanding"].abs() < 0.01, "Outstanding"] = 0.0
    d["Pembayaran"] = d["Payment_Amnt"].where(d["Payment_Date"].notna() & d["Payment_Amnt"].gt(0), 0.0)
    ratio = (d["Net_Sales_Amnt_Excl_Ppn"] / d["Net_Sales_Amnt_Incl_Ppn"].replace(0, float("nan"))).fillna(0).clip(0, 1)
    d["Pembayaran_Tanpa_PPN"] = d["Pembayaran"] * ratio
    d["Rasio_Tersedia"] = d["Net_Sales_Amnt_Incl_Ppn"].gt(0)
    return d


def create_summary_pdf(table, period, totals, filters):
    """Buat PDF ringkasan per customer; tanpa Excel/CSV."""
    from io import BytesIO
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, KeepTogether
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    font = "Helvetica"
    font_bold = "Helvetica-Bold"
    font_candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ]
    for regular_path, bold_path in font_candidates:
        if os.path.isfile(regular_path) and os.path.isfile(bold_path):
            try:
                pdfmetrics.registerFont(TTFont("CollectionBody", regular_path))
                pdfmetrics.registerFont(TTFont("CollectionBold", bold_path))
                font, font_bold = "CollectionBody", "CollectionBold"
                break
            except Exception:
                pass

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=29,
                            rightMargin=29, topMargin=36, bottomMargin=38)
    available_width = landscape(A4)[0] - 58
    style_title = ParagraphStyle("title", fontName=font_bold, fontSize=15, leading=19, spaceAfter=8)
    style_text = ParagraphStyle("body", fontName=font, fontSize=8, leading=11)
    style_small = ParagraphStyle("small", fontName=font, fontSize=7.2, leading=10)
    style_name = ParagraphStyle("name", parent=style_small, alignment=TA_LEFT)
    style_money = ParagraphStyle("money", parent=style_small, alignment=TA_RIGHT)
    style_header = ParagraphStyle("header", fontName=font_bold, fontSize=7.1, leading=9.2, textColor=colors.white)
    elements = [
        Paragraph("RINGKASAN COLLECTION PER CUSTOMER", style_title),
        Paragraph(f"Periode Collection: {escape(period)} | {escape(filters)}", style_text),
        Spacer(1, 11),
    ]
    kpi_labels = ["Tagihan jatuh tempo", "Collection aktual", "Outstanding saat ini", "Collection tanpa PPN"]
    kpi_values = [rupiah(n) for n in totals]
    kpis = Table([[Paragraph(escape(label), style_small) for label in kpi_labels],
                  [Paragraph(f"<b>{escape(value)}</b>", style_money) for value in kpi_values]],
                 colWidths=[available_width/4]*4)
    kpis.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F2F5F8")),
        ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#D5DCE3")),
        ("INNERGRID", (0, 0), (-1, -1), .25, colors.HexColor("#D5DCE3")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.extend([kpis, Spacer(1, 13)])

    headings = ["No.", "Customer", "Jatuh Tempo Belum Lunas", "Collection Aktual", "Outstanding", "Collection Tanpa PPN"]
    data = [[Paragraph(escape(h), style_header) for h in headings]]
    for item in table.itertuples(index=False):
        data.append([
            Paragraph(str(item.No), style_small),
            Paragraph(escape(str(item.Customer)), style_name),
            Paragraph(escape(rupiah(item.Jatuh_Tempo_Belum_Lunas)), style_money),
            Paragraph(escape(rupiah(item.Collection_Bulan)), style_money),
            Paragraph(escape(rupiah(item.Outstanding)), style_money),
            Paragraph(escape(rupiah(item.Tanpa_PPN_Bulan)), style_money),
        ])
    widths = [31, 215, 137, 124, 125, available_width - 31 - 215 - 137 - 124 - 125]
    grid = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    grid.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#183149")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FA")]),
        ("LINEBELOW", (0, 0), (-1, 0), .6, colors.HexColor("#183149")),
        ("LINEBELOW", (0, 1), (-1, -1), .2, colors.HexColor("#E2E6EA")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(grid)
    elements.extend([
        Spacer(1, 12),
        Paragraph("Catatan: jatuh tempo dihitung dari Balance terkini untuk invoice dengan Jth_Tempo sampai akhir periode. "
                  "Collection mengikuti Payment_Date bulan terpilih. Collection tanpa PPN adalah alokasi proporsional.", style_small),
    ])

    def footer(canvas, pdf_doc):
        canvas.setFont(font, 8)
        canvas.setFillColor(colors.HexColor("#687782"))
        canvas.drawString(29, 20, "Dashboard Collection - Khusus Direksi")
        canvas.drawRightString(landscape(A4)[0] - 29, 20, f"Halaman {pdf_doc.page}")

    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def fmt_table(df, cols):
    d = df[cols].copy()
    for col in ["Tagihan", "Jatuh Tempo Belum Lunas", "Collection Aktual", "Outstanding", "Collection Tanpa PPN", "Pembayaran Tercatat"]:
        if col in d:
            d[col] = d[col].map(rupiah)
    return d


st.title("💳 Dashboard Collection")
try:
    with st.spinner("Memuat Sales Report..."):
        raw = load_sales_report()
    if raw is None or raw.empty:
        st.warning("Sales Report kosong atau belum dapat dibaca.")
        st.stop()
    df = prepare(raw)
except Exception as exc:
    st.error(f"Gagal memproses data Collection: {exc}")
    st.stop()
if df.empty:
    st.warning("Tidak ada data yang sesuai.")
    st.stop()

# Filter Periode Collection hanya mengikuti Payment_Date sampai bulan berjalan.
# Jth_Tempo tetap dipakai khusus untuk menghitung tagihan jatuh tempo,
# tetapi tidak boleh memperpanjang pilihan periode hingga tahun mendatang.
current_month = pd.Timestamp.today().to_period("M")
valid_payment_dates = df.loc[
    df["Payment_Date"].notna()
    & df["Payment_Date"].le(current_month.end_time),
    "Payment_Date",
]
first = valid_payment_dates.min().to_period("M") if not valid_payment_dates.empty else current_month
periods = [str(p) for p in pd.period_range(first, current_month, freq="M")][::-1]
default = str(current_month)

with st.expander("🔎 Filter Collection", expanded=True):
    left, right = st.columns(2)
    with left:
        period = st.selectbox("Periode Collection", periods, index=periods.index(default) if default in periods else 0)
        branches = st.multiselect("Branch", sorted(x for x in df["Branch"].unique() if x))
    with right:
        sales = st.multiselect("Sales", sorted(x for x in df["Sales_Name"].unique() if x))
        query = st.text_input("Cari Customer / Invoice", placeholder="Ketik customer atau nomor invoice")

filtered = df.copy()
if branches:
    filtered = filtered[filtered["Branch"].isin(branches)]
if sales:
    filtered = filtered[filtered["Sales_Name"].isin(sales)]
if query.strip():
    found = filtered["Customer"].str.contains(query.strip(), case=False, regex=False, na=False) | filtered["Invoice_ID"].str.contains(query.strip(), case=False, regex=False, na=False)
    selected_names = filtered.loc[found, "Customer"].unique()
    filtered = filtered[filtered["Customer"].isin(selected_names)]

# Pilihan customer ditampilkan DI BAWAH ringkasan seperti versi awal.
# Streamlit menjalankan ulang skrip ketika multiselect berubah; pilihan lama
# dibaca dari session_state sebelum KPI dihitung agar semua KPI ikut terfilter.
customer_options = sorted(filtered["Customer"].dropna().unique().tolist())
customer_widget_key = "collection_detail_customer_selection"
if customer_widget_key not in st.session_state:
    st.session_state[customer_widget_key] = []
# Hindari opsi pilihan yang sudah tidak tersedia setelah filter Branch/Sales.
st.session_state[customer_widget_key] = [
    name for name in st.session_state[customer_widget_key]
    if name in customer_options
]
selected_customers = list(st.session_state[customer_widget_key])
if selected_customers:
    filtered = filtered[filtered["Customer"].isin(selected_customers)].copy()

start = pd.Period(period, freq="M").start_time
end = pd.Period(period, freq="M").end_time
filtered = filtered.copy()
filtered["Jatuh_Tempo_Belum_Lunas"] = filtered["Outstanding"].where(filtered["Jth_Tempo"].notna() & filtered["Jth_Tempo"].le(end), 0.0)
filtered["Collection_Bulan"] = filtered["Pembayaran"].where(filtered["Payment_Date"].between(start, end), 0.0)
filtered["Tanpa_PPN_Bulan"] = filtered["Pembayaran_Tanpa_PPN"].where(filtered["Payment_Date"].between(start, end), 0.0)

st.caption(f"Periode Collection: {period}. Piutang jatuh tempo menggunakan batas {end:%d-%m-%Y}; pembayaran menggunakan tanggal {start:%d-%m-%Y} s.d. {end:%d-%m-%Y}.")
a, b = st.columns(2)
a.metric("Total Tagihan Jatuh Tempo", rupiah(filtered["Jatuh_Tempo_Belum_Lunas"].sum()))
b.metric("Collection Aktual", rupiah(filtered["Collection_Bulan"].sum()))
a, b = st.columns(2)
a.metric("Outstanding Saat Ini", rupiah(filtered["Outstanding"].sum()))
b.metric("Collection Tanpa PPN", rupiah(filtered["Tanpa_PPN_Bulan"].sum()))
st.caption("Piutang jatuh tempo = saldo belum lunas saat ini dengan jatuh tempo sampai bulan pilihan. Outstanding = semua saldo belum lunas saat ini. Collection = pembayaran di bulan pilihan.")

if filtered.empty:
    st.warning("Tidak ada customer sesuai filter.")
    st.stop()

summary_all = filtered.groupby("Customer", as_index=False).agg(
    Tagihan=("Tagihan", "sum"),
    Jatuh_Tempo_Belum_Lunas=("Jatuh_Tempo_Belum_Lunas", "sum"),
    Collection_Bulan=("Collection_Bulan", "sum"),
    Outstanding=("Outstanding", "sum"),
    Tanpa_PPN_Bulan=("Tanpa_PPN_Bulan", "sum"),
)
# Ringkasan hanya customer yang MASIH mempunyai tagihan (Outstanding > 0).
# Customer lunas tetap tersedia pada pilihan detail dan KPI/Collection bulanan.
summary = summary_all.loc[summary_all["Outstanding"] > 0.009].copy()
summary = summary.sort_values(
    ["Jatuh_Tempo_Belum_Lunas", "Outstanding", "Customer"],
    ascending=[False, False, True],
).reset_index(drop=True)
summary.insert(0, "No", range(1, len(summary) + 1))
summary_export = summary.rename(columns={
    "No": "No.", "Jatuh_Tempo_Belum_Lunas": "Jatuh Tempo Belum Lunas",
    "Collection_Bulan": "Collection Aktual", "Tanpa_PPN_Bulan": "Collection Tanpa PPN",
})
st.subheader("Ringkasan per Customer — Masih Memiliki Tagihan")
if summary.empty:
    st.info("Tidak ada customer dengan sisa tagihan pada pilihan filter ini.")
else:
    st.dataframe(fmt_table(
        summary_export,
        ["No.", "Customer", "Jatuh Tempo Belum Lunas", "Collection Aktual", "Outstanding", "Collection Tanpa PPN"],
    ), use_container_width=True, hide_index=True)

try:
    filter_desc = "Branch: " + (", ".join(branches) if branches else "Semua") + " | Sales: " + (", ".join(sales) if sales else "Semua")
    if query.strip():
        filter_desc += " | Cari: " + query.strip()
    if selected_customers:
        filter_desc += " | Customer: " + ", ".join(selected_customers)
    pdf_data = create_summary_pdf(
        summary, period,
        [filtered["Jatuh_Tempo_Belum_Lunas"].sum(), filtered["Collection_Bulan"].sum(),
         filtered["Outstanding"].sum(), filtered["Tanpa_PPN_Bulan"].sum()],
        filter_desc,
    )
    st.download_button("⬇️ Download Ringkasan Customer (PDF)", data=pdf_data,
                       file_name=f"ringkasan_collection_{period}.pdf", mime="application/pdf")
except ImportError:
    st.error("Fitur PDF memerlukan library reportlab. Jalankan: pip install reportlab")
except Exception as exc:
    st.error(f"Gagal membuat laporan PDF: {exc}")

st.divider()
st.subheader("Detail Invoice Customer")
st.multiselect(
    "Customer",
    options=customer_options,
    key=customer_widget_key,
    placeholder="Pilih satu atau beberapa customer",
)
if not selected_customers:
    st.info("Pilih customer di atas untuk menampilkan detail invoice. KPI dan ringkasan tetap menampilkan semua customer sesuai filter lain.")
    st.stop()

st.caption(f"Menampilkan detail {len(selected_customers)} customer terpilih.")
for selected_customer in selected_customers:
    st.subheader(f"Detail Invoice — {selected_customer}")
    rows = filtered[filtered["Customer"].eq(selected_customer)].copy()

    keys = ["Company", "Branch", "Invoice_ID"]
    invoices = rows.groupby(keys, as_index=False, dropna=False).agg(
        Tagihan=("Tagihan", "sum"),
        Jatuh_Tempo_Belum_Lunas=("Jatuh_Tempo_Belum_Lunas", "sum"),
        Collection_Bulan=("Collection_Bulan", "sum"),
        Outstanding=("Outstanding", "sum"),
        Tanpa_PPN_Bulan=("Tanpa_PPN_Bulan", "sum"),
        Tgl_Inv=("Tgl_Inv", "min"),
        Jth_Tempo=("Jth_Tempo", "max"),
    )
    invoices = invoices.sort_values(["Tgl_Inv", "Invoice_ID"], ascending=[False, False], na_position="last")
    st.caption("Invoice diurutkan berdasarkan tanggal invoice terbaru ke terlama. Satu invoice bisa berisi beberapa produk.")
    for rec in invoices.itertuples(index=False):
        due = rec.Jth_Tempo.strftime("%d-%m-%Y") if pd.notna(rec.Jth_Tempo) else "—"
        with st.expander(f"{rec.Invoice_ID} | Jatuh tempo {due} | Sisa {rupiah(rec.Outstanding)}"):
            c1, c2 = st.columns(2)
            c1.metric("Total Invoice", rupiah(rec.Tagihan))
            c2.metric("Outstanding Invoice", rupiah(rec.Outstanding))
            c1, c2 = st.columns(2)
            c1.metric("Collection Bulan Pilihan", rupiah(rec.Collection_Bulan))
            c2.metric("Collection Tanpa PPN", rupiah(rec.Tanpa_PPN_Bulan))
            st.caption(f"Company: {rec.Company or '—'} • Branch: {rec.Branch or '—'} • Jatuh tempo belum lunas: {rupiah(rec.Jatuh_Tempo_Belum_Lunas)}")
            lines = rows[(rows["Company"] == rec.Company) & (rows["Branch"] == rec.Branch) & (rows["Invoice_ID"] == rec.Invoice_ID)].copy()
            lines["Tanggal Bayar"] = lines["Payment_Date"].dt.strftime("%d-%m-%Y").fillna("")
            # Pilih kolom sumber dahulu agar "Produk" bawaan Sales Report
            # tidak bertabrakan dengan label "Produk" untuk Item_Name_Vam.
            detail = lines[[
                "Item_Name_Vam", "Tagihan", "Pembayaran",
                "Outstanding", "Tanggal Bayar", "Acc_Bank",
            ]].copy()
            detail.columns = [
                "Produk", "Tagihan", "Pembayaran Tercatat",
                "Outstanding", "Tanggal Bayar", "Rekening Bank",
            ]
            detail = fmt_table(detail, list(detail.columns))
            st.dataframe(detail, use_container_width=True, hide_index=True)
            st.caption("Pembayaran Tercatat pada rincian produk dapat berasal dari bulan lain; KPI Collection hanya menghitung bulan pilihan.")
