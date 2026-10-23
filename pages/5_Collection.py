"""Dashboard Collection — versi Collection Aktual kompatibel kode awal.

Collection Aktual = SUM(Payment_Amnt positif untuk Payment_Date pada periode),
setelah filter dan tanpa penghapusan otomatis baris pembayaran.
Margin Collection (estimasi) dialokasikan dari Total_COGS per invoice.
"""
import re
import pandas as pd
import streamlit as st
from db import load_collection
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
    """Membaca nominal uang dari format Indonesia dan internasional."""
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
    # Format data Collection adalah DD/MM/YYYY (contoh: 09/10/2026 = 9 Oktober).

    # Dahulukan hari/bulan; format Amerika hanya cadangan untuk tanggal >12 di posisi kedua.

    result = pd.to_datetime(vals, format="%d/%m/%Y", errors="coerce")
    missing = result.isna()
    result.loc[missing] = pd.to_datetime(vals.loc[missing], format="%Y-%m-%d", errors="coerce")
    missing = result.isna()
    result.loc[missing] = pd.to_datetime(vals.loc[missing], format="%m/%d/%Y", errors="coerce")
    nums = pd.to_numeric(vals, errors="coerce")
    excel = result.isna() & nums.between(20000, 80000)
    result.loc[excel] = pd.to_datetime(nums.loc[excel], origin="1899-12-30", unit="D", errors="coerce")
    return result
def prepare(source):
    d = source.copy()
    d.columns = d.columns.map(lambda x: str(x).strip())
    needed = ["Cust_Name", "Net_Ar", "Balance", "Jth_Tempo", "Payment_Date", "Payment_Amnt", "Net_Sales_Amnt_Excl_Ppn", "Net_Sales_Amnt_Incl_Ppn", "Total_COGS"]
    absent = [x for x in needed if x not in d]
    if absent:
        raise ValueError("Kolom wajib tidak ditemukan: " + ", ".join(absent))
    text_cols = ["No_Inv", "No_SJ", "Cust_Name", "Company", "Branch", "Sales_Name", "Item_Name_Vam", "KeyItem", "Acc_Bank", "Ket_Bayar", "Tanda", "Batch_Number"]
    for col in text_cols:
        if col not in d:
            d[col] = ""
        d[col] = d[col].fillna("").astype(str).str.strip()
    for col in ["Total_Amnt", "Ppn"]:

        if col not in d:

            raise ValueError(f"Kolom wajib detail invoice tidak ditemukan: {col}")
    for col in ["Net_Ar", "Balance", "Payment_Amnt", "Net_Sales_Amnt_Excl_Ppn", "Net_Sales_Amnt_Incl_Ppn", "Total_Amnt", "Ppn", "Total_COGS"]:
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
    # Sumber data per item. Total_COGS = COGS/kg * Tot_Qty_Kg.
    # Data pembayaran kadang diulang pada beberapa item dari invoice yang sama.
    invoice_keys = ["Customer", "Company", "Branch", "Invoice_ID"]
    item_keys = ["Item_Name_Vam", "KeyItem", "Batch_Number", "Tot_Qty_Kg", "Total_COGS"]
    for col in ["Tot_Qty_Kg", "COGS"]:
        if col not in d:
            d[col] = 0.0
        d[col] = d[col].map(to_number)
    d["_source_row"] = range(len(d))
    def aggregate_invoice(g):
        # Identifikasi pengulangan baris item lintas pembayaran.
        # Baris item dengan kunci identik tetap dipertahankan jika tidak ada
        # bukti berasal dari beberapa event pembayaran berbeda.
        item_fingerprint = ["Item_Name_Vam", "KeyItem", "Batch_Number", "Tot_Qty_Kg", "Total_COGS", "Total_Amnt"]
        repeated = False
        for _, part in g.groupby(item_fingerprint, dropna=False):
            pay_variants = part.loc[part["Payment_Amnt"].gt(0), ["Payment_Date", "Payment_Amnt"]].drop_duplicates()
            if len(pay_variants) > 1:
                repeated = True
                break
        items = g.drop_duplicates(item_fingerprint) if repeated else g
        # Penjualan: seluruh nilai sama kemungkinan invoice-level diulang;
        # bila berbeda, diasumsikan dicatat per item.
        def basis(col):
            v = items[col]
            nz = v[v.abs().gt(.009)]
            if nz.empty:
                return 0.0
            return float(nz.iloc[0] if (nz - nz.iloc[0]).abs().max() < .01 else v.sum())
        excl = basis("Net_Sales_Amnt_Excl_Ppn")
        incl = basis("Net_Sales_Amnt_Incl_Ppn")
        cogs = float(items["Total_COGS"].sum())
        return pd.Series({"Invoice_Net_Excl":excl, "Invoice_Net_Incl":incl,
                          "Invoice_COGS":cogs, "Item_Replicated_By_Payment":repeated})
    inv = d.groupby(invoice_keys,dropna=False).apply(aggregate_invoice).reset_index()
    inv["Sales_Ratio"] = inv["Invoice_Net_Excl"] / inv["Invoice_Net_Incl"].replace(0,float("nan"))
    inv["Cost_Ratio"] = inv["Invoice_COGS"] / inv["Invoice_Net_Incl"].replace(0,float("nan"))
    inv["Margin_Ratio"] = inv["Sales_Ratio"] - inv["Cost_Ratio"]
    inv["Margin_Valid"] = (inv["Invoice_Net_Incl"] > 0) & (inv["Invoice_Net_Excl"] > 0) & (inv["Invoice_COGS"] >= 0)
    d = d.merge(inv[invoice_keys + ["Sales_Ratio", "Cost_Ratio", "Margin_Ratio", "Margin_Valid", "Item_Replicated_By_Payment"]], on=invoice_keys, how="left",validate="many_to_one")
    # PERTAHANKAN LOGIKA COLLECTION AKTUAL VERSI AWAL:
    # semua Payment_Amnt positif dengan Payment_Date valid dihitung per baris.
    # Tidak ada penghapusan otomatis berdasarkan kesamaan transaksi / item.
    # Rasio margin tetap dihitung berdasarkan agregasi COGS invoice.
    d["Pembayaran_Raw"] = d["Pembayaran"]
    d["Payment_Repeat_Item"] = False
    d["Margin_Pembayaran"] = d["Pembayaran"] * d["Margin_Ratio"].fillna(0)
    d["COGS_Pembayaran"] = d["Pembayaran"] * d["Cost_Ratio"].fillna(0)
    d["PPN_Pembayaran"] = d["Pembayaran"] * (1-d["Sales_Ratio"].fillna(0))
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
    kpi_labels = ["Tagihan jatuh tempo", "Collection aktual", "Outstanding saat ini", "Margin Collection"]
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
    headings = ["No.", "Customer", "Jatuh Tempo Belum Lunas", "Collection Aktual", "Outstanding", "Margin Collection"]
    data = [[Paragraph(escape(h), style_header) for h in headings]]
    for item in table.itertuples(index=False):
        data.append([
            Paragraph(str(item.No), style_small),
            Paragraph(escape(str(item.Customer)), style_name),
            Paragraph(escape(rupiah(item.Jatuh_Tempo_Belum_Lunas)), style_money),
            Paragraph(escape(rupiah(item.Collection_Bulan)), style_money),
            Paragraph(escape(rupiah(item.Outstanding)), style_money),
            Paragraph(escape(rupiah(item.Margin_Bulan)), style_money),
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
                  "Collection mengikuti Payment_Date bulan terpilih. Margin Collection = pembayaran dikali (penjualan tanpa PPN dikurangi Total_COGS), dibagi penjualan termasuk PPN.", style_small),
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
    for col in ["Tagihan", "Jatuh Tempo Belum Lunas", "Collection Aktual", "Outstanding", "Margin Collection", "Pembayaran Tercatat"]:
        if col in d:
            d[col] = d[col].map(rupiah)
    return d
st.title("💳 Dashboard Collection")
try:
    with st.spinner("Memuat Data Collection..."):
        raw = load_collection()
    if raw is None or raw.empty:
        st.warning("Data Collection kosong atau belum dapat dibaca.")
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
# Penting: sumber tab 2025 mungkin tidak memuat tagihan/pembayaran tahun 2026.

latest_dates = pd.concat([df["Jth_Tempo"], df["Payment_Date"], df["Tgl_Inv"]]).dropna()

if not latest_dates.empty and latest_dates.max().year < current_month.year:

    st.warning(

        f"Data Collection yang dimuat memiliki tanggal terakhir {latest_dates.max():%d-%m-%Y}. "

        f"KPI sampai {current_month.end_time:%d-%m-%Y} tidak akan lengkap bila "

        "transaksi tahun berjalan berada di tab/file lain."

    )
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
filtered["Margin_Bulan"] = filtered["Margin_Pembayaran"].where(filtered["Payment_Date"].between(start, end) & filtered["Margin_Valid"].fillna(False), 0.0)
filtered["COGS_Bulan"] = filtered["COGS_Pembayaran"].where(filtered["Payment_Date"].between(start, end), 0.0)
filtered["PPN_Bulan"] = filtered["PPN_Pembayaran"].where(filtered["Payment_Date"].between(start, end), 0.0)
active_payments = filtered["Collection_Bulan"].gt(0)
valid_payments = active_payments & filtered["Margin_Valid"].fillna(False)
invalid_payments = active_payments & ~valid_payments
margin_amount = filtered.loc[valid_payments,"Margin_Bulan"].sum()
collection_amount = filtered["Collection_Bulan"].sum()
st.caption(f"Periode Collection: {period}. Piutang jatuh tempo sampai {end:%d-%m-%Y}; pembayaran {start:%d-%m-%Y} s.d. {end:%d-%m-%Y}.")
a,b = st.columns(2)
a.metric("Total Tagihan Jatuh Tempo",rupiah(filtered["Jatuh_Tempo_Belum_Lunas"].sum()))
b.metric("Collection Aktual",rupiah(collection_amount))
a,b = st.columns(2)
a.metric("Outstanding Saat Ini",rupiah(filtered["Outstanding"].sum()))
b.metric("Margin Collection",rupiah(margin_amount))
with st.expander("Rincian Margin Collection",expanded=True):
    st.write(f"**Collection termasuk PPN:** {rupiah(collection_amount)}")
    st.write(f"**Alokasi PPN:** {rupiah(filtered.loc[valid_payments,'PPN_Bulan'].sum())}")
    st.write(f"**Alokasi Total COGS:** {rupiah(filtered.loc[valid_payments,'COGS_Bulan'].sum())}")
    st.write(f"**Margin Collection:** {rupiah(margin_amount)}")
    omitted = filtered.loc[invalid_payments,"Collection_Bulan"].sum()
    if omitted > .01:
        st.warning(f"Ada {rupiah(omitted)} pembayaran yang dasar penjualan invoice-nya kosong/tidak valid; "
                   "pembayaran tersebut tetap masuk Collection Aktual, tetapi belum masuk perhitungan Margin Collection.")
if filtered.empty:
    st.warning("Tidak ada customer sesuai filter.")
    st.stop()
summary_all = filtered.groupby("Customer", as_index=False).agg(
    Tagihan=("Tagihan", "sum"),
    Jatuh_Tempo_Belum_Lunas=("Jatuh_Tempo_Belum_Lunas", "sum"),
    Collection_Bulan=("Collection_Bulan", "sum"),
    Outstanding=("Outstanding", "sum"),
    Margin_Bulan=("Margin_Bulan", "sum"),
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
    "Collection_Bulan": "Collection Aktual", "Margin_Bulan": "Margin Collection",
})
st.subheader("Ringkasan per Customer — Masih Memiliki Tagihan")
if summary.empty:
    st.info("Tidak ada customer dengan sisa tagihan pada pilihan filter ini.")
else:
    st.dataframe(fmt_table(
        summary_export,
        ["No.", "Customer", "Jatuh Tempo Belum Lunas", "Collection Aktual", "Outstanding"] + ["Margin Collection"],
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
         filtered["Outstanding"].sum(), filtered["Margin_Bulan"].sum()],
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

    st.info("Pilih customer untuk melihat dua tabel: Collection dan Tagihan.")

    st.stop()
# Filter customer dari kode utama sudah diterapkan sebelum menghitung KPI.

# Invoice dapat muncul pada kedua tabel apabila baru dibayar sebagian.
def tanggal_tergabung(values):

    dates = pd.Series(values).dropna().drop_duplicates().sort_values()

    return ", ".join(dates.dt.strftime("%d-%m-%Y")) if not dates.empty else "—"
def bentuk_tabel_invoice(rows, pembayaran_only=False):

    """Satu baris per customer + perusahaan + cabang + invoice."""

    if rows.empty:

        return pd.DataFrame(columns=[

            "Customer", "Company", "Branch", "Invoice_ID", "Tgl_Inv",

            "Jth_Tempo", "Total_Amnt", "Ppn", "Payment_Date",

            "Payment_Amnt", "Balance", "Payment_Date_Sort",

        ])

    if pembayaran_only:

        # Tanggal dan nominal hanya pembayaran pada bulan pilihan.

        # Informasi total invoice dan balance tetap diperoleh dari seluruh baris.

        base = filtered.groupby(

            ["Customer", "Company", "Branch", "Invoice_ID"],

            as_index=False, dropna=False,

        ).agg(

            Tgl_Inv=("Tgl_Inv", "min"),

            Jth_Tempo=("Jth_Tempo", "max"),

            Total_Amnt=("Total_Amnt", "sum"),

            Ppn=("Ppn", "sum"),

            Balance=("Outstanding", "sum"),

        )

        paid = rows.groupby(

            ["Customer", "Company", "Branch", "Invoice_ID"],

            as_index=False, dropna=False,

        ).agg(

            Payment_Date=("Payment_Date", tanggal_tergabung),

            Payment_Date_Sort=("Payment_Date", "max"),

            Payment_Amnt=("Collection_Bulan", "sum"),

        )

        return base.merge(paid, on=["Customer", "Company", "Branch", "Invoice_ID"], how="inner")
    return rows.groupby(

        ["Customer", "Company", "Branch", "Invoice_ID"],

        as_index=False, dropna=False,

    ).agg(

        Tgl_Inv=("Tgl_Inv", "min"),

        Jth_Tempo=("Jth_Tempo", "max"),

        Total_Amnt=("Total_Amnt", "sum"),

        Ppn=("Ppn", "sum"),

        Payment_Date=("Payment_Date", tanggal_tergabung),

        Payment_Amnt=("Payment_Amnt", "sum"),

        Balance=("Outstanding", "sum"),

    )
def tampilkan_invoice(data, sort_cols, ascending):

    display = data.sort_values(

        sort_cols, ascending=ascending, na_position="last"

    ).reset_index(drop=True).copy()

    display = display.rename(columns={

        "Invoice_ID": "No. Invoice",

        "Tgl_Inv": "Tanggal Invoice",

        "Jth_Tempo": "Jatuh Tempo",

        "Total_Amnt": "Total Amount",

        "Ppn": "PPN",

        "Payment_Date": "Payment Date",

        "Payment_Amnt": "Payment Amount",

        "Balance": "Balance",

    })

    for col in ["Tanggal Invoice", "Jatuh Tempo"]:

        display[col] = display[col].dt.strftime("%d-%m-%Y").fillna("—")

    for col in ["Total Amount", "PPN", "Payment Amount", "Balance"]:

        display[col] = display[col].map(rupiah)

    display.insert(0, "No.", range(1, len(display) + 1))

    return display[[

        "No.", "Customer", "No. Invoice", "Tanggal Invoice", "Jatuh Tempo",

        "Company", "Branch", "Total Amount", "PPN", "Payment Date",

        "Payment Amount", "Balance",

    ]]
def create_tagihan_pdf(display_table, periode, balance_total, customer_names):

    """Ekspor tampilan tabel tagihan ke PDF landscape A3 (multi-halaman)."""

    from io import BytesIO

    from xml.sax.saxutils import escape

    from reportlab.lib import colors

    from reportlab.lib.pagesizes import A3, landscape

    from reportlab.lib.styles import ParagraphStyle

    from reportlab.pdfbase import pdfmetrics

    from reportlab.pdfbase.ttfonts import TTFont

    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer

    import os
    regular, bold = "Helvetica", "Helvetica-Bold"

    for font_normal, font_heavy in [

        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),

        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),

    ]:

        if os.path.isfile(font_normal) and os.path.isfile(font_heavy):

            try:

                pdfmetrics.registerFont(TTFont("TagihanRegular", font_normal))

                pdfmetrics.registerFont(TTFont("TagihanBold", font_heavy))

                regular, bold = "TagihanRegular", "TagihanBold"

                break

            except Exception:

                pass
    buffer = BytesIO()

    paper_width, _ = landscape(A3)

    doc = SimpleDocTemplate(

        buffer, pagesize=landscape(A3), leftMargin=25, rightMargin=25,

        topMargin=38, bottomMargin=36,

    )

    usable = paper_width - 50

    title_style = ParagraphStyle("TgTitle", fontName=bold, fontSize=15, leading=19, spaceAfter=10)

    info_style = ParagraphStyle("TgInfo", fontName=regular, fontSize=8.5, leading=12, spaceAfter=7)

    head_style = ParagraphStyle("TgHead", fontName=bold, textColor=colors.white, fontSize=7.0, leading=9)

    cell_style = ParagraphStyle("TgCell", fontName=regular, fontSize=6.9, leading=9)

    elements = [

        Paragraph("DAFTAR TAGIHAN CUSTOMER", title_style),

        Paragraph("Periode pilihan: " + escape(str(periode)) + " | Customer: " + escape(", ".join(customer_names)), info_style),

        Paragraph("Tagihan: seluruh invoice dengan Balance &gt; 0, termasuk yang sudah lewat jatuh tempo. Diurutkan dari jatuh tempo terlama.", info_style),

        Spacer(1, 6),

    ]

    headers = list(display_table.columns)

    data = [[Paragraph(escape(str(h)), head_style) for h in headers]]

    for values in display_table.itertuples(index=False, name=None):

        data.append([Paragraph(escape(str(v)) if v is not None else "", cell_style) for v in values])

    if len(data) == 1:

        data.append([Paragraph("Tidak ada tagihan belum lunas", cell_style)] + ["" for _ in headers[1:]])

    # 12 kolom: nomor, customer, invoice, tanggal invoice, jatuh tempo,

    # company, branch, total amount, PPN, payment date, payment amount, balance.

    width_weights = [3, 14, 13, 8, 8, 7, 7, 10, 9, 10, 10, 11]

    if len(headers) != len(width_weights):

        width_weights = [1] * len(headers)

    col_widths = [usable * x / sum(width_weights) for x in width_weights]

    grid = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")

    grid.setStyle(TableStyle([

        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#19364C")),

        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F5F8")]),

        ("VALIGN", (0, 0), (-1, -1), "TOP"),

        ("TOPPADDING", (0, 0), (-1, -1), 6),

        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),

        ("LEFTPADDING", (0, 0), (-1, -1), 4),

        ("RIGHTPADDING", (0, 0), (-1, -1), 4),

        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#19364C")),

        ("LINEBELOW", (0, 1), (-1, -1), 0.2, colors.HexColor("#DEE4E9")),

    ]))

    elements.append(grid)

    elements.append(Spacer(1, 12))

    elements.append(Paragraph("TOTAL BALANCE CUSTOMER: " + escape(rupiah(balance_total)), title_style))

    elements.append(Paragraph(

        "Catatan: nilai per invoice adalah penjumlahan baris sumber; validasi terhadap duplikasi nominal pada baris produk tetap diperlukan.",

        info_style,

    ))
    def footer(canvas, pdf_doc):

        canvas.setFont(regular, 8)

        canvas.setFillColor(colors.HexColor("#637381"))

        canvas.drawString(25, 19, "Dashboard Collection | Tagihan Customer")

        canvas.drawRightString(paper_width - 25, 19, f"Halaman {pdf_doc.page}")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)

    return buffer.getvalue()
def create_collection_pdf(display_table, periode, payment_total, customer_names):

    """Ekspor tampilan tabel collection ke PDF landscape A3 (multi-halaman)."""

    from io import BytesIO

    from xml.sax.saxutils import escape

    from reportlab.lib import colors

    from reportlab.lib.pagesizes import A3, landscape

    from reportlab.lib.styles import ParagraphStyle

    from reportlab.pdfbase import pdfmetrics

    from reportlab.pdfbase.ttfonts import TTFont

    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer

    import os
    regular, bold = "Helvetica", "Helvetica-Bold"

    for font_normal, font_heavy in [

        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),

        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),

    ]:

        if os.path.isfile(font_normal) and os.path.isfile(font_heavy):

            try:

                pdfmetrics.registerFont(TTFont("CollectionRegular", font_normal))

                pdfmetrics.registerFont(TTFont("CollectionBold", font_heavy))

                regular, bold = "CollectionRegular", "CollectionBold"

                break

            except Exception:

                pass
    buffer = BytesIO()

    paper_width, _ = landscape(A3)

    doc = SimpleDocTemplate(

        buffer, pagesize=landscape(A3), leftMargin=25, rightMargin=25,

        topMargin=38, bottomMargin=36,

    )

    usable = paper_width - 50

    title_style = ParagraphStyle("TgTitle", fontName=bold, fontSize=15, leading=19, spaceAfter=10)

    info_style = ParagraphStyle("TgInfo", fontName=regular, fontSize=8.5, leading=12, spaceAfter=7)

    head_style = ParagraphStyle("TgHead", fontName=bold, textColor=colors.white, fontSize=7.0, leading=9)

    cell_style = ParagraphStyle("TgCell", fontName=regular, fontSize=6.9, leading=9)

    elements = [

        Paragraph("DAFTAR COLLECTION CUSTOMER", title_style),

        Paragraph("Periode pilihan: " + escape(str(periode)) + " | Customer: " + escape(", ".join(customer_names)), info_style),

        Paragraph("Collection: pembayaran dengan Payment Date pada periode pilihan. Diurutkan dari pembayaran terbaru.", info_style),

        Spacer(1, 6),

    ]

    headers = list(display_table.columns)

    data = [[Paragraph(escape(str(h)), head_style) for h in headers]]

    for values in display_table.itertuples(index=False, name=None):

        data.append([Paragraph(escape(str(v)) if v is not None else "", cell_style) for v in values])

    if len(data) == 1:

        data.append([Paragraph("Tidak ada pembayaran dalam periode", cell_style)] + ["" for _ in headers[1:]])

    # 12 kolom: nomor, customer, invoice, tanggal invoice, jatuh tempo,

    # company, branch, total amount, PPN, payment date, payment amount, balance.

    width_weights = [3, 14, 13, 8, 8, 7, 7, 10, 9, 10, 10, 11]

    if len(headers) != len(width_weights):

        width_weights = [1] * len(headers)

    col_widths = [usable * x / sum(width_weights) for x in width_weights]

    grid = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")

    grid.setStyle(TableStyle([

        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#19364C")),

        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F5F8")]),

        ("VALIGN", (0, 0), (-1, -1), "TOP"),

        ("TOPPADDING", (0, 0), (-1, -1), 6),

        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),

        ("LEFTPADDING", (0, 0), (-1, -1), 4),

        ("RIGHTPADDING", (0, 0), (-1, -1), 4),

        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#19364C")),

        ("LINEBELOW", (0, 1), (-1, -1), 0.2, colors.HexColor("#DEE4E9")),

    ]))

    elements.append(grid)

    elements.append(Spacer(1, 12))

    elements.append(Paragraph("TOTAL COLLECTION CUSTOMER: " + escape(rupiah(payment_total)), title_style))

    elements.append(Paragraph(

        "Catatan: nilai per invoice adalah penjumlahan baris sumber; validasi terhadap duplikasi nominal pada baris produk tetap diperlukan.",

        info_style,

    ))
    def footer(canvas, pdf_doc):

        canvas.setFont(regular, 8)

        canvas.setFillColor(colors.HexColor("#637381"))

        canvas.drawString(25, 19, "Dashboard Collection | Collection Customer")

        canvas.drawRightString(paper_width - 25, 19, f"Halaman {pdf_doc.page}")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)

    return buffer.getvalue()
# TABEL 1: Collection: pembayaran positif yang jatuh pada bulan pilihan.

collection_rows = filtered.loc[filtered["Collection_Bulan"].gt(0)].copy()

collection_invoices = bentuk_tabel_invoice(collection_rows, pembayaran_only=True)
st.markdown("#### Collection Customer")

st.caption(

    f"Pembayaran masuk selama {start:%d-%m-%Y} s.d. {end:%d-%m-%Y}; "

    "diurutkan dari Payment Date terbaru. Invoice dibayar sebagian tetap ditampilkan."

)

if collection_invoices.empty:

    st.info("Belum ada pembayaran pada bulan yang dipilih untuk customer ini.")

else:

    st.dataframe(

        tampilkan_invoice(collection_invoices, ["Payment_Date_Sort", "Invoice_ID"], [False, False]),

        use_container_width=True, hide_index=True,

    )

st.metric("Total Collection Customer", rupiah(collection_invoices["Payment_Amnt"].sum()))

try:

    collection_display = tampilkan_invoice(

        collection_invoices, ["Payment_Date_Sort", "Invoice_ID"], [False, False]

    )

    collection_pdf = create_collection_pdf(

        collection_display,

        period,

        collection_invoices["Payment_Amnt"].sum(),

        selected_customers,

    )

    st.download_button(

        "⬇️ Download Collection Customer (PDF)",

        data=collection_pdf,

        file_name=f"collection_customer_{period}.pdf",

        mime="application/pdf", key="download_collection_invoice",

    )

except ImportError:

    st.error("Download PDF memerlukan reportlab. Jalankan: pip install reportlab")

except Exception as exc:

    st.error(f"Gagal membuat PDF Collection Customer: {exc}")
st.divider()

# TABEL 2: Semua tagihan yang masih memiliki saldo, termasuk lewat jatuh tempo.

tagihan_rows = filtered.loc[filtered["Outstanding"].gt(0.009)].copy()

tagihan_invoices = bentuk_tabel_invoice(tagihan_rows)

tagihan_invoices = tagihan_invoices.loc[tagihan_invoices["Balance"].gt(0.009)].copy()

st.markdown("#### Tagihan Customer")

st.caption(

    "Seluruh invoice dengan Balance > 0 (termasuk sudah jatuh tempo). "

    "Diurutkan dari jatuh tempo terlama ke terbaru."

)

if tagihan_invoices.empty:

    st.info("Tidak ada tagihan belum lunas untuk customer ini.")

else:

    st.dataframe(

        tampilkan_invoice(tagihan_invoices, ["Jth_Tempo", "Invoice_ID"], [True, True]),

        use_container_width=True, hide_index=True,

    )

st.metric("Total Balance Customer", rupiah(tagihan_invoices["Balance"].sum()))

try:

    tagihan_display = tampilkan_invoice(tagihan_invoices, ["Jth_Tempo", "Invoice_ID"], [True, True])

    tagihan_pdf = create_tagihan_pdf(

        tagihan_display,

        period,

        tagihan_invoices["Balance"].sum(),

        selected_customers,

    )

    st.download_button(

        "⬇️ Download Tagihan Customer (PDF)",

        data=tagihan_pdf,

        file_name=f"tagihan_customer_{period}.pdf",

        mime="application/pdf",

        key="download_tagihan_invoice",

    )

except ImportError:

    st.error("Download PDF memerlukan reportlab. Jalankan: pip install reportlab")

except Exception as exc:

    st.error(f"Gagal membuat PDF Tagihan Customer: {exc}")

st.caption(

    "Catatan: angka per invoice merupakan penjumlahan baris sumber. "

    "Pastikan Total Amount, PPN, Payment Amount, dan Balance tidak diduplikasi "

    "di beberapa baris produk pada spreadsheet."

)
