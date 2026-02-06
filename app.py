import streamlit as st
import pandas as pd
import datetime
import os
import urllib.parse
import json
import base64
from fpdf import FPDF

# ==========================================
# 1. PROFESSIONAL MEDICAL UI CONFIGURATION
# ==========================================
st.set_page_config(page_title="Sudantam OS", layout="wide", page_icon="🦷")

st.markdown("""
    <style>
        /* FORCE LIGHT MODE COLOR SCHEME */
        :root { color-scheme: light !important; }
        
        .stApp {
            background-color: #FFFFFF !important;
            color: #000000 !important;
        }

        /* --- LOGO SIZE UPGRADE --- */
        [data-testid="stImage"] img {
            display: block;
            margin-left: auto;
            margin-right: auto;
            width: 150px !important; /* Larger Logo */
            border-radius: 15px;
        }

        /* --- INPUT FIELDS & DROPDOWNS --- */
        input, textarea, select, .stNumberInput input {
            background-color: #FFFFFF !important;
            color: #000000 !important;
            border: 1px solid #2C7A6F !important;
            border-radius: 8px !important;
        }
        
        /* Fix for invisible dropdown text and "weird signs" */
        div[data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            color: #000000 !important;
        }
        
        /* Target the arrow and clear icons in dropdowns */
        svg[data-testid="chevron-down"], svg[title="Clear all"] {
            fill: #2C7A6F !important;
            color: #2C7A6F !important;
        }

        /* --- PILL TABS WITH ICONS --- */
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
            border-radius: 30px !important;
            padding: 10px 20px !important;
            font-weight: bold !important;
            font-size: 14px !important;
        }
        .stTabs [aria-selected="true"] {
            background-color: #2C7A6F !important;
            color: #FFFFFF !important;
        }

        /* --- BUTTONS: TEAL WITH WHITE TEXT --- */
        div.stButton > button {
            background-color: #2C7A6F !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 800 !important;
            height: 55px !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
        }

        /* --- TAGS (Medical History / Teeth) --- */
        span[data-baseweb="tag"] {
            background-color: #2C7A6F !important;
            color: #FFFFFF !important;
            border-radius: 5px !important;
        }
        span[data-baseweb="tag"] span { color: white !important; }
        span[data-baseweb="tag"] svg { fill: white !important; }

        /* Hide Default UI */
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
# 3. PDF GENERATOR
# ==========================================
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 20)
        self.set_text_color(44, 122, 111)
        self.cell(0, 10, 'Sudantam Dental Clinic', 0, 1, 'C')
        self.set_font('Arial', '', 10); self.set_text_color(50)
        self.cell(0, 5, 'Dr. Sugam Jangid (BDS) | +91-8078656835', 0, 1, 'C')
        self.ln(5); self.set_draw_color(44, 122, 111); self.line(10, 25, 200, 25); self.ln(5)

def generate_pdf_file(name, age, date, diag, meds, tx_reason, teeth, amount, paid, due):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12); pdf.set_text_color(0)
    pdf.cell(0, 10, f"Patient: {name} ({age} Yrs)  |  Date: {date}", 0, 1, 'L')
    pdf.ln(2)
    
    if diag:
        pdf.set_font('Arial', 'B', 12); pdf.set_text_color(44, 122, 111); pdf.cell(0, 8, "Diagnosis", 0, 1)
        pdf.set_font('Arial', '', 11); pdf.set_text_color(0); pdf.multi_cell(0, 6, f"{', '.join(diag)}"); pdf.ln(3)

    if meds:
        pdf.set_font('Arial', 'B', 12); pdf.set_text_color(44, 122, 111); pdf.cell(0, 8, "Prescription", 0, 1)
        pdf.set_font('Arial', '', 11); pdf.set_text_color(0)
        for m in meds: pdf.cell(0, 6, f"- {m}", 0, 1)
        pdf.ln(3)
    
    filename = f"{name.replace(' ', '_')}_Invoice.pdf"
    path = os.path.join(PRESCRIPTION_FOLDER, filename); pdf.output(path)
    return path, filename

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
# LARGE CENTERED LOGO
if os.path.exists(LOGO_FILENAME):
    st.image(LOGO_FILENAME)

# TABS WITH ICONS
tabs = st.tabs(["📝 REGISTRATION", "🦷 CLINICAL", "📂 RECORDS", "💰 DUES", "🔄 SYNC"])

# --- TAB 1: NEW PATIENT ---
with tabs[0]:
    st.markdown("#### Patient Registration")
    with st.form("reg", clear_on_submit=True):
        name = st.text_input("FULL NAME")
        phone = st.text_input("PHONE NUMBER")
        c1, c2 = st.columns(2)
        with c1: age = st.number_input("AGE", min_value=1, step=1)
        with c2: gender = st.selectbox("GENDER", ["Male", "Female", "Other"])
        mh = st.multiselect("MEDICAL HISTORY", ["None", "Diabetes", "Hypertension", "Thyroid", "Asthma", "Allergy"])
        
        if st.form_submit_button("✅ REGISTER PATIENT"):
            if not name: st.error("Enter Name")
            else:
                new_row = {"Patient ID": len(df)+101, "Name": name, "Age": age, "Gender": gender, "Contact": phone, "Last Visit": datetime.date.today().strftime("%d-%m-%Y"), "Medical History": ", ".join(mh), "Pending Amount": 0, "Visit Log": ""}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True); save_data(df)
                st.success(f"Registered: {name}")

# --- TAB 2: CLINICAL (FDI) ---
with tabs[1]:
    pt_name = st.selectbox("SELECT PATIENT", [""] + df["Name"].tolist())
    if pt_name:
        idx = df.index[df["Name"] == pt_name].tolist()[0]
        row = df.iloc[idx]
        
        st.info("🦷 FDI TOOTH SELECTOR")
        c1, c2 = st.columns(2)
        with c1: ur = st.multiselect("UR (18-11)", ["18","17","16","15","14","13","12","11"])
        with c2: ul = st.multiselect("UL (21-28)", ["21","22","23","24","25","26","27","28"])
        c3, c4 = st.columns(2)
        with c3: lr = st.multiselect("LR (48-41)", ["48","47","46","45","44","43","42","41"])
        with c4: ll = st.multiselect("LL (31-38)", ["31","32","33","34","35","36","37","38"])

        fdi_str = ", ".join(ur + ul + ll + lr)
        if fdi_str: st.success(f"Selected: {fdi_str}")

        diag = st.multiselect("DIAGNOSIS", ["Caries", "Pulpitis", "Periodontitis", "Fractured"])
        meds = st.multiselect("PRESCRIPTION", ["Amoxicillin 500", "Augmentin 625", "Zerodol-SP", "Ketorol DT", "Pan-D"])
        tx_reason = st.text_input("TREATMENT DONE")
        
        c1, c2 = st.columns(2)
        with c1: amount = st.number_input("TOTAL BILL", step=100); paid = st.number_input("PAID NOW", step=100)
        
        if st.button("💾 SAVE & PRINT"):
            due = (amount - paid) + (float(row['Pending Amount']) if row['Pending Amount'] else 0)
            log = f"\n📅 {datetime.date.today()} | Tx: {tx_reason} | Teeth: {fdi_str} | Paid: {paid}"
            df.at[idx, "Visit Log"] = str(row['Visit Log']) + log
            df.at[idx, "Pending Amount"] = due
            save_data(df)
            st.success("Saved!")

# --- TAB 3: RECORDS ---
with tabs[2]:
    q = st.text_input("🔍 SEARCH")
    if q:
        res = df[df["Name"].str.contains(q, case=False, na=False)]
        for i, r in res.iterrows():
            with st.expander(f"{r['Name']} (Due: ₹{r['Pending Amount']})"):
                st.write(f"📞 {r['Contact']}")
                if r['Contact']:
                    link = f"https://wa.me/91{r['Contact']}?text=Hello%20{r['Name']}"
                    st.link_button("📲 WhatsApp", link)
                st.text_area("Log", r['Visit Log'])

# --- TAB 4: DUES ---
with tabs[3]:
    df["Pending Amount"] = pd.to_numeric(df["Pending Amount"], errors='coerce').fillna(0)
    defaulters = df[df["Pending Amount"] > 0]
    if not defaulters.empty:
        st.dataframe(defaulters[["Name", "Contact", "Pending Amount"]])
        pay_name = st.selectbox("PAYER", defaulters["Name"].unique())
        if pay_name:
            pay_idx = df.index[df["Name"] == pay_name].tolist()[0]
            curr = df.at[pay_idx, "Pending Amount"]
            pay_now = st.number_input("RECEIVED", max_value=float(curr))
            if st.button("✅ CLEAR"):
                df.at[pay_idx, "Pending Amount"] = curr - pay_now
                save_data(df); st.rerun()

# --- TAB 5: SYNC ---
with tabs[4]:
    if st.button("🔄 REFRESH CLOUD"): st.cache_resource.clear(); st.rerun()
