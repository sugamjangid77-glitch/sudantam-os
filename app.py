import streamlit as st
import pandas as pd
import datetime
import os
import urllib.parse
import json
import base64
from fpdf import FPDF

# Try importing Cloud libs
try:
    import gspread
    from google.oauth2.service_account import Credentials
    CLOUD_AVAILABLE = True
except ImportError:
    CLOUD_AVAILABLE = False

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

# Mobile-Friendly CSS
st.markdown(f"""
<style>
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
    
    /* BIG THUMB-FRIENDLY BUTTONS */
    div.stButton > button {{
        width: 100%;
        height: 60px;
        font-size: 18px;
        font-weight: bold;
        background-color: {PRIMARY_COLOR};
        color: white;
        border-radius: 12px;
        margin-bottom: 10px;
    }}
    /* TABS STYLING */
    .stSelectbox > div > div {{
        background-color: #f0f2f6;
        border-radius: 10px;
        font-weight: bold;
    }}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. PDF ENGINE (Restored)
# ==========================================
class PDF(FPDF):
    def header(self):
        # Simplified header for mobile PDF
        self.set_font('Arial', 'B', 20)
        self.set_text_color(44, 122, 111)
        self.cell(0, 10, 'Sudantam Dental Clinic', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.set_text_color(50)
        self.cell(0, 5, 'Dr. Sugam Jangid (BDS) | +91-8078656835', 0, 1, 'C')
        self.ln(5)
        self.set_draw_color(44, 122, 111)
        self.line(10, 25, 200, 25)
        self.ln(5)

    def patient_info(self, name, age, date):
        self.set_font('Arial', 'B', 12)
        self.set_text_color(0)
        self.cell(0, 10, f"Patient: {name} ({age} Yrs)  |  Date: {date}", 0, 1, 'L')
        self.ln(2)

    def invoice_row(self, item, price, bold=False):
        self.set_font('Arial', 'B' if bold else '', 11)
        self.cell(145, 8, f" {item}", 1, 0, 'L')
        self.cell(45, 8, f"{price} ", 1, 1, 'R')

def generate_pdf_file(name, age, date, diag, meds, tx_reason, amount, paid, due):
    pdf = PDF()
    pdf.add_page()
    
    # Info Block
    pdf.patient_info(name, age, date)
    
    # Clinical Notes
    if diag:
        pdf.set_font('Arial', 'B', 12); pdf.set_text_color(44, 122, 111)
        pdf.cell(0, 8, "Diagnosis & Findings", 0, 1)
        pdf.set_font('Arial', '', 11); pdf.set_text_color(0)
        pdf.multi_cell(0, 6, f"{', '.join(diag)}")
        pdf.ln(3)

    # Rx
    if meds:
        pdf.set_font('Arial', 'B', 12); pdf.set_text_color(44, 122, 111)
        pdf.cell(0, 8, "Prescription (Rx)", 0, 1)
        pdf.set_font('Arial', '', 11); pdf.set_text_color(0)
        for m in meds:
            pdf.cell(0, 6, f"- {m}", 0, 1)
        pdf.ln(3)

    # Invoice
    pdf.set_font('Arial', 'B', 12); pdf.set_text_color(44, 122, 111)
    pdf.cell(0, 8, "Invoice", 0, 1)
    pdf.set_text_color(0)
    
    if tx_reason: pdf.invoice_row(tx_reason, amount)
    pdf.invoice_row("Total Amount", amount, True)
    pdf.invoice_row("Paid", paid)
    pdf.invoice_row("Balance Due", due, True)
    
    # Save
    filename = f"{name.replace(' ', '_')}_Invoice.pdf"
    path = os.path.join(PRESCRIPTION_FOLDER, filename)
    pdf.output(path)
    return path, filename

# ==========================================
# 3. DATABASE SETUP
# ==========================================
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
    if pt_sheet:
        try:
            d = pt_sheet.get_all_records()
            if d: df = pd.DataFrame(d).astype(str)
        except: pass
    if df.empty and os.path.exists(LOCAL_DB_FILE):
        try: df = pd.read_csv(LOCAL_DB_FILE).astype(str)
        except: pass
    
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

df = load_data()

# ==========================================
# 4. APP INTERFACE
# ==========================================
c1, c2 = st.columns([1, 4])
with c1:
    if os.path.exists(LOGO_FILENAME): st.image(LOGO_FILENAME, width=60)
with c2:
    st.markdown("<h3 style='margin:0; padding-top:15px;'>Sudantam OS</h3>", unsafe_allow_html=True)

# NAV TABS
selected_tab = st.selectbox("⬇️ GO TO:", 
    ["➕ New Patient", "💊 Rx & Invoice", "📂 Registry", "💰 Manage Dues", "🔧 Tools"], index=0
)
st.markdown("---")

# --- TAB 1: REGISTER ---
if selected_tab == "➕ New Patient":
    st.subheader("Add New Patient")
    with st.form("reg"):
        name = st.text_input("Name")
        phone = st.text_input("Phone (10 digits)")
        c1, c2 = st.columns(2)
        age = c1.number_input("Age", 1, 100); gender = c2.selectbox("Sex", ["M", "F"])
        hist = st.multiselect("Medical History", ["Diabetes", "BP", "Thyroid", "Allergy"])
        if st.form_submit_button("✅ SAVE PATIENT"):
            new_row = {"Patient ID": len(df)+101, "Name": name, "Age": age, "Gender": gender, "Contact": phone, "Last Visit": datetime.date.today().strftime("%d-%m-%Y"), "Medical History": ", ".join(hist), "Pending Amount": 0, "Visit Log": ""}
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_data(df)
            st.success(f"Saved {name}!")

# --- TAB 2: RX & INVOICE (FIXED WITH PDF) ---
elif selected_tab == "💊 Rx & Invoice":
    st.subheader("Prescription & Bill")
    pt_name = st.selectbox("Select Patient", [""] + df["Name"].tolist())
    
    if pt_name:
        idx = df.index[df["Name"] == pt_name].tolist()[0]
        row = df.iloc[idx]
        
        # Clinical Inputs
        st.caption(f"Patient: {pt_name} | Due: {row['Pending Amount']}")
        diag = st.multiselect("Diagnosis", ["Caries", "Pain", "RCT Needed", "Extraction", "Cleaning"])
        meds = st.multiselect("Medicines", ["Amoxicillin", "Augmentin 625", "Zerodol-SP", "Dolo 650", "Metrogyl 400", "Pan-D", "Ketorol DT"])
        
        # Financial Inputs
        st.markdown("---")
        tx_reason = st.text_input("Treatment Done (e.g. RCT, Scaling)")
        c1, c2 = st.columns(2)
        amount = c1.number_input("Total Bill", step=100)
        paid = c2.number_input("Amount Paid", step=100)
        
        # Action Buttons
        if st.button("💾 SAVE & GENERATE PDF"):
            # 1. Calc Dues
            due = amount - paid
            old_due = float(row['Pending Amount']) if row['Pending Amount'] else 0
            total_due = old_due + due
            
            # 2. Update DB
            log = f"\n📅 {datetime.date.today()}\nTx: {tx_reason}\nBill: {amount}, Paid: {paid}\nRx: {', '.join(meds)}\n"
            df.at[idx, "Visit Log"] = str(row['Visit Log']) + log
            df.at[idx, "Pending Amount"] = total_due
            save_data(df)
            
            # 3. Generate PDF
            pdf_path, pdf_name = generate_pdf_file(
                pt_name, str(row['Age']), datetime.date.today().strftime("%d-%m-%Y"),
                diag, meds, tx_reason, amount, paid, total_due
            )
            
            # 4. Show Success & Download
            st.success("✅ Saved Successfully!")
            
            with open(pdf_path, "rb") as f:
                st.download_button(
                    label="🖨️ DOWNLOAD PDF INVOICE",
                    data=f,
                    file_name=pdf_name,
                    mime="application/pdf"
                )
            
            # 5. WhatsApp
            if row['Contact']:
                msg = f"Hello {pt_name}, Visit Summary:\nTx: {tx_reason}\nBill: {amount}\nPaid: {paid}\nDue: {total_due}\n\n- Sudantam Dental Clinic"
                link = f"https://wa.me/91{row['Contact']}?text={urllib.parse.quote(msg)}"
                st.link_button("📲 Open WhatsApp", link)

# --- TAB 3: REGISTRY ---
elif selected_tab == "📂 Registry":
    st.subheader("Patient Database")
    q = st.text_input("🔍 Search Name (Type to find)")
    if q:
        res = df[df["Name"].str.contains(q, case=False, na=False)]
        for i, r in res.iterrows():
            with st.expander(f"{r['Name']} (Age: {r['Age']})"):
                st.write(f"📞 {r['Contact']}")
                st.write(f"⚠️ {r['Medical History']}")
                st.text("History Log:\n" + str(r['Visit Log']))

# --- TAB 4: DUES ---
elif selected_tab == "💰 Manage Dues":
    st.subheader("Pending Payments")
    df["Pending Amount"] = pd.to_numeric(df["Pending Amount"], errors='coerce').fillna(0)
    dues = df[df["Pending Amount"] > 0]
    if dues.empty: st.success("No Dues!")
    else:
        for i, r in dues.iterrows():
            c1, c2 = st.columns([3, 1])
            c1.error(f"{r['Name']}: ₹{r['Pending Amount']}")
            if r['Contact']: 
                link = f"https://wa.me/91{r['Contact']}?text=Payment Reminder: Rs {r['Pending Amount']} due."
                c2.link_button("📲", link)

# --- TAB 5: TOOLS ---
elif selected_tab == "🔧 Tools":
    st.subheader("Tools")
    if st.button("☁️ Force Sync Cloud"):
        save_data(df); st.success("Synced!")
    
    up = st.file_uploader("Restore CSV (Laptop Data)")
    if up:
        old = pd.read_csv(up)
        df = pd.concat([df, old], ignore_index=True)
        save_data(df)
        st.success("Restored!")
