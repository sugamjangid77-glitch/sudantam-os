import streamlit as st
import pandas as pd
import datetime
import os
import urllib.parse
import time
import base64
import json
from PIL import Image, ImageDraw

# Try importing Cloud libs
try:
    import gspread
    from google.oauth2.service_account import Credentials
    CLOUD_AVAILABLE = True
except ImportError:
    CLOUD_AVAILABLE = False

from fpdf import FPDF

# ==========================================
# 1. PAGE CONFIG & MOBILE STYLING
# ==========================================
st.set_page_config(page_title="Sudantam Mobile", layout="wide", page_icon="🦷")

PRIMARY_COLOR = "#2C7A6F"
LOGO_FILENAME = "logo.jpeg"
PRESCRIPTION_FOLDER = "Prescriptions"
LOCAL_DB_FILE = "sudantam_patients.csv"

if not os.path.exists(PRESCRIPTION_FOLDER):
    os.makedirs(PRESCRIPTION_FOLDER)

# Remove the annoying sidebar and make the interface clean
st.markdown(f"""
<style>
    /* HIDE DEFAULT STREAMLIT ELEMENTS */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
    
    /* BIGGER BUTTONS FOR THUMBS */
    div.stButton > button {{
        width: 100%;
        height: 60px;
        font-size: 20px;
        font-weight: bold;
        background-color: {PRIMARY_COLOR};
        color: white;
        border-radius: 12px;
        margin-bottom: 10px;
    }}
    
    /* MOBILE INPUT FIELDS */
    .stTextInput > div > div > input {{
        font-size: 18px;
        padding: 10px;
    }}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE & CLOUD SETUP
# ==========================================
# Create key.json from Secrets
if not os.path.exists("key.json"):
    if "gcp_service_account" in st.secrets:
        try:
            with open("key.json", "w") as f:
                json.dump(st.secrets["gcp_service_account"], f)
        except: pass

@st.cache_resource
def get_cloud_engine():
    if not CLOUD_AVAILABLE or not os.path.exists("key.json"): return None
    try:
        creds = Credentials.from_service_account_file("key.json", scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        client = gspread.authorize(creds)
        sh = client.open("Sudantam_Cloud_DB")
        return sh.worksheet("Patients")
    except: return None

pt_sheet = get_cloud_engine()

def load_data():
    df = pd.DataFrame()
    # 1. Try Cloud
    if pt_sheet:
        try:
            d = pt_sheet.get_all_records()
            if d: df = pd.DataFrame(d).astype(str)
        except: pass
    
    # 2. Fallback Local
    if df.empty and os.path.exists(LOCAL_DB_FILE):
        try: df = pd.read_csv(LOCAL_DB_FILE).astype(str)
        except: pass
    
    # 3. Columns
    expected_cols = ["Patient ID", "Name", "Age", "Gender", "Contact", "Last Visit", "Treatment Notes", "Medical History", "Treatments Done", "Affected Teeth", "Pending Amount", "Visit Log"]
    if df.empty:
        df = pd.DataFrame(columns=expected_cols)
    else:
        for c in expected_cols:
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
# 3. HELPER FUNCTIONS
# ==========================================
def render_tooth_selector(key):
    st.info("🦷 Tooth Selector")
    sel = []
    # Simplified for Mobile: Just check boxes
    c1, c2, c3, c4 = st.columns(4)
    with c1: 
        st.caption("UR")
        if st.checkbox("1-8 UR", key=f"{key}UR"): sel.append("UR Quad")
    with c2: 
        st.caption("UL")
        if st.checkbox("1-8 UL", key=f"{key}UL"): sel.append("UL Quad")
    with c3: 
        st.caption("LL")
        if st.checkbox("1-8 LL", key=f"{key}LL"): sel.append("LL Quad")
    with c4: 
        st.caption("LR")
        if st.checkbox("1-8 LR", key=f"{key}LR"): sel.append("LR Quad")
    
    # Specific input for precision
    spec = st.text_input("Or type specific (e.g., 36, 46)", key=f"{key}txt")
    if spec: sel.append(spec)
    return ", ".join(sel)

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 20)
        self.cell(0, 10, 'Sudantam Dental Clinic', 0, 1, 'C')
        self.ln(5)

# ==========================================
# 4. MAIN MOBILE INTERFACE (TABS)
# ==========================================

# 🔹 HEADER (Logo & Title)
c1, c2 = st.columns([1, 4])
with c1:
    if os.path.exists(LOGO_FILENAME): st.image(LOGO_FILENAME, width=60)
with c2:
    st.markdown("<h2 style='margin:0; padding-top:10px;'>Sudantam OS</h2>", unsafe_allow_html=True)

# 🔹 NAVIGATION (THE FIX: Always Visible Tabs)
selected_tab = st.selectbox("⬇️ SELECT MENU HERE ⬇️", 
    ["➕ New Patient", "💊 Rx & Invoice", "📂 Registry (Search)", "💰 Manage Dues", "🔧 Tools"],
    index=0
)

st.markdown("---")

# ==========================================
# TAB 1: NEW PATIENT
# ==========================================
if selected_tab == "➕ New Patient":
    st.subheader("Add New Patient")
    with st.form("reg_mobile"):
        name = st.text_input("Name")
        phone = st.text_input("Phone (10 digits)")
        c1, c2 = st.columns(2)
        age = c1.number_input("Age", 1, 100)
        gender = c2.selectbox("Sex", ["M", "F"])
        hist = st.multiselect("Medical History", ["Diabetes", "BP", "Thyroid", "Allergy"])
        
        if st.form_submit_button("✅ SAVE PATIENT"):
            if not name:
                st.error("Name is required!")
            else:
                new_row = {
                    "Patient ID": len(df) + 101, "Name": name, "Age": age, "Gender": gender, "Contact": phone, 
                    "Last Visit": datetime.date.today().strftime("%d-%m-%Y"), 
                    "Medical History": ", ".join(hist), "Treatments Done": "", 
                    "Affected Teeth": "", "Pending Amount": 0, "Visit Log": ""
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(df)
                st.success(f"Saved {name}!")

# ==========================================
# TAB 2: RX & INVOICE
# ==========================================
elif selected_tab == "💊 Rx & Invoice":
    st.subheader("Prescription & Bill")
    pt_name = st.selectbox("Search Patient", [""] + df["Name"].tolist())
    
    if pt_name:
        idx = df.index[df["Name"] == pt_name].tolist()[0]
        row = df.iloc[idx]
        
        st.info(f"Pt: {pt_name} | Age: {row['Age']}")
        
        diag = st.multiselect("Diagnosis", ["Caries", "Pain", "RCT Needed", "Extraction", "Cleaning"])
        
        st.write("---")
        st.write("💊 **Medicines**")
        meds = st.multiselect("Meds", ["Amoxicillin", "Augmentin 625", "Zerodol-SP", "Dolo 650", "Metrogyl 400", "Pan-D"])
        
        st.write("---")
        st.write("💰 **Bill**")
        reason = st.text_input("Treatment Done (e.g. RCT)")
        amount = st.number_input("Total Bill", step=100)
        paid = st.number_input("Amount Paid", step=100)
        
        if st.button("💾 SAVE & FINALIZE"):
            due = amount - paid
            old_due = float(row['Pending Amount']) if row['Pending Amount'] else 0
            total_due = old_due + due
            
            # Log
            log = f"\n📅 {datetime.date.today()}\nTx: {reason}\nBill: {amount}, Paid: {paid}\nRx: {', '.join(meds)}\n"
            df.at[idx, "Visit Log"] = str(row['Visit Log']) + log
            df.at[idx, "Pending Amount"] = total_due
            save_data(df)
            
            st.success("Saved!")
            st.info(f"Current Due: ₹{total_due}")
            
            # WhatsApp Link
            if row['Contact']:
                msg = f"Hello {pt_name}, your visit at Sudantam is complete. Bill: {amount}, Paid: {paid}, Due: {total_due}."
                link = f"https://wa.me/91{row['Contact']}?text={urllib.parse.quote(msg)}"
                st.link_button("📲 Send WhatsApp Receipt", link)

# ==========================================
# TAB 3: REGISTRY (SEARCH)
# ==========================================
elif selected_tab == "📂 Registry (Search)":
    st.subheader("Patient Database")
    q = st.text_input("🔍 Search Name")
    
    if q:
        res = df[df["Name"].str.contains(q, case=False, na=False)]
        for i, r in res.iterrows():
            with st.expander(f"{r['Name']} (Due: ₹{r['Pending Amount']})"):
                st.write(f"📞 {r['Contact']}")
                st.write(f"📝 History: {r['Visit Log']}")
                st.write(f"⚠️ Med Hist: {r['Medical History']}")

# ==========================================
# TAB 4: DEFAULTERS
# ==========================================
elif selected_tab == "💰 Manage Dues":
    st.subheader("Pending Payments")
    df["Pending Amount"] = pd.to_numeric(df["Pending Amount"], errors='coerce').fillna(0)
    dues = df[df["Pending Amount"] > 0]
    
    if dues.empty:
        st.success("No pending dues!")
    else:
        for i, r in dues.iterrows():
            st.error(f"{r['Name']}: ₹{r['Pending Amount']}")
            if r['Contact']:
                link = f"https://wa.me/91{r['Contact']}?text=Hello, pending due reminder of Rs {r['Pending Amount']} at Sudantam."
                st.markdown(f"[📲 Remind]({link})")

# ==========================================
# TAB 5: TOOLS
# ==========================================
elif selected_tab == "🔧 Tools":
    st.subheader("Data Tools")
    if st.button("🔄 Force Sync to Cloud"):
        save_data(df)
        st.success("Synced!")
    
    up = st.file_uploader("Restore CSV")
    if up:
        old = pd.read_csv(up)
        df = pd.concat([df, old], ignore_index=True)
        save_data(df)
        st.success("Restored")
