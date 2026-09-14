# import streamlit as st
# import pandas as pd
# import plotly.express as px
# from db import load_sales_report, check_role_access

# st.set_page_config(
#     page_title="Dashboard Piutang",
#     layout="wide",
#     initial_sidebar_state="auto"
# )

# # ==========================================================
# # LOAD CSS
# # ==========================================================
# def load_css(file_name):
#     try:
#         with open(file_name, encoding="utf-8") as f:
#             st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
#     except FileNotFoundError:
#         pass

# load_css("assets/style.css")

# st.title("💰 Dashboard Piutang Customer")
# st.caption("Menampilkan invoice yang masih memiliki Balance.")

# # ==========================================================
# # FORMAT RUPIAH
# # ==========================================================
# def rupiah(x):
#     try:
#         return f"Rp {float(x):,.0f}".replace(",", ".")
#     except:
#         return "Rp 0"

# # ==========================================================
# # LOAD DATA
# # ==========================================================
# df = load_sales_report()

# if df.empty:
#     st.error("Data Sales Report tidak ditemukan.")
#     st.stop()

# df.columns = df.columns.astype(str).str.strip()

# # Filter akses Sales
# df = check_role_access(df, sales_column_name="Sales_Name")

# # ==========================================================
# # CLEAN DATA
# # ==========================================================
# df["Balance"] = pd.to_numeric(df["Balance"], errors="coerce").fillna(0)
# df["Top_Days"] = pd.to_numeric(df["Top_Days"], errors="coerce").fillna(0)
# df["Jth_Tempo"] = pd.to_datetime(df["Jth_Tempo"], errors="coerce")

# # Bersihkan periode (hilangkan .0)
# df["Periode"] = (
#     df["Periode"]
#     .astype(str)
#     .str.replace(".0", "", regex=False)
# )

# # ==========================================================
# # FILTER TANDA (BELAKANG LAYAR)
# # ==========================================================
# df["Tanda"] = df["Tanda"].fillna("").astype(str).str.strip()

# # Dashboard hanya menampilkan data Tanda = V / v / VAM / Blank
# df = df[df["Tanda"].isin(["V", "v", "VAM", ""])]

# # ==========================================================
# # FILTER KETERANGAN JATUH TEMPO (BELAKANG LAYAR)
# # ==========================================================
# df["Ket_Balance"] = df["Ket_Balance"].fillna("").astype(str).str.strip()

# # Hanya tampilkan:
# # - "0"
# # - "Jatuh Tempo sd ..."
# df = df[
#     (df["Ket_Balance"] == "0")
#     | (df["Ket_Balance"].str.startswith("Jatuh Tempo sd"))
# ]

# # ==========================================================
# # HANYA PIUTANG
# # ==========================================================
# df = df[df["Balance"] > 0].copy()

# today = pd.Timestamp.today().normalize()

# df["Status Tempo"] = df["Jth_Tempo"].apply(
#     lambda x: "Lewat Tempo"
#     if pd.notnull(x) and x < today
#     else "Belum Tempo"
# )

# # ==========================================================
# # KPI
# # ==========================================================
# total_balance = df["Balance"].sum()

# kurang_bayar = df[
#     df["Ket_Bayar"] == "02. Kurang Bayar"
# ]["Balance"].sum()

# belum_bayar = df[
#     df["Ket_Bayar"] == "03. Belum Bayar"
# ]["Balance"].sum()

# invoice = len(df)
# customer = df["Cust_Name"].nunique()

# k1, k2, k3, k4, k5 = st.columns(5)

# k1.metric("💵 Total Balance", rupiah(total_balance))
# k2.metric("🟠 Kurang Bayar", rupiah(kurang_bayar))
# k3.metric("🔴 Belum Bayar", rupiah(belum_bayar))
# k4.metric("📄 Total Invoice", invoice)
# k5.metric("👥 Customer", customer)

# st.markdown("---")

# # ==========================================================
# # FILTER
# # ==========================================================
# with st.expander("🔍 Filter Piutang", expanded=False):

#     c1, c2, c3 = st.columns(3)

#     # ---------- PERIODE ----------
#     with c1:
#         periode_raw = sorted(
#             df["Periode"].dropna().unique(),
#             reverse=True
#         )

#         periode_map = {
#             p: f"{p[:4]}-{p[4:]}"
#             for p in periode_raw
#         }

#         periode = st.multiselect(
#             "Periode",
#             options=periode_raw,
#             format_func=lambda x: periode_map[x],
#             placeholder="Pilih Periode"
#         )

#     # ---------- BRANCH ----------
#     with c2:
#         branch = st.multiselect(
#             "Branch",
#             options=sorted(
#                 df["Branch"]
#                 .dropna()
#                 .astype(str)
#                 .unique()
#             ),
#             placeholder="Pilih Branch"
#         )

#     # ---------- SALES ----------
#     with c3:
#         sales = []

#         if st.session_state.get("role") in ["admin", "direksi"]:
#             sales = st.multiselect(
#                 "Sales Name",
#                 options=sorted(
#                     df["Sales_Name"]
#                     .dropna()
#                     .astype(str)
#                     .unique()
#                 ),
#                 placeholder="Pilih Sales"
#             )

#     c4, c5 = st.columns([1, 2])

#     # ---------- STATUS BAYAR ----------
#     with c4:
#         status_list = [
#             "02. Kurang Bayar",
#             "03. Belum Bayar"
#         ]

#         status_bayar = st.multiselect(
#             "Status Bayar",
#             options=status_list,
#             default=status_list
#         )

#     # ---------- SEARCH ----------
#     with c5:
#         keyword = st.text_input(
#             "Cari Customer / Invoice",
#             placeholder="Nama customer atau nomor invoice..."
#         )

# # ==========================================================
# # APPLY FILTER
# # ==========================================================
# if periode:
#     df = df[df["Periode"].isin(periode)]

# if branch:
#     df = df[df["Branch"].isin(branch)]

# if sales:
#     df = df[df["Sales_Name"].isin(sales)]

# if status_bayar:
#     df = df[df["Ket_Bayar"].isin(status_bayar)]

# if keyword:
#     df = df[
#         df["Cust_Name"].astype(str).str.contains(
#             keyword,
#             case=False,
#             na=False
#         )
#         |
#         df["No_Inv"].astype(str).str.contains(
#             keyword,
#             case=False,
#             na=False
#         )
#     ]

# st.caption(
#     f"Menampilkan {len(df)} Invoice • {df['Cust_Name'].nunique()} Customer"
# )
# # ==========================================================
# # TABEL PIUTANG
# # ==========================================================
# table = df[
#     [
#         "Branch",
#         "Sales_Name",
#         "Cust_Name",
#         "No_Inv",
#         "Periode",
#         "Jth_Tempo",
#         "Top_Days",
#         "Ket_Bayar",
#         "Balance",
#     ]
# ].copy()

# table["Jth_Tempo"] = table["Jth_Tempo"].dt.strftime("%d-%m-%Y")
# table["Top_Days"] = table["Top_Days"].fillna(0).astype(int)
# table["Balance"] = table["Balance"].apply(rupiah)

# table = table.rename(
#     columns={
#         "Sales_Name": "Sales Name",
#         "Cust_Name": "Customer",
#         "No_Inv": "No Invoice",
#         "Jth_Tempo": "Jatuh Tempo",
#         "Top_Days": "TOP (Days)",
#         "Ket_Bayar": "Status Bayar",
#         "Balance": "Balance",
#     }
# )

# # Highlight invoice lewat tempo
# def highlight_overdue(row):
#     try:
#         tgl = pd.to_datetime(row["Jatuh Tempo"], format="%d-%m-%Y")
#         if tgl < today:
#             return ["background-color:#FEE2E2;color:#B91C1C;font-weight:bold"] * len(row)
#     except:
#         pass
#     return [""] * len(row)


# st.subheader("📋 Daftar Piutang Customer")

# st.dataframe(
#     table.style.apply(highlight_overdue, axis=1),
#     use_container_width=True,
#     hide_index=True,
#     height=560,
# )

# # ==========================================================
# # INVOICE LEWAT TEMPO
# # ==========================================================
# st.markdown("---")
# st.subheader("🚨 Invoice Lewat Tempo")

# overdue = df[df["Status Tempo"] == "Lewat Tempo"].copy()

# if overdue.empty:

#     st.success("Tidak ada invoice yang melewati jatuh tempo.")

# else:

#     overdue = overdue.sort_values(
#         by=["Top_Days", "Balance"],
#         ascending=[False, False],
#     )

#     overdue["Jth_Tempo"] = overdue["Jth_Tempo"].dt.strftime("%d-%m-%Y")
#     overdue["Balance"] = overdue["Balance"].apply(rupiah)
#     overdue["Top_Days"] = overdue["Top_Days"].fillna(0).astype(int)

#     overdue = overdue.rename(
#         columns={
#             "Cust_Name": "Customer",
#             "Sales_Name": "Sales Name",
#             "No_Inv": "No Invoice",
#             "Jth_Tempo": "Jatuh Tempo",
#             "Top_Days": "TOP (Days)",
#             "Balance": "Balance",
#         }
#     )

#     st.dataframe(
#         overdue[
#             [
#                 "Customer",
#                 "Sales Name",
#                 "Branch",
#                 "No Invoice",
#                 "Periode",
#                 "Jatuh Tempo",
#                 "TOP (Days)",
#                 "Balance",
#             ]
#         ],
#         use_container_width=True,
#         hide_index=True,
#         height=280,
#     )

# # ==========================================================
# # GRAFIK BALANCE PER BRANCH
# # ==========================================================
# st.markdown("---")
# st.subheader("🏢 Total Balance per Branch")

# branch_chart = (
#     df.groupby("Branch", as_index=False)["Balance"]
#     .sum()
#     .sort_values("Balance", ascending=False)
# )

# if not branch_chart.empty:

#     fig_branch = px.bar(
#         branch_chart,
#         x="Branch",
#         y="Balance",
#         text="Balance",
#         template="plotly_white",
#         color="Balance",
#         color_continuous_scale="Tealgrn",
#     )

#     fig_branch.update_layout(
#         height=420,
#         coloraxis_showscale=False,
#         margin=dict(l=20, r=20, t=20, b=20),
#         xaxis_title="Branch",
#         yaxis_title="Balance",
#     )

#     fig_branch.update_traces(
#         texttemplate="Rp %{text:,.0f}",
#         textposition="outside",
#     )

#     st.plotly_chart(
#         fig_branch,
#         use_container_width=True,
#         config={"displayModeBar": False},
#     )

# # ==========================================================
# # GRAFIK BALANCE PER SALES (ADMIN & DIREKSI)
# # ==========================================================
# if st.session_state.get("role") in ["admin", "direksi"]:

#     st.markdown("---")
#     st.subheader("👤 Total Balance per Sales")

#     sales_chart = (
#         df.groupby("Sales_Name", as_index=False)["Balance"]
#         .sum()
#         .sort_values("Balance", ascending=False)
#     )

#     if not sales_chart.empty:

#         fig_sales = px.bar(
#             sales_chart,
#             x="Sales_Name",
#             y="Balance",
#             text="Balance",
#             template="plotly_white",
#             color="Balance",
#             color_continuous_scale="Blues",
#         )

#         fig_sales.update_layout(
#             height=420,
#             coloraxis_showscale=False,
#             margin=dict(l=20, r=20, t=20, b=20),
#             xaxis_title="Sales Name",
#             yaxis_title="Balance",
#         )

#         fig_sales.update_traces(
#             texttemplate="Rp %{text:,.0f}",
#             textposition="outside",
#         )

#         st.plotly_chart(
#             fig_sales,
#             use_container_width=True,
#             config={"displayModeBar": False},
#         )

# # ==========================================================
# # RINGKASAN BALANCE PER BRANCH
# # ==========================================================
# st.markdown("---")
# st.subheader("📊 Ringkasan Balance per Branch")

# summary = (
#     df.groupby("Branch")
#     .agg(
#         Customer=("Cust_Name", "nunique"),
#         Invoice=("No_Inv", "count"),
#         Balance=("Balance", "sum"),
#     )
#     .reset_index()
#     .sort_values("Balance", ascending=False)
# )

# summary["Balance"] = summary["Balance"].apply(rupiah)

# st.dataframe(
#     summary,
#     use_container_width=True,
#     hide_index=True,
# )

# # ==========================================================
# # DOWNLOAD EXCEL
# # ==========================================================
# st.markdown("---")

# download_df = df[
#     [
#         "Branch",
#         "Sales_Name",
#         "Cust_Name",
#         "No_Inv",
#         "Periode",
#         "Jth_Tempo",
#         "Top_Days",
#         "Ket_Bayar",
#         "Balance",
#     ]
# ].copy()

# download_df["Jth_Tempo"] = download_df["Jth_Tempo"].dt.strftime("%d-%m-%Y")

# excel = download_df.to_csv(index=False).encode("utf-8-sig")

# st.download_button(
#     "📥 Download Data Piutang",
#     data=excel,
#     file_name="Dashboard_Piutang.csv",
#     mime="text/csv",
#     use_container_width=True,
# )