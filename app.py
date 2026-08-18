import streamlit as st
from db import load_user_credentials

st.set_page_config(page_title="Dashboard Management", layout="wide")

def load_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

load_css("assets/style.css")

# Memuat data kredensial user
USER_CREDENTIALS = load_user_credentials()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# --- KONDISI KETIKA BELUM LOGIN ---
if not st.session_state.logged_in:
    # Sembunyikan sidebar secara dinamis saat belum login
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {
                display: none !important;
            }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<div style='height: 4vh;'></div>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            st.markdown(
                "<h2 style='text-align: center; color: #0f172a; font-weight: 700; margin-bottom: 8px;'>Dashboard Management</h2>"
                "<p style='text-align: center; color: #64748b; font-size: 14px; margin-bottom: 25px;'>Silakan masuk menggunakan akun Anda</p>", 
                unsafe_allow_html=True
            )
            
            username = st.text_input("Username", placeholder="Masukkan username Anda")
            password = st.text_input("Password", type="password", placeholder="Masukkan password Anda")
            
            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
            
            submit_button = st.form_submit_button("Masuk", use_container_width=True)
            
            if submit_button:
                input_username = username.strip()
                input_password = str(password).strip()
                
                if not USER_CREDENTIALS:
                    st.error("Gagal memuat database user atau database kosong.")
                else:
                    user_dict_lower = {str(k).strip().lower(): v for k, v in USER_CREDENTIALS.items()}
                    
                    if input_username.lower() in user_dict_lower:
                        user_data = user_dict_lower[input_username.lower()]
                        
                        db_password = str(user_data.get("password", "")).strip()
                        if db_password.endswith(".0"):
                            db_password = db_password[:-2]
                        
                        if db_password == input_password:
                            st.session_state.logged_in = True
                            st.session_state.username = input_username
                            st.session_state.role = str(user_data.get("role", "sales")).strip().lower()
                            st.session_state.nama_sales = user_data.get("nama", input_username)
                            st.rerun()
                        else:
                            st.error("Password salah!")
                    else:
                        st.error("Username tidak ditemukan di dalam database user.")
                
    st.stop() 

# --- KONDISI KETIKA SUDAH BERHASIL LOGIN ---
# Sidebar Menu & Informasi Akun
st.sidebar.write(f"Halo, **{st.session_state.get('nama_sales', 'User')}**")
st.sidebar.write(f"Role: **{str(st.session_state.get('role', 'sales')).capitalize()}**")

if st.sidebar.button("Logout", use_container_width=True):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.sidebar.markdown("---")

pages = [
    st.Page("pages/1_Sales_Performance.py", title="Sales Performance"),
    st.Page("pages/2_Sales_Per_Minggu.py", title="Sales Per Minggu"),
    st.Page("pages/3_Report_Activity.py", title="Report Activity"),
    st.Page("pages/4_Stock_All_Branch.py", title="Stock All Branch"),
    # st.Page("pages/5_Piutang.py", title="Piutang"),
    st.Page("pages/6_Pricelist.py", title="Pricelist"),
]

pg = st.navigation(pages)
pg.run()