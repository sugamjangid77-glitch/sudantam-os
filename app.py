import streamlit as st
import pandas as pd
import datetime
import os
import urllib.parse
import json
import base64
from fpdf import FPDF

# ==========================================
# 1. VISIBILITY LOCK & UI CONFIG
# ==========================================
st.set_page_config(page_title="Sudantam OS", layout="wide", page_icon="🦷")

st.markdown("""
    <style>
        /* FORCE LIGHT MODE */
        :root { color-scheme: light !important; }
        .stApp { background-color: #FFFFFF !important; }

        /* --- LOGO UPGRADE --- */
        [data-testid="stImage"] img {
            width: 250px !important;
            border-radius: 10px;
            margin-bottom: 30px;
        }

        /* --- TEXT & LABEL VISIBILITY --- */
        label, .stMarkdown p, p {
            color: #000000 !important;
            font-weight: 700 !important;
        }

        /* --- INPUT BOXES --- */
        input, textarea, [data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            color: #000000 !important;
            border: 2px solid #2C7A6F !important;
            border-radius: 8px !important;
        }

        /* --- DROPDOWN ARROW FIX --- */
        /* Forces the dropdown icons to be simple teal arrows */
        svg[data-testid="chevron-down"] {
            fill: #2C7A6F !important;
        }

        /* --- BUTTONS (FIXING THE BLACK BUTTON) --- */
        /* Target the specific registration/save buttons */
        div.stButton > button {
            background-color: #2C7A6F !important;
            color: #FFFFFF !important; /* Force White Text */
            font-weight: 800 !important;
            font-size: 18px !important;
            height: 60px !important;
            border-radius: 12px !important;
            border: none !important;
            box-shadow: 0 4px 6px rgba(44, 122, 111, 0.2) !important;
        }

        /* --- MODERN PILL TABS --- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background-color: #F0F2F6;
            padding: 10px;
            border-radius: 15px;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: #FFFFFF !important;
            color: #2C7A6F !important;
            border: 1px solid #2C7A6F !important;
            border-radius: 25px !important;
            padding: 10px 20px !important;
            font-weight: bold !important;
        }
        .stTabs [aria-selected="true"] {
            background-color: #2C7A6F !important;
            color: #FFFFFF !important;
        }

        /* Hide Default UI Elements */
        #MainMenu, footer, header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# Constants
PRESCRIPTION_FOLDER = "Prescriptions"
LOCAL_DB_FILE = "sudantam_patients.csv"
LOGO_FILENAME = "logo.jpeg"

if not os.path.exists(PRESCRIPTION_FOLDER): os.makedirs(PRESCRIPTION_FOLDER)

# ==========================================
# 2. DATA ENGINE
# ==========================================
try:
    import gspread
    from google.oauth2.service_account import Credentials
    CLOUD_AVAILABLE = True
except ImportError: CLOUD_AVAILABLE = False

if not os.path.exists("key.json") and "gcp_service_account" in st.secrets:
    try:
        with open("key.json", "w") as f: json.dump(st.secrets["gcp_service_account"], f)
    except: pass

@st.cache_resource(ttl=1)
def get_cloud_engine():
    if not CLOUD_AVAILABLE or not os.path.exists("key.json"): return None
    try:
        creds = Credentials.from_service_account_file("key.json", scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(creds)
        return client.open("Sudantam_Cloud_DB").worksheet("Patients")
    except: return None

pt_sheet = get_cloud_engine()

def load_data():
    df = pd.DataFrame()
    if pt_sheet:
        try:
            d = pt_sheet.get_all_records()
            if d: df = pd.DataFrame(d).astype(str)
        except: pass
    if df.empty and os.path.exists(LOCAL_DB_FILE):
        try: df = pd.read_csv(LOCAL_DB_FILE).astype(str)
        except: pass
    cols = ["Patient ID", "Name", "Age", "Gender", "Contact", "Last Visit", "Medical History", "Pending Amount", "Visit Log", "Affected Teeth"]
    if df.empty: df = pd.DataFrame(columns=cols)
    else:
        for c in cols: 
            if c not in df.columns: df[c] = ""
    return df

def save_data(df):
    df.to_csv(LOCAL_DB_FILE, index=False)
    if pt_sheet:
        try:
            pt_sheet.clear()
            pt_sheet.update([df.columns.values.tolist()] + df.values.tolist())
        except: pass

df = load_data()

# ==========================================
# 3. INTERFACE
# ==========================================
if os.path.exists(LOGO_FILENAME):
    st.image(LOGO_FILENAME)

tabs = st.tabs(["📝 REGISTRATION", "🦷 CLINICAL", "📂 RECORDS", "💰 DUES", "🔄 SYNC"])

# --- TAB 1: REGISTRATION ---
with tabs[0]:
    st.markdown("### 📝 Register New Patient")
    with st.form("reg", clear_on_submit=True):
        name = st.text_input("FULL NAME")
        phone = st.text_input("CONTACT NUMBER")
        
        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input("AGE (YEARS)", min_value=1, step=1)
        with col2:
            # Removed default "Male"
            gender = st.selectbox("GENDER", ["", "Male", "Female", "Other"])
        
        # Removed default "None"
        med_hx = st.multiselect("MEDICAL HISTORY", ["Diabetes", "BP", "Thyroid", "Asthma", "Allergy"])
        
        if st.form_submit_button("✅ COMPLETE REGISTRATION"):
            if not name:
                st.error("Name is required!")
            else:
                new_pt = {
                    "Patient ID": len(df)+101, "Name": name, "Age": age, "Gender": gender, "Contact": phone,
                    "Last Visit": datetime.date.today().strftime("%d-%m-%Y"),
                    "Medical History": ", ".join(med_hx), "Pending Amount": 0, "Visit Log": ""
                }
                df = pd.concat([df, pd.DataFrame([new_pt])], ignore_index=True)
                save_data(df)
                st.success(f"Registered: {name}")

# --- TAB 2: CLINICAL ---
with tabs[1]:
    st.markdown("### 🦷 Treatment & Billing")
    pt_select = st.selectbox("SEARCH PATIENT", [""] + df["Name"].tolist())
    
    if pt_select:
        idx = df.index[df["Name"] == pt_select].tolist()[0]
        row = df.iloc[idx]
        
        st.write("---")
        st.info("🦷 FDI Tooth Selection")
        c1, c2 = st.columns(2)
        with c1: ur = st.multiselect("UR", [str(x) for x in range(11, 19)][::-1])
        with c2: ul = st.multiselect("UL", [str(x) for x in range(21, 29)])
        c3, c4 = st.columns(2)
        with c3: lr = st.multiselect("LR", [str(x) for x in range(41, 49)][::-1])
        with c4: ll = st.multiselect("LL", [str(x) for x in range(31, 39)])
        
        fdi_sel = ", ".join(ur + ul + ll + lr)
        if fdi_sel: st.success(f"Selected: {fdi_sel}")

        tx = st.text_input("TREATMENT DONE")
        c_bill1, c_bill2 = st.columns(2)
        bill = c_bill1.number_input("BILL", step=100)
        paid = c_bill2.number_input("PAID", step=100)
        
        if st.form_submit_button("💾 SAVE TREATMENT"):
            due = (bill - paid) + (float(row['Pending Amount']) if row['Pending Amount'] else 0)
            log = f"\n📅 {datetime.date.today()} | Tx: {tx} | Teeth: {fdi_sel} | Paid: {paid}"
            df.at[idx, "Visit Log"] = str(row['Visit Log']) + log
            df.at[idx, "Pending Amount"] = due
            save_data(df)
            st.success("Treatment Saved!")

# --- TAB 3: RECORDS ---
with tabs[2]:
    search_q = st.text_input("🔍 Search Registry")
    if search_q:
        results = df[df["Name"].str.contains(search_q, case=False, na=False)]
        for i, r in results.iterrows():
            with st.expander(f"{r['Name']} (Due: ₹{r['Pending Amount']})"):
                if r['Contact']:
                    wa_link = f"https://wa.me/91{r['Contact']}?text=Hello%20{r['Name']}"
                    st.link_button("📲 WhatsApp", wa_link)
                st.text_area("Visit History", r['Visit Log'], height=150)

# --- TAB 4: DUES ---
with tabs[3]:
    df["Pending Amount"] = pd.to_numeric(df["Pending Amount"], errors='coerce').fillna(0)
    defaulters = df[df["Pending Amount"] > 0]
    if not defaulters.empty:
        st.dataframe(defaulters[["Name", "Contact", "Pending Amount"]])
        payer = st.selectbox("Select Payer", [""] + defaulters["Name"].unique().tolist())
        if payer:
            p_idx = df.index[df["Name"] == payer].tolist()[0]
            current_due = df.at[p_idx, "Pending Amount"]
            rec = st.number_input("Amount Received", max_value=float(current_due))
            if st.button("✅ Update Account"):
                df.at[p_idx, "Pending Amount"] = current_due - rec
                save_data(df)
                st.rerun()

# --- TAB 5: SYNC ---
with tabs[4]:
    if st.button("🔄 Refresh Data"):
        st.cache_resource.clear()
        st.rerun()
