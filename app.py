import streamlit as st
from db import load_user_credentials

st.set_page_config(page_title="Dashboard Management", layout="wide")


def load_css(file_name):
    try:
        with open(file_name, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"File CSS tidak ditemukan: {file_name}")


load_css("assets/style.css")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    # CSS ini hanya aktif saat halaman login dirender.
    st.markdown(
        '<style>[data-testid="stSidebar"] {display: none !important;}</style>',
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<div style='height: 4vh;'></div>", unsafe_allow_html=True)
        with st.form("login_form"):
            st.markdown(
                "<h2 style='text-align: center; color: #0f172a; font-weight: 700; margin-bottom: 8px;'>Dashboard Management</h2>"
                "<p style='text-align: center; color: #64748b; font-size: 14px; margin-bottom: 25px;'>Silakan masuk menggunakan akun Anda</p>",
                unsafe_allow_html=True,
            )
            username = st.text_input("Username", placeholder="Masukkan username Anda")
            password = st.text_input("Password", type="password", placeholder="Masukkan password Anda")
            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
            submit_button = st.form_submit_button("Masuk", use_container_width=True)

            if submit_button:
                input_username = username.strip()
                input_password = str(password).strip()
                try:
                    user_credentials = load_user_credentials()
                except Exception:
                    user_credentials = None

                if not user_credentials:
                    st.error("Gagal memuat database user atau database kosong.")
                else:
                    user_dict_lower = {
                        str(k).strip().lower(): v for k, v in user_credentials.items()
                    }
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

# Setelah login: buat navigasi lebih dulu agar urutan sidebar konsisten.
user_role = str(st.session_state.get("role", "sales")).strip().lower()

pages = [
    st.Page("pages/1_Sales_Performance.py", title="Sales Performance", default=True),
    st.Page("pages/2_Sales_Per_Minggu.py", title="Sales Per Minggu"),
    st.Page("pages/3_Report_Activity.py", title="Report Activity"),
    st.Page("pages/4_Stock_All_Branch.py", title="Stock All Branch"),
    st.Page("pages/6_Pricelist.py", title="Pricelist"),
]

# Collection hanya tersedia untuk Direksi / Direktur.
if user_role in ("direksi", "direktur"):
    pages.insert(4, st.Page("pages/5_Collection.py", title="Collection"))

pg = st.navigation(pages, position="sidebar", expanded=True)

with st.sidebar:
    st.write(f"Halo, **{st.session_state.get('nama_sales', 'User')}**")
    st.write(f"Role: **{user_role.capitalize()}**")

    # Key khusus agar CSS hanya memberi warna merah pada Logout.
    if st.button("Logout", key="logout_button", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.logged_in = False
        st.rerun()

pg.run()
