"""Dashboard Collection — customer-first, khusus Direksi.
Simpan sebagai pages/5_Collection.py. Memakai load_sales_report() dari db.py.
"""

import re
import pandas as pd
import streamlit as st
from db import load_sales_report


# Halaman menggunakan st.set_page_config() yang sudah ada di app.py.
if not st.session_state.get('logged_in', False):
    st.error('Silakan login terlebih dahulu.')
    st.stop()

USER_ROLE = str(st.session_state.get('role', '')).strip().lower()
if USER_ROLE not in ('direksi', 'direktur'):
    st.error('Akses ditolak. Collection hanya untuk Direksi.')
    st.stop()


def load_css(path):
    try:
        with open(path, encoding='utf-8') as css_file:
            st.markdown('<style>' + css_file.read() + '</style>', unsafe_allow_html=True)
    except OSError:
        pass


def money(value):
    """Tampilkan rupiah Indonesia, misalnya Rp 1.234.567,89."""
    number = '{:,.2f}'.format(float(value))
    return 'Rp ' + number.replace(',', 'X').replace('.', ',').replace('X', '.')


def jumlah(value):
    return '{:,}'.format(int(value)).replace(',', '.')


def as_money(series):
    """Menerima nilai numerik asli atau angka teks dengan pemisah ribuan."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors='coerce').fillna(0.0)

    def parse(value):
        if pd.isna(value):
            return 0.0
        raw = re.sub(r'[^0-9,.-]', '', str(value).strip())
        if raw in ('', '-', ',', '.'):
            return 0.0
        if ',' in raw and '.' in raw:
            if raw.rfind(',') > raw.rfind('.'):
                raw = raw.replace('.', '').replace(',', '.')
            else:
                raw = raw.replace(',', '')
        elif ',' in raw:
            parts = raw.split(',')
            raw = raw.replace(',', '') if len(parts[-1]) == 3 else raw.replace(',', '.')
        elif raw.count('.') > 1:
            raw = raw.replace('.', '')
        elif '.' in raw and len(raw.split('.')[-1]) == 3:
            raw = raw.replace('.', '')
        try:
            return float(raw)
        except ValueError:
            return 0.0

    return series.map(parse)


def as_date(series):
    """Data sampel memakai M/D/YYYY; angka serial Excel juga didukung."""
    raw = series.astype('string').str.strip()
    dates = pd.to_datetime(raw, format='%m/%d/%Y', errors='coerce')
    remaining = dates.isna() & raw.notna()
    if remaining.any():
        dates.loc[remaining] = pd.to_datetime(
            raw.loc[remaining], format='%Y-%m-%d', errors='coerce'
        )
    serial = pd.to_numeric(raw, errors='coerce')
    use_serial = dates.isna() & serial.between(20000, 80000)
    if use_serial.any():
        dates.loc[use_serial] = pd.to_datetime(
            serial.loc[use_serial], origin='1899-12-30', unit='D', errors='coerce'
        )
    return dates


def prepare_data(source):
    """Satu baris sumber = satu baris item. Tidak menghapus item yang mirip."""
    data = source.copy()
    data.columns = data.columns.astype(str).str.strip()
    needed = ['Cust_Name', 'Net_Ar', 'Balance', 'Payment_Amnt', 'Payment_Date']
    missing = [col for col in needed if col not in data.columns]
    if missing:
        raise ValueError('Kolom wajib tidak ditemukan: ' + ', '.join(missing))

    text_cols = ['Company', 'Branch', 'Sales_Name', 'No_Inv', 'No_SJ',
                 'Index', 'Cust_Name', 'Periode', 'Tanda', 'Ket_Bayar',
                 'Item_Name_Vam', 'KeyItem', 'Acc_Bank']
    for col in text_cols:
        if col not in data.columns:
            data[col] = ''
        data[col] = data[col].fillna('').astype(str).str.strip()
    for col in ('Net_Ar', 'Balance', 'Payment_Amnt'):
        data[col] = as_money(data[col])
    for col in ('Payment_Date', 'Tgl_Inv', 'Jth_Tempo'):
        if col not in data.columns:
            data[col] = pd.NaT
        else:
            data[col] = as_date(data[col])

    data['Tanda'] = data['Tanda'].str.upper()
    data = data[data['Tanda'].isin(['V', 'VAM', ''])].copy()
    data = data[data['Cust_Name'].str.len().gt(0)].copy()
    data['Customer_Key'] = (
        data['Cust_Name'].str.upper().str.replace(r'\s+', ' ', regex=True).str.strip()
    )
    data['Company'] = data['Company'].str.upper()
    data['Branch'] = data['Branch'].str.upper()
    data['Sales_Name'] = data['Sales_Name'].str.upper()
    # Format tampilan Periode Invoice: YYYYMM -> YYYY-MM.
    # Nilai lain dibiarkan apa adanya; nomor invoice tidak diubah.
    data['Periode'] = data['Periode'].str.replace(r'\.0$', '', regex=True)
    data['Periode'] = data['Periode'].str.replace(
        r'^(\d{4})(0[1-9]|1[0-2])$', r'\1-\2', regex=True
    )

    # Invoice kosong atau '-' jangan digabungkan dengan invoice lain:
    # fallback No_SJ; bila sama-sama kosong, gunakan identitas baris sumber.
    inv_ok = ~data['No_Inv'].str.upper().isin(['', '-', 'NAN', 'NONE'])
    sj_ok = ~data['No_SJ'].str.upper().isin(['', '-', 'NAN', 'NONE'])
    data['Invoice_Key'] = data['No_Inv']
    data.loc[~inv_ok & sj_ok, 'Invoice_Key'] = 'SJ: ' + data.loc[~inv_ok & sj_ok, 'No_SJ']
    no_reference = ~inv_ok & ~sj_ok
    data.loc[no_reference, 'Invoice_Key'] = 'BARIS: ' + data.index[no_reference].astype(str)

    # Nilai dibukukan per item, sehingga untuk satu invoice multi-item HARUS dijumlah.
    # Collection hanya berasal dari baris dengan tanggal pembayaran valid.
    data['Collection'] = data['Payment_Amnt'].where(
        data['Payment_Date'].notna() & (data['Payment_Amnt'] > 0), 0.0
    )
    data['Tagihan'] = data['Net_Ar'].clip(lower=0)
    data['Outstanding'] = data['Balance'].clip(lower=0)
    return data


def customer_rollup(data):
    return (data.groupby('Customer_Key', as_index=False, dropna=False)
            .agg(Tagihan=('Tagihan', 'sum'),
                 Collection=('Collection', 'sum'),
                 Outstanding=('Outstanding', 'sum'),
                 Invoice=('Invoice_Key', 'nunique'),
                 Baris_Item=('Invoice_Key', 'size'))
            .rename(columns={'Customer_Key': 'Customer'})
            .sort_values(['Outstanding', 'Customer'], ascending=[False, True])
            .reset_index(drop=True))


def invoice_rollup(data):
    keys = ['Customer_Key', 'Company', 'Branch', 'Invoice_Key']
    result = (data.groupby(keys, as_index=False, dropna=False)
              .agg(Sales=('Sales_Name', 'first'),
                   Nomor_Invoice=('No_Inv', 'first'),
                   Tanggal_Invoice=('Tgl_Inv', 'min'),
                   Jatuh_Tempo=('Jth_Tempo', 'max'),
                   Tagihan=('Tagihan', 'sum'),
                   Collection=('Collection', 'sum'),
                   Outstanding=('Outstanding', 'sum'),
                   Jumlah_Item=('Invoice_Key', 'size')))
    result['Nomor_Invoice'] = result['Nomor_Invoice'].where(
        ~result['Nomor_Invoice'].str.upper().isin(['', '-', 'NAN']), result['Invoice_Key']
    )
    result['Status'] = result.apply(
        lambda row: 'Lunas' if row.Outstanding <= 0.01
        else ('Sebagian Bayar' if row.Collection > 0 else 'Belum Bayar'), axis=1
    )
    return result


load_css('assets/style.css')
st.title('💳 Dashboard Collection')
st.caption('Ringkasan pembayaran dan piutang berdasarkan customer. Khusus Direksi.')

# Pengambilan data mengikuti Sales Performance; tidak membuat koneksi baru.
with st.spinner('Memuat Sales Report...'):
    try:
        source = load_sales_report()
    except Exception as exc:
        st.error(f'Gagal memuat Sales Report: {exc}')
        st.stop()
if source is None or source.empty:
    st.error('Sales Report kosong. Periksa data pada halaman Sales Performance.')
    st.stop()

try:
    df = prepare_data(source)
except Exception as exc:
    st.error(f'Data Sales Report belum dapat diproses: {exc}')
    st.stop()

if df.empty:
    st.warning('Tidak ada baris data setelah penyaringan Tanda (V/VAM/kosong).')
    st.stop()

# Pilihan filter sederhana; hanya memengaruhi data customer yang terlihat.
with st.expander('🔍 Filter & Cari Customer', expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        f_branch = st.multiselect('Branch', sorted(df['Branch'].unique().tolist()))
    with col2:
        f_periode = st.multiselect('Periode Invoice', sorted(df['Periode'].unique().tolist(), reverse=True))
    with col3:
        f_sales = st.multiselect('Sales', sorted(df['Sales_Name'].unique().tolist()))
    search = st.text_input('Cari customer atau nomor invoice', placeholder='Ketik nama customer / nomor invoice...')
    only_outstanding = st.checkbox('Hanya customer yang masih memiliki outstanding', value=False)

visible = df.copy()
for name, values in [('Branch', f_branch), ('Periode', f_periode), ('Sales_Name', f_sales)]:
    if values:
        visible = visible[visible[name].isin(values)].copy()

if search.strip():
    # Bila pencarian cocok dengan nomor invoice, munculkan seluruh item untuk
    # customer tersebut; jangan menghilangkan invoice lainnya dari ringkasan customer.
    query = search.strip()
    matching = visible[
        visible['Customer_Key'].str.contains(query, case=False, regex=False, na=False)
        | visible['No_Inv'].str.contains(query, case=False, regex=False, na=False)
        | visible['Invoice_Key'].str.contains(query, case=False, regex=False, na=False)
    ]['Customer_Key'].unique()
    visible = visible[visible['Customer_Key'].isin(matching)].copy()

customers = customer_rollup(visible)
if only_outstanding:
    customers = customers[customers['Outstanding'] > 0.01].copy()
    visible = visible[visible['Customer_Key'].isin(customers['Customer'])].copy()

st.caption('Tagihan = jumlah Net_Ar per item • Collection = jumlah Payment_Amnt dengan Payment_Date valid • Outstanding = jumlah Balance per item.')

# KPI dua baris agar angka rupiah tidak terpotong di layar desktop.
k1, k2 = st.columns(2)
k1.metric('Total Tagihan', money(customers['Tagihan'].sum()))
k2.metric('Collection', money(customers['Collection'].sum()))

k3, k4 = st.columns(2)
k3.metric('Outstanding', money(customers['Outstanding'].sum()))
k4.metric('Customer / Invoice', f"{jumlah(len(customers))} / {jumlah(customers['Invoice'].sum())}")

st.divider()
st.subheader('📋 Ringkasan per Customer')
if customers.empty:
    st.info('Tidak ada customer sesuai filter. Ubah filter atau pencarian.')
    st.stop()

view = customers[['Customer', 'Invoice', 'Tagihan', 'Collection', 'Outstanding']].copy()
view.insert(0, 'No', range(1, len(view) + 1))
# Format uang hanya pada tabel yang terlihat, data dasar dan ekspor CSV tetap numerik.
view_display = view.copy()
for column in ('Tagihan', 'Collection', 'Outstanding'):
    view_display[column] = view_display[column].map(money)
view_display['Invoice'] = view_display['Invoice'].map(jumlah)
st.dataframe(
    view_display, hide_index=True, use_container_width=True, height=380,
    column_config={
        'No': st.column_config.NumberColumn('No', format='%d'),
        'Invoice': 'Jumlah Invoice',
        'Tagihan': 'Total Tagihan',
        'Collection': 'Collection',
        'Outstanding': 'Outstanding',
    }
)

st.subheader('🔎 Detail Customer')
choice = st.selectbox('Pilih customer untuk melihat semua invoice dan produk', customers['Customer'].tolist())
selected = visible[visible['Customer_Key'] == choice].copy()
selected_inv = invoice_rollup(selected).sort_values(
    ['Outstanding', 'Tanggal_Invoice'], ascending=[False, False]
)

st.caption(f"{len(selected_inv)} invoice • {len(selected)} baris produk")
for _, inv in selected_inv.iterrows():
    group = selected[
        (selected['Company'] == inv['Company'])
        & (selected['Branch'] == inv['Branch'])
        & (selected['Invoice_Key'] == inv['Invoice_Key'])
    ].copy()
    title = f"{inv['Nomor_Invoice']}  |  {inv['Status']}  |  Outstanding {money(inv['Outstanding'])}"
    with st.expander(title, expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric('Tagihan', money(inv['Tagihan']))
        c2.metric('Collection', money(inv['Collection']))
        c3.metric('Outstanding', money(inv['Outstanding']))
        date_inv = inv['Tanggal_Invoice']
        due = inv['Jatuh_Tempo']
        st.caption(
            f"Company: {inv['Company']} • Branch: {inv['Branch']} • Sales: {inv['Sales']} • "
            f"Tanggal invoice: {date_inv.strftime('%d-%m-%Y') if pd.notna(date_inv) else '-'} • "
            f"Jatuh tempo: {due.strftime('%d-%m-%Y') if pd.notna(due) else '-'}"
        )
        items = group[['Item_Name_Vam', 'KeyItem', 'Tagihan', 'Collection',
                       'Outstanding', 'Payment_Date', 'Acc_Bank']].copy()
        items = items.rename(columns={
            'Item_Name_Vam': 'Produk', 'KeyItem': 'Kode Item',
            'Payment_Date': 'Tanggal Bayar', 'Acc_Bank': 'Rekening Bank'
        })
        items['Tanggal Bayar'] = items['Tanggal Bayar'].dt.strftime('%d-%m-%Y').fillna('')
        for column in ('Tagihan', 'Collection', 'Outstanding'):
            items[column] = items[column].map(money)
        st.dataframe(items, hide_index=True, use_container_width=True)

# st.divider()
# col_a, col_b = st.columns(2)
# with col_a:
#     st.download_button('📥 Download Ringkasan Customer',
#         data=view.to_csv(index=False).encode('utf-8-sig'),
#         file_name='Collection_per_Customer.csv', mime='text/csv',
#         use_container_width=True)
# with col_b:
#     exported = invoice_rollup(visible)
#     st.download_button('📥 Download Ringkasan Invoice',
#         data=exported.to_csv(index=False).encode('utf-8-sig'),
#         file_name='Collection_per_Invoice.csv', mime='text/csv',
#         use_container_width=True)

# with st.expander('ℹ️ Catatan validasi data', expanded=False):
#     st.write('Dasar perhitungan adalah baris produk pada Sales Report. Invoice yang sama '
#              'dikelompokkan berdasarkan customer, company, branch, dan nomor invoice.')
#     st.write('Jika No_Inv kosong, kode memakai No_SJ sebagai pengganti. '
#              'Jika keduanya kosong, baris diperlakukan sebagai identitas terpisah.')
#     st.write('Pembayaran dianggap masuk bila Payment_Amnt positif dan Payment_Date valid. '
#              'Jika Payment_Amnt merupakan akumulasi transaksi yang diperbarui dari waktu ke waktu, '
#              'total collection historis perlu direkonsiliasi dengan mutasi bank.')
#     st.write('Outstanding adalah saldo pada Sales Report saat data dimuat, '
#              'bukan saldo historis pada tanggal pembayaran.')
#     st.write('Data dengan Tanda di luar V, VAM, atau kosong tidak ditampilkan.')
