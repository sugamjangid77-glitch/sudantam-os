import streamlit as st
import pandas as pd
import datetime
import os
import urllib.parse
import json
import base64
from fpdf import FPDF

# ==========================================
# 1. CONFIG & HIGH-CONTRAST THEME
# ==========================================
st.set_page_config(page_title="Sudantam OS", layout="wide", page_icon="🦷")

st.markdown("""
    <style>
        /* 1. Global White Theme */
        .stApp {
            background-color: #FFFFFF;
            color: #000000;
        }
        
        /* 2. TAB STYLING (The Fix) */
        /* Container for tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 5px;
            background-color: #ffffff;
            padding: 5px;
        }
        /* Unselected Tabs: White Back, Black Text */
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            background-color: #FFFFFF !important;
            color: #000000 !important;
            border: 1px solid #ced4da; /* Grey border to see the box */
            border-radius: 5px;
            font-weight: bold;
            font-size: 16px;
        }
        /* Selected Tab: Teal Back, White Text */
        .stTabs [aria-selected="true"] {
            background-color: #2C7A6F !important;
            color: #FFFFFF !important;
            border: none;
        }

        /* 3. INPUTS & DROPDOWNS */
        .stTextInput, .stNumberInput, .stSelectbox, .stTextArea {
            font-size: 16px;
            color: black !important;
        }
        
        /* Force dropdown backgrounds to be white */
        div[data-baseweb="select"] > div {
            background-color: #F8F9FA !important;
            border: 1px solid #ced4da !important;
            color: black !important;
        }
        
        /* 4. BUTTONS */
        div.stButton > button {
            background-color: #2C7A6F !important;
            color: white !important;
            border-radius: 8px;
            height: 50px;
            width: 100%;
            border: none;
            font-weight: bold;
            font-size: 16px;
        }
        
        /* Whatsapp Button Style */
        .stLinkButton > a {
            background-color: #25D366 !important;
            color: white !important;
            border-radius: 8px;
            height: 50px;
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            text-decoration: none;
        }

        #MainMenu, footer, header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# Constants
PRESCRIPTION_FOLDER = "Prescriptions"
LOCAL_DB_FILE = "sudantam_patients.csv"
LOGO_FILENAME = "logo.jpeg"

if not os.path.exists(PRESCRIPTION_FOLDER): os.makedirs(PRESCRIPTION_FOLDER)

# ==========================================
# 2. CLOUD SYNC
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

    def invoice_row(self, item, price, bold=False):
        self.set_font('Arial', 'B' if bold else '', 11)
        self.cell(145, 8, f" {item}", 1, 0, 'L')
        self.cell(45, 8, f"{price} ", 1, 1, 'R')

def generate_pdf_file(name, age, date, diag, meds, tx_reason, teeth, amount, paid, due):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12); pdf.set_text_color(0)
    pdf.cell(0, 10, f"Patient: {name} ({age} Yrs)  |  Date: {date}", 0, 1, 'L')
    pdf.ln(2)
    
    if diag:
        pdf.set_font('Arial', 'B', 12); pdf.set_text_color(44, 122, 111); pdf.cell(0, 8, "Diagnosis", 0, 1)
        pdf.set_font('Arial', '', 11); pdf.set_text_color(0); pdf.multi_cell(0, 6, f"{', '.join(diag)}"); pdf.ln(3)

    if teeth:
        pdf.set_font('Arial', 'B', 12); pdf.set_text_color(44, 122, 111); pdf.cell(0, 8, "Teeth Treated (FDI)", 0, 1)
        pdf.set_font('Arial', '', 11); pdf.set_text_color(0); pdf.cell(0, 6, f"{teeth}", 0, 1); pdf.ln(3)

    if meds:
        pdf.set_font('Arial', 'B', 12); pdf.set_text_color(44, 122, 111); pdf.cell(0, 8, "Prescription", 0, 1)
        pdf.set_font('Arial', '', 11); pdf.set_text_color(0)
        for m in meds: pdf.cell(0, 6, f"- {m}", 0, 1)
        pdf.ln(3)

    pdf.set_font('Arial', 'B', 12); pdf.set_text_color(44, 122, 111); pdf.cell(0, 8, "Invoice", 0, 1); pdf.set_text_color(0)
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
c1, c2 = st.columns([1, 5])
with c1: 
    if os.path.exists(LOGO_FILENAME): st.image(LOGO_FILENAME, width=70)
with c2: st.markdown("### Sudantam OS")

tabs = st.tabs(["➕ NEW", "🦷 CLINICAL", "📂 RECORDS", "💰 DUES", "🔧 SYNC"])

# --- TAB 1: NEW ---
with tabs[0]:
    st.subheader("Register New Patient")
    with st.form("reg"):
        name = st.text_input("Patient Name")
        phone = st.text_input("Phone Number")
        
        c1, c2 = st.columns(2)
        with c1: age = st.number_input("Age", min_value=1, max_value=100, step=1)
        with c2: gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            
        mh = st.multiselect("Medical History", ["Diabetes", "BP", "Thyroid", "Asthma", "Allergy"])
        
        if st.form_submit_button("✅ Register Patient"):
            if not name:
                st.error("Enter Name")
            else:
                new_row = {"Patient ID": len(df)+101, "Name": name, "Age": age, "Gender": gender, "Contact": phone, "Last Visit": datetime.date.today().strftime("%d-%m-%Y"), "Medical History": ", ".join(mh), "Pending Amount": 0, "Visit Log": ""}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(df)
                st.success(f"Registered: {name}")

# --- TAB 2: CLINICAL (FDI) ---
with tabs[1]:
    st.subheader("Treatment & Billing")
    pt_name = st.selectbox("Select Patient", [""] + df["Name"].tolist())
    
    if pt_name:
        idx = df.index[df["Name"] == pt_name].tolist()[0]
        row = df.iloc[idx]
        
        # Grid Layout for Tooth Chart
        st.info("🦷 FDI Tooth Selector")
        st.caption("Select teeth from the quadrants below:")
        
        c1, c2 = st.columns(2)
        with c1:
            ur = st.multiselect("Upper Right (18-11)", ["18","17","16","15","14","13","12","11"])
        with c2:
            ul = st.multiselect("Upper Left (21-28)", ["21","22","23","24","25","26","27","28"])
        
        c3, c4 = st.columns(2)
        with c3:
            lr = st.multiselect("Lower Right (48-41)", ["48","47","46","45","44","43","42","41"])
        with c4:
            ll = st.multiselect("Lower Left (31-38)", ["31","32","33","34","35","36","37","38"])

        all_selected = ur + ul + ll + lr
        fdi_str = ", ".join(all_selected)
        if fdi_str: st.success(f"Selected: {fdi_str}")

        st.write("---")
        diag = st.multiselect("Diagnosis", ["Caries", "Pulpitis", "Periodontitis", "Fractured"])
        meds = st.multiselect("Medicines", ["Amoxicillin 500", "Augmentin 625", "Zerodol-SP", "Ketorol DT", "Pan-D", "Metrogyl 400"])
        
        tx_reason = st.text_input("Treatment Done")
        
        c1, c2 = st.columns(2)
        with c1: amount = st.number_input("Total Bill", step=100)
        with c2: paid = st.number_input("Paid Now", step=100)
        
        if st.button("💾 Save & Generate PDF"):
            due = (amount - paid) + (float(row['Pending Amount']) if row['Pending Amount'] else 0)
            log = f"\n📅 {datetime.date.today()} | Tx: {tx_reason} | Teeth: {fdi_str} | Paid: {paid}"
            df.at[idx, "Visit Log"] = str(row['Visit Log']) + log
            df.at[idx, "Pending Amount"] = due
            df.at[idx, "Affected Teeth"] = fdi_str
            save_data(df)
            
            pdf_path, pdf_name = generate_pdf_file(pt_name, str(row['Age']), datetime.date.today().strftime("%d-%m-%Y"), diag, meds, tx_reason, fdi_str, amount, paid, due)
            st.success("✅ Saved!")
            with open(pdf_path, "rb") as f:
                st.download_button("🖨️ Download Invoice PDF", f, file_name=pdf_name, mime="application/pdf")

# --- TAB 3: RECORDS (With Messaging) ---
with tabs[2]:
    st.subheader("Patient Records")
    q = st.text_input("🔍 Search Name (Type to find)")
    
    if q:
        res = df[df["Name"].str.contains(q, case=False, na=False)]
        for i, r in res.iterrows():
            with st.expander(f"{r['Name']} (Age: {r['Age']})"):
                # Contact Info & Message Button
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.write(f"📞 **Phone:** {r['Contact']}")
                    st.write(f"⚠️ **Medical Hx:** {r['Medical History']}")
                    st.info(f"💰 **Pending Due:** ₹{r['Pending Amount']}")
                with c2:
                    if r['Contact']:
                        msg = f"Hello {r['Name']}, this is Dr. Sugam from Sudantam Dental Clinic."
                        link = f"https://wa.me/91{r['Contact']}?text={urllib.parse.quote(msg)}"
                        st.link_button("📲 Chat", link)
                
                # History Log
                st.write("---")
                st.write("**Visit History:**")
                st.text(r['Visit Log'])

# --- TAB 4: DUES ---
with tabs[3]:
    st.subheader("Payment Defaulters")
    df["Pending Amount"] = pd.to_numeric(df["Pending Amount"], errors='coerce').fillna(0)
    defaulters = df[df["Pending Amount"] > 0]
    
    if not defaulters.empty:
        st.dataframe(defaulters[["Name", "Contact", "Pending Amount"]])
        
        st.markdown("#### Clear Dues")
        pay_name = st.selectbox("Select Patient to Pay", defaulters["Name"].unique())
        
        if pay_name:
            pay_idx = df.index[df["Name"] == pay_name].tolist()[0]
            curr = df.at[pay_idx, "Pending Amount"]
            st.info(f"Current Due: ₹{curr}")
            
            pay_now = st.number_input("Amount Received", min_value=0.0, max_value=float(curr), step=100.0)
            
            if st.button("✅ Update Balance"):
                df.at[pay_idx, "Pending Amount"] = curr - pay_now
                save_data(df)
                st.success("Balance Updated!")
                st.rerun()
    else:
        st.success("No Pending Dues!")

# --- TAB 5: SYNC ---
with tabs[4]:
    st.subheader("Settings")
    if st.button("🔄 Force Cloud Sync"):
        st.cache_resource.clear()
        st.rerun()
