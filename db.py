import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_KEY = "1ZMO609rqjm7GvY4CiDrjGBny-AYiopGJDt5nl6kWYj0"

def init_db():
    """Fungsi inisialisasi database (menghilangkan ImportError di app.py)."""
    pass

def _load_gsheet(sheet_key, error_msg):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_key}/export?format=csv"
    try:
        return pd.read_csv(url, on_bad_lines='skip')
    except Exception as e:
        st.error(f"{error_msg}: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_sales_report():
    return _load_gsheet(st.secrets["google_sheets"]["sales_report"], "Gagal memuat Sales Report")

@st.cache_data(ttl=600)
def load_report_activity():
    return _load_gsheet(st.secrets["google_sheets"]["report_activity"], "Gagal memuat Report Activity")

@st.cache_data(ttl=600)
def load_activity_report():
    return load_report_activity()

@st.cache_data(ttl=600)
def load_stock_branch():
    return _load_gsheet(st.secrets["google_sheets"]["stock_branch"], "Gagal memuat Stock")

@st.cache_data(ttl=600)
def load_hpp_pricelist():
    return _load_gsheet(st.secrets["google_sheets"]["hpp_pricelist"], "Gagal memuat HPP/Pricelist")

@st.cache_data(ttl=60)
def load_user_credentials():
    df = _load_gsheet(SHEET_KEY, "Gagal memuat database user")
    if df.empty: 
        return {}
    df.columns = df.columns.astype(str).str.strip()
    user_dict = {}
    for _, row in df.iterrows():
        uname = str(row.get("Username", "")).strip()
        if uname and uname.lower() != "nan":
            user_dict[uname] = {
                "password": str(row.get("Password", "")).strip(),
                "role": str(row.get("Role", "sales")).strip().lower(),
                "nama": str(row.get("Nama", "")).strip()
            }
    return user_dict

def update_password(username, new_password):
    try:
        creds_dict = dict(st.secrets["gcp"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_KEY).sheet1
        
        cell = sheet.find(username)
        if cell:
            header_row = sheet.row_values(1)
            password_col_index = None
            for idx, header in enumerate(header_row, start=1):
                if header.strip().lower() == "password":
                    password_col_index = idx
                    break
            
            if not password_col_index:
                password_col_index = 4 
                
            sheet.update_cell(cell.row, password_col_index, str(new_password)) 
            return True, "Sukses"
        return False, "Username tidak ditemukan di spreadsheet"
    except Exception as e:
        return False, str(e)

def check_role_access(df, sales_column_name="Sales_Name", filter_by_sales=True):
    if "role" not in st.session_state:
        st.session_state.role = "sales"
    
    user_role = str(st.session_state.get("role", "sales")).strip().lower()
    nama_sales = str(st.session_state.get("nama_sales", "")).strip().upper()
    
    if user_role == "sales" and filter_by_sales and sales_column_name in df.columns:
        if nama_sales:
            df = df[df[sales_column_name].astype(str).str.strip().str.upper() == nama_sales]
            
    return df