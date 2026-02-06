import streamlit as st
import pandas as pd
import datetime
import os
import urllib.parse
import json
import base64
from fpdf import FPDF
from PIL import Image

# ==========================================
# 1. CONFIG & THEME (Light Mode Forced)
# ==========================================
st.set_page_config(page_title="Sudantam OS", layout="wide", page_icon="🦷")

# Force Light Theme CSS
st.markdown("""
    <style>
        /* Force White Background */
        .stApp {
            background-color: #FFFFFF;
            color: #000000;
        }
        
        /* Sudantam Teal Color Palette */
        :root {
            --primary-color: #2C7A6F;
        }
        
        /* Buttons */
        div.stButton > button {
            background-color: #2C7A6F !important;
            color: white !important;
            border-radius: 8px;
            font-size: 16px;
            height: 55px;
            width: 100%;
            border: none;
        }
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: #f0f2f6;
            border-radius: 5px;
            padding: 10px 20px;
            color: #2C7A6F;
            font-weight: bold;
        }
        .stTabs [aria-selected="true"] {
            background-color: #2C7A6F !important;
            color: white !important;
        }
        
        /* Inputs */
        input {
            background-color: #F8F9FA !important;
            color: black !important;
        }
        
        /* Hide Streamlit Branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# Constants
PRESCRIPTION_FOLDER = "Prescriptions"
LOCAL_DB_FILE = "sudantam_patients.csv"
LOGO_FILENAME = "logo.jpeg"
TOOTH_CHART_FILENAME = "tooth_chart_base.png"

# Ensure folders exist
if not os.path.exists(PRESCRIPTION_FOLDER):
    os.makedirs(PRESCRIPTION_FOLDER)

# ==========================================
# 2. REAL-TIME CLOUD DATABASE (Syncs Instantly)
# ==========================================
try:
    import gspread
    from google.oauth2.service_account import Credentials
    CLOUD_AVAILABLE = True
except ImportError:
    CLOUD_AVAILABLE = False

# Create key.json if missing (from Secrets)
if not os.path.exists("key.json") and "gcp_service_account" in st.secrets:
    try:
        with open("key.json", "w") as f:
            json.dump(st.secrets["gcp_service_account"], f)
    except: pass

@st.cache_resource(ttl=2)  # <--- SYNC MAGIC: Refreshes connection every 2 seconds
def get_cloud_engine():
    if not CLOUD_AVAILABLE or not os.path.exists("key.json"): return None
    try:
        creds = Credentials.from_service_account_file("key.json", scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        client = gspread.authorize(creds)
        sh = client.open("Sudantam_Cloud_DB")
        return sh.worksheet("Patients")
    except: return None

pt_sheet = get_cloud_engine()

# Load Data (No caching = Always fresh)
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
    
    # 3. Structure
    cols = ["Patient ID", "Name", "Age", "Gender", "Contact", "Last Visit", "Treatment Notes", "Medical History", "Treatments Done", "Affected Teeth", "Pending Amount", "Visit Log"]
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

# Load data on every interaction
df = load_data()

# ==========================================
# 3. PDF GENERATOR
# ==========================================
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 20)
        self.set_text_color(44, 122, 111)
        self.cell(0, 10, 'Sudantam Dental Clinic', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.set_text_color(50)
        self.cell(0, 5, 'Dr. Sugam Jangid (BDS) | +91-8078656835', 0, 1, 'C')
        self.ln(5)
        self.set_draw_color(44, 122, 111); self.line(10, 25, 200, 25); self.ln(5)

    def invoice_row(self, item, price, bold=False):
        self.set_font('Arial', 'B' if bold else '', 11)
        self.cell(145, 8, f" {item}", 1, 0, 'L')
        self.cell(45, 8, f"{price} ", 1, 1, 'R')

def generate_pdf_file(name, age, date, diag, meds, tx_reason, amount, paid, due):
    pdf = PDF()
    pdf.add_page()
    
    # Patient Info
    pdf.set_font('Arial', 'B', 12); pdf.set_text_color(0)
    pdf.cell(0, 10, f"Patient: {name} ({age} Yrs)  |  Date: {date}", 0, 1, 'L')
    pdf.ln(2)
    
    # Diagnosis
    if diag:
        pdf.set_font('Arial', 'B', 12); pdf.set_text_color(44, 122, 111)
        pdf.cell(0, 8, "Diagnosis", 0, 1)
        pdf.set_font('Arial', '', 11); pdf.set_text_color(0)
        pdf.multi_cell(0, 6, f"{', '.join(diag)}"); pdf.ln(3)

    # Rx
    if meds:
        pdf.set_font('Arial', 'B', 12); pdf.set_text_color(44, 122, 111)
        pdf.cell(0, 8, "Prescription", 0, 1)
        pdf.set_font('Arial', '', 11); pdf.set_text_color(0)
        for m in meds: pdf.cell(0, 6, f"- {m}", 0, 1)
        pdf.ln(3)

    # Invoice
    pdf.set_font('Arial', 'B', 12); pdf.set_text_color(44, 122, 111)
    pdf.cell(0, 8, "Invoice", 0, 1); pdf.set_text_color(0)
    if tx_reason: pdf.invoice_row(tx_reason, amount)
    pdf.invoice_row("Total", amount, True)
    pdf.invoice_row("Paid", paid)
    pdf.invoice_row("Due", due, True)
    
    filename = f"{name.replace(' ', '_')}_Invoice.pdf"
    path = os.path.join(PRESCRIPTION_FOLDER, filename)
    pdf.output(path)
    return path, filename

# ==========================================
# 4. APP INTERFACE
# ==========================================

# HEADER
c1, c2 = st.columns([1, 5])
with c1:
    if os.path.exists(LOGO_FILENAME): st.image(LOGO_FILENAME, width=70)
with c2:
    st.markdown("<h2 style='color:#2C7A6F; margin-top:10px;'>Sudantam OS</h2>", unsafe_allow_html=True)

# TABS (Top Navigation)
tabs = st.tabs(["➕ NEW PATIENT", "💊 RX & BILL", "📂 RECORDS", "💰 DUES", "🔧 TOOLS"])

# --- TAB 1: NEW PATIENT ---
with tabs[0]:
    st.subheader("Patient Registration")
    with st.form("reg_form"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Full Name")
        phone = c2.text_input("Mobile Number")
        
        c3, c4 = st.columns(2)
        age = c3.number_input("Age", 1, 100)
        gender = c4.selectbox("Gender", ["Male", "Female", "Other"])
        
        st.markdown("**Medical History**")
        mh = st.multiselect("Select Conditions", ["Diabetes", "Hypertension (BP)", "Thyroid", "Asthma", "Drug Allergy", "Cardiac Issues"])
        
        if st.form_submit_button("✅ Register Patient"):
            if not name:
                st.error("Name is required!")
            else:
                new_row = {
                    "Patient ID": len(df)+101, "Name": name, "Age": age, "Gender": gender, "Contact": phone,
                    "Last Visit": datetime.date.today().strftime("%d-%m-%Y"),
                    "Medical History": ", ".join(mh), "Pending Amount": 0, "Visit Log": ""
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(df)
                st.success(f"Successfully Registered: {name}")

# --- TAB 2: RX & INVOICE (Full Features) ---
with tabs[1]:
    st.subheader("Treatment & Billing")
    pt_name = st.selectbox("🔍 Search Patient", [""] + df["Name"].tolist())
    
    if pt_name:
        idx = df.index[df["Name"] == pt_name].tolist()[0]
        row = df.iloc[idx]
        
        # 1. Tooth Chart (Visual)
        st.info("🦷 Tooth Selection")
        if os.path.exists(TOOTH_CHART_FILENAME):
            st.image(TOOTH_CHART_FILENAME, caption="Reference Chart", use_container_width=True)
        
        c_t1, c_t2, c_t3 = st.columns(3)
        sel_teeth = []
        if c_t1.checkbox("UR Quadrant (1-8)"): sel_teeth.append("UR Quad")
        if c_t2.checkbox("UL Quadrant (1-8)"): sel_teeth.append("UL Quad")
        if c_t3.checkbox("Lower Arch"): sel_teeth.append("Lower Arch")
        specific_teeth = st.text_input("Specific Teeth (e.g., 36, 46)")
        if specific_teeth: sel_teeth.append(specific_teeth)
        
        # 2. Clinical Notes
        st.write("---")
        c1, c2 = st.columns(2)
        diag = c1.multiselect("Diagnosis", ["Dental Caries", "Pulpitis", "Periodontitis", "Gingivitis", "Fractured Tooth", "Missing Tooth"])
        tx_reason = c2.text_input("Procedure Done (e.g., RCT, Extraction)")
        
        # 3. Prescription
        st.write("---")
        st.markdown("**💊 Prescription**")
        meds = st.multiselect("Medicines", ["Amoxicillin 500mg", "Augmentin 625mg", "Zerodol-SP", "Ketorol DT", "Metrogyl 400mg", "Pan-D", "Chymoral Forte"])
        
        # 4. Billing
        st.write("---")
        st.markdown(f"**💰 Billing (Pending: ₹{row['Pending Amount']})**")
        c_b1, c_b2 = st.columns(2)
        amount = c_b1.number_input("Total Bill", step=100)
        paid = c_b2.number_input("Amount Paid Now", step=100)
        
        if st.button("💾 SAVE & PRINT INVOICE"):
            # Calc
            due = amount - paid
            old_due = float(row['Pending Amount']) if row['Pending Amount'] else 0
            total_due = old_due + due
            
            # Save
            log = f"\n📅 {datetime.date.today()} | Tx: {tx_reason} | Bill: {amount} | Paid: {paid}"
            df.at[idx, "Visit Log"] = str(row['Visit Log']) + log
            df.at[idx, "Pending Amount"] = total_due
            save_data(df)
            
            # PDF
            pdf_path, pdf_name = generate_pdf_file(pt_name, str(row['Age']), datetime.date.today().strftime("%d-%m-%Y"), diag, meds, tx_reason, amount, paid, total_due)
            
            st.success("Saved!")
            with open(pdf_path, "rb") as f:
                st.download_button("🖨️ Download PDF", f, file_name=pdf_name, mime="application/pdf")

# --- TAB 3: RECORDS (Full Registry) ---
with tabs[2]:
    st.subheader("Patient Records")
    # Show last 5 added by default
    st.write("Recently Added:")
    st.dataframe(df.tail(5)[["Name", "Contact", "Last Visit"]])
    
    st.write("---")
    q = st.text_input("🔍 Search Database")
    if q:
        res = df[df["Name"].str.contains(q, case=False, na=False)]
        for i, r in res.iterrows():
            with st.expander(f"📄 {r['Name']} (Age: {r['Age']})"):
                st.write(f"**Phone:** {r['Contact']}")
                st.write(f"**Medical Hx:** {r['Medical History']}")
                st.error(f"**Dues:** ₹{r['Pending Amount']}")
                st.text_area("Visit Log", r['Visit Log'], height=100)

# --- TAB 4: DUES ---
with tabs[3]:
    st.subheader("Payment Defaulters")
    df["Pending Amount"] = pd.to_numeric(df["Pending Amount"], errors='coerce').fillna(0)
    dues = df[df["Pending Amount"] > 0]
    
    if dues.empty: st.success("No pending dues!")
    else:
        st.dataframe(dues[["Name", "Contact", "Pending Amount"]])

# --- TAB 5: TOOLS ---
with tabs[4]:
    st.subheader("System Tools")
    if st.button("🔄 Force Sync Cloud Data"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()
