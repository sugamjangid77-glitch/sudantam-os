import streamlit as st
import pandas as pd
import datetime
import os
import webbrowser
import subprocess
import urllib.parse
import socket
import time
from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 0. AUTO-GENERATE ASSETS (Prevents Crashes)
# ==========================================
def generate_assets():
    """Generates placeholder images if missing."""
    if not os.path.exists("logo.jpeg"):
        try:
            img = Image.new('RGB', (200, 200), color='#2C7A6F')
            d = ImageDraw.Draw(img)
            d.text((50, 90), "Sudantam", fill=(255, 255, 255))
            img.save("logo.jpeg")
        except: pass
    
    if not os.path.exists("tooth_diagram.png"):
        try:
            img = Image.new('RGB', (400, 200), color='white')
            d = ImageDraw.Draw(img)
            d.text((10, 90), "Tooth Diagram Placeholder", fill=(0, 0, 0))
            img.save("tooth_diagram.png")
        except: pass

generate_assets()

# ==========================================
# 1. GOOGLE SHEETS CONFIGURATION (WITH FIX)
# ==========================================
# REPLACE THIS WITH YOUR SHEET ID
SHEET_ID = "120wdQHfL9mZB7OnYyHg-9o2Px-6cZogctcuNEHjhD9Q"

@st.cache_resource
def get_sheet_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = None
    if os.path.exists("key.json"):
        creds = Credentials.from_service_account_file("key.json", scopes=scope)
    else:
        st.error("⚠️ key.json not found. Please add your Google Cloud key.")
        return None
    
    # --- NETWORK FIX: RETRY LOGIC ---
    # Tries to connect 3 times before failing
    for attempt in range(3):
        try:
            client = gspread.authorize(creds)
            # Test connection by opening sheet
            return client.open_by_key(SHEET_ID)
        except Exception as e:
            if attempt < 2:
                time.sleep(2) # Wait 2 seconds and try again
                continue
            else:
                st.error(f"⚠️ Connection Failed after 3 tries. Check Internet/VPN. Error: {e}")
                return None

# --- DATA LOADING (Google Sheets Version) ---
def load_data():
    """Loads Patients from 'Patients' tab."""
    sh = get_sheet_client()
    if not sh: return pd.DataFrame()
    try:
        ws = sh.worksheet("Patients")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        # Ensure columns exist
        cols = ["Patient ID", "Name", "Age", "Gender", "Contact", "Last Visit", "Next Appointment", "Treatment Notes", "Medical History", "Treatments Done", "Affected Teeth", "Pending Amount"]
        for c in cols:
            if c not in df.columns: df[c] = ""
        # Fix numeric types
        df["Pending Amount"] = pd.to_numeric(df["Pending Amount"], errors='coerce').fillna(0)
        return df
    except gspread.WorksheetNotFound:
        # Create if missing
        ws = sh.add_worksheet(title="Patients", rows=100, cols=20)
        ws.append_row(["Patient ID", "Name", "Age", "Gender", "Contact", "Last Visit", "Next Appointment", "Treatment Notes", "Medical History", "Treatments Done", "Affected Teeth", "Pending Amount"])
        return pd.DataFrame(columns=["Patient ID", "Name", "Age", "Gender", "Contact", "Last Visit", "Next Appointment", "Treatment Notes", "Medical History", "Treatments Done", "Affected Teeth", "Pending Amount"])

def load_billing():
    """Loads Finances from 'Finances' tab."""
    sh = get_sheet_client()
    if not sh: return pd.DataFrame()
    try:
        ws = sh.worksheet("Finances")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        cols = ["Date", "Patient Name", "Treatments", "Total Amount", "Paid Amount", "Balance Due"]
        for c in cols:
            if c not in df.columns: df[c] = ""
        return df
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Finances", rows=100, cols=20)
        ws.append_row(["Date", "Patient Name", "Treatments", "Total Amount", "Paid Amount", "Balance Due"])
        return pd.DataFrame(columns=["Date", "Patient Name", "Treatments", "Total Amount", "Paid Amount", "Balance Due"])

def save_data(df):
    """Saves Patients to Google Sheet."""
    sh = get_sheet_client()
    if sh:
        try:
            ws = sh.worksheet("Patients")
            ws.clear()
            df = df.astype(str)
            ws.update([df.columns.values.tolist()] + df.values.tolist())
            st.cache_data.clear()
        except:
            st.warning("⚠️ Save failed (Network Issue). Retrying...")
            time.sleep(2)
            try:
                ws = sh.worksheet("Patients")
                ws.clear()
                df = df.astype(str)
                ws.update([df.columns.values.tolist()] + df.values.tolist())
                st.cache_data.clear()
            except:
                st.error("❌ Save Failed completely. Check Internet.")

def save_billing(df):
    """Saves Finances to Google Sheet."""
    sh = get_sheet_client()
    if sh:
        try:
            ws = sh.worksheet("Finances")
            ws.clear()
            df = df.astype(str)
            ws.update([df.columns.values.tolist()] + df.values.tolist())
            st.cache_data.clear()
        except:
            pass # Silent fail on billing backup

# ==========================================
# 2. APP CONFIGURATION
# ==========================================
FILE_NAME = "sudantam_patients.csv" # Kept for reference, but unused
BILLING_FILE = "sudantam_finances.csv" # Kept for reference, but unused
LOGO_FILENAME = "logo.jpeg"
DIAGRAM_FILENAME = "tooth_diagram.png"
PRESCRIPTION_FOLDER = "Prescriptions"

# --- THEME COLORS ---
PRIMARY_COLOR = "#2C7A6F"  
SECONDARY_COLOR = "#F0F8F5" 
TEXT_COLOR = "#1B5E55"

# --- STANDARD DATA LISTS ---
TREATMENT_PRICES = {
    "Consultation": 200, 
    "X-Ray (IOPA)": 150, 
    "Scaling & Polishing": 800, 
    "Extraction": 500, 
    "Restoration (Composite/GIC)": 1000, 
    "Root Canal (RCT)": 3500, 
    "Crown (Metal)": 2000, 
    "Crown (Ceramic)": 4000, 
    "Implant": 15000, 
    "Orthodontics (Braces)": 25000, 
    "Bleaching (Whitening)": 5000,
    "Complete Denture": 12000,
    "RPD (Partial Denture)": 3000
}

MED_HISTORY_OPTIONS = ["Diabetes", "Hypertension", "Thyroid", "Cardiac History", "Allergy", "Pregnancy", "Currently on medication"]

COMMON_DIAGNOSES = [
    "Dental Caries (Decay)", "Grossly Decayed Tooth", "Periapical Abscess", 
    "Gingival Abscess", "Periodontitis (Gum Disease)", "Gingivitis",
    "Fractured Tooth / Cracked Tooth", "Mobile Tooth", "Impacted Wisdom Tooth",
    "Pulpitis (Sensitivity/Pain)", "Apthous Ulcer", "Mucocele", "Leukoplakia", "Traumatic Ulcer"
]

COMMON_ADVICED_TREATMENTS = list(TREATMENT_PRICES.keys()) + ["Operculectomy", "Flap Surgery", "Medicine Only"]

COMMON_MEDICINES = [
    "Tab Augmentin 625mg (1-0-1 x 5 Days) [Antibiotic]",
    "Tab Amoxicillin 500mg (1-1-1 x 5 Days) [Antibiotic]",
    "Tab Metrogyl 400mg (1-0-1 x 5 Days) [Antibiotic]",
    "Tab Zerodol-SP (1-0-1 x 3 Days) [Painkiller]",
    "Tab Enzoflam (1-0-1 x 3 Days) [Painkiller]",
    "Tab Ketorol-DT (2 tablets SOS) [Painkiller]",
    "Tab Pan-D (1-0-0 Empty Stomach) [Antacid]",
    "Mouthwash Hexidine (Rinse twice daily)", "Gel Metrohex (Apply on gums)"
]

COMMON_INSTRUCTIONS = [
    "Warm saline rinses 3-4 times a day.", "Soft diet for 24 hours.", "Avoid hot/spicy food.",
    "Take medicines after food.", "Do not spit or rinse for 24 hours (if extraction done)."
]

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        IP = s.getsockname()[0]
    except Exception:
        IP = "127.0.0.1"
    finally:
        s.close()
    return IP

class PDF(FPDF):
    def header(self):
        if os.path.exists(LOGO_FILENAME): self.image(LOGO_FILENAME, 10, 8, 28)
        self.set_font('Arial', 'B', 16)
        self.set_text_color(27, 94, 85)
        self.cell(0, 8, 'Dr. Sugam Jangid', 0, 1, 'R')
        self.set_font('Arial', 'I', 10)
        self.set_text_color(50, 50, 50)
        self.cell(0, 5, 'Dental Surgeon (BDS)', 0, 1, 'R')
        self.cell(0, 5, 'Reg No: A-9254', 0, 1, 'R')
        self.cell(0, 5, '+91-8078656835', 0, 1, 'R')
        self.ln(5)
        self.set_draw_color(27, 94, 85)
        self.set_line_width(0.5)
        self.line(10, 38, 200, 38) 
        self.ln(10)

    def footer(self):
        self.set_y(-25)
        self.set_font('Arial', 'I', 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, 'Opposite Agrasen Bhawan, Madanganj, Kishangarh - 305801', 0, 1, 'C')
        self.cell(0, 5, 'Timing: 9 AM to 2 PM  &  4 PM to 8 PM', 0, 1, 'C')

def create_checkbox_grid(options_list, num_columns=3):
    selected_items = []
    cols = st.columns(num_columns)
    for i, option in enumerate(options_list):
        with cols[i % num_columns]:
            if st.checkbox(option): selected_items.append(option)
    return ", ".join(selected_items)

def render_tooth_diagram():
    st.info("Select affected teeth")
    selected_teeth = []
    col1, col2 = st.columns(2)
    with col1:
        st.caption("Left Side")
        ul = st.columns(8)
        for i in range(8, 0, -1):
            with ul[8-i]: 
                if st.checkbox(f"{i}", key=f"UL{i}"): selected_teeth.append(f"UL{i}")
        st.write("---")
        ll = st.columns(8)
        for i in range(8, 0, -1):
            with ll[8-i]: 
                if st.checkbox(f"{i}", key=f"LL{i}"): selected_teeth.append(f"LL{i}")
    with col2:
        st.caption("Right Side")
        ur = st.columns(8)
        for i in range(1, 9):
            with ur[i-1]: 
                if st.checkbox(f"{i}", key=f"UR{i}"): selected_teeth.append(f"UR{i}")
        st.write("---")
        lr = st.columns(8)
        for i in range(1, 9):
            with lr[i-1]: 
                if st.checkbox(f"{i}", key=f"LR{i}"): selected_teeth.append(f"LR{i}")
    return ", ".join(selected_teeth)

def generate_vcf(dataframe):
    vcf_content = ""
    for index, row in dataframe.iterrows():
        name = row['Name']
        phone = str(row['Contact']).replace(" ", "").replace("-", "")
        vcf_content += f"BEGIN:VCARD\nVERSION:3.0\nFN:pt {name}\nTEL;TYPE=CELL:{phone}\nEND:VCARD\n"
    return vcf_content

# --- App Interface & Styling ---
st.set_page_config(page_title="Sudantam Dental Clinic", layout="wide")

st.markdown(f"""
<style>
    [data-testid="stSidebar"] {{ background-color: {SECONDARY_COLOR}; }}
    [data-testid="stSidebar"] div[role="radiogroup"] {{ display: flex; flex-direction: column; gap: 12px; }}
    [data-testid="stSidebar"] div[role="radiogroup"] label {{
        background-color: white !important; padding: 18px !important;
        border-radius: 15px !important; box-shadow: 0 2px 5px rgba(0,0,0,0.05) !important;
        border: 2px solid transparent !important; margin: 0 !important; width: 100% !important;
        font-size: 18px !important; color: #444 !important;
    }}
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] {{
        background-color: {PRIMARY_COLOR} !important; color: white !important;
    }}
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{ display: none; }}
    div.stButton > button {{
        width: 100%; background-color: {PRIMARY_COLOR}; color: white; height: 50px;
        font-size: 18px !important; border-radius: 8px; border: none; transition: 0.3s;
    }}
    div.stButton > button:hover {{ background-color: #1B5E55; box-shadow: 0 5px 10px rgba(0,0,0,0.2); }}
    @keyframes pulse-red {{
        0% {{ box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.7); }}
        70% {{ box-shadow: 0 0 0 15px rgba(255, 0, 0, 0); }}
        100% {{ box-shadow: 0 0 0 0 rgba(255, 0, 0, 0); }}
    }}
    .urgent-alert {{
        animation: pulse-red 2s infinite; background-color: #ffe6e6; border: 2px solid #ff4d4d;
        color: #cc0000; padding: 15px; border-radius: 10px; font-weight: bold; text-align: center; margin-bottom: 20px;
    }}
</style>
""", unsafe_allow_html=True)

# LOAD DATA FROM GOOGLE SHEETS
df = load_data()
billing_df = load_billing()

if not os.path.exists(PRESCRIPTION_FOLDER): os.makedirs(PRESCRIPTION_FOLDER)

# --- SIDEBAR MENU ---
with st.sidebar:
    if os.path.exists(LOGO_FILENAME): st.image(Image.open(LOGO_FILENAME), use_container_width=True)
    else: st.title("🦷 Sudantam")
    st.write("") 
    
    menu_options = ["➕  Add New Patient", "💊  Actions (Rx & Bill)", "📢  Marketing / WhatsApp", "💰  Manage Defaulters", "🔧  Manage Data", "🔍  Search Registry", "🗓️  Today's Queue"]
    choice = st.radio("Main Menu", menu_options, label_visibility="collapsed")
    st.markdown("---")
    
    st.markdown(f"<h4 style='color:{PRIMARY_COLOR}'>📱 Mobile App Link</h4>", unsafe_allow_html=True)
    pc_ip = get_local_ip()
    mobile_url = f"http://{pc_ip}:8501"
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={mobile_url}"
    st.image(qr_url, caption="Scan with Phone to Open App", width=150)
    st.caption("1. Phone must be on same Wi-Fi.\n2. Scan QR.\n3. Tap 'Add to Home Screen'.")
    st.markdown("---")

    st.markdown(f"<h4 style='color:{PRIMARY_COLOR}'>🔔 Alerts</h4>", unsafe_allow_html=True)
    today_str = datetime.date.today().strftime("%d-%m-%Y")
    
    # Ensure correct data type for comparison
    df["Next Appointment"] = df["Next Appointment"].astype(str)
    
    apps_today = df[df["Next Appointment"] == today_str]
    if not apps_today.empty:
        st.markdown(f'<div class="urgent-alert">📞 {len(apps_today)} Appointments Today!</div>', unsafe_allow_html=True)
        with st.expander("View List"): st.dataframe(apps_today[["Name", "Contact"]], hide_index=True)
    else: st.success("✅ No appointments")

    pending_money = df[df["Pending Amount"] > 0]
    if not pending_money.empty:
        total_due = pending_money["Pending Amount"].sum()
        st.warning(f"💰 Due: ₹{total_due}")
        with st.expander("View Defaulters"): st.dataframe(pending_money[["Name", "Pending Amount"]], hide_index=True)
    else: st.success("✅ No pending dues")
    st.markdown("---")
    st.caption("Dr. Sugam | Sudantam Clinic")

# --- MAIN CONTENT ---
if choice == "➕  Add New Patient":
    st.header("📋 Register New Patient")
    with st.form("entry_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1: 
            name = st.text_input("Name*")
            age = st.number_input("Age", 1, 120)
            gender = st.selectbox("Gender", ["Male", "Female", "Other"])
        with c2: 
            contact = st.text_input("Phone Number*")
            visit_date = st.date_input("Date", datetime.date.today(), format="DD-MM-YYYY")
        
        st.markdown("---")
        c3, c4 = st.columns(2)
        with c3: 
            st.subheader("Medical History")
            hist = create_checkbox_grid(MED_HISTORY_OPTIONS, 2)
        with c4: 
            st.subheader("Treatments Done")
            treat = create_checkbox_grid(list(TREATMENT_PRICES.keys()), 2)
        st.markdown("---")
        teeth = render_tooth_diagram()
        st.markdown("---")
        c5, c6 = st.columns([2,1])
        with c5: notes = st.text_area("Notes")
        with c6: 
            schedule_next = st.checkbox("Schedule Next Visit?", value=True)
            if schedule_next:
                next_app_date = st.date_input("Next Visit Date", datetime.date.today() + datetime.timedelta(days=7), format="DD-MM-YYYY")
                next_app_str = next_app_date.strftime("%d-%m-%Y")
            else: next_app_str = "Not Required"

        if st.form_submit_button("✅ Save Patient Record"):
            if name and contact:
                new_id = len(df) + 101
                new_data = pd.DataFrame([{
                    "Patient ID": new_id, "Name": name, "Age": age, "Gender": gender, "Contact": contact,
                    "Last Visit": visit_date.strftime("%d-%m-%Y"), 
                    "Next Appointment": next_app_str,
                    "Treatment Notes": f"[Registered: {visit_date.strftime('%d-%m-%Y')}] {notes}", 
                    "Medical History": hist, "Treatments Done": treat, "Affected Teeth": teeth, "Pending Amount": 0
                }])
                df = pd.concat([df, new_data], ignore_index=True)
                save_data(df)
                st.success("Patient Saved Successfully!")
            else: st.error("Name & Phone Required")

elif choice == "💊  Actions (Rx & Bill)":
    st.header("📝 Visit Record (Rx & Invoice)")
    names_sorted = sorted(df["Name"].tolist())
    patient = st.selectbox("Select Patient", [""] + names_sorted)
    if patient:
        p_data = df[df["Name"] == patient].iloc[0]
        
        # --- NEW FEATURE: HISTORY VIEWER ---
        st.info(f"📜 **{patient}'s Medical History**")
        with st.expander("View Complete Visit Log", expanded=True):
            history_text = str(p_data.get("Treatment Notes", "No previous notes."))
            st.text_area("Past Notes & Treatments", value=history_text, height=150, disabled=True)
            
            prev_med_hist = str(p_data.get("Medical History", ""))
            if prev_med_hist:
                st.write(f"**Medical History:** {prev_med_hist}")

        st.markdown("---")

        # --- SECTION 1: PRESCRIPTION ---
        st.markdown("### 1. New Visit Entry (Rx)")
        col_diag, col_adv = st.columns(2)
        with col_diag: selected_diag = st.multiselect("Diagnosis / Findings:", COMMON_DIAGNOSES)
        with col_adv: selected_advice_treat = st.multiselect("Advised Treatment:", COMMON_ADVICED_TREATMENTS)
            
        col_med, col_inst = st.columns(2)
        with col_med: meds = st.multiselect("Medicines:", COMMON_MEDICINES)
        with col_inst: inst = st.multiselect("Instructions:", COMMON_INSTRUCTIONS)
        
        col_note, col_next_date = st.columns([2, 1])
        with col_note: custom_notes = st.text_area("Custom Notes (Rx)", height=60)
        with col_next_date: 
            schedule_next = st.checkbox("Schedule Next Visit?", value=True)
            try:
                existing_date_str = str(p_data["Next Appointment"])
                if existing_date_str == "Not Required" or existing_date_str == "nan": default_date = datetime.date.today() + datetime.timedelta(days=7)
                else: default_date = pd.to_datetime(existing_date_str, format="%d-%m-%Y").date()
            except: default_date = datetime.date.today() + datetime.timedelta(days=7)
            if schedule_next:
                new_next_visit_date = st.date_input("Date:", value=default_date, format="DD-MM-YYYY")
                final_next_visit_str = new_next_visit_date.strftime("%d-%m-%Y")
            else: final_next_visit_str = "Not Required"

        st.markdown("---")
        
        # --- SECTION 2: SMART INVOICE (Auto-Fill) ---
        st.markdown("### 2. Invoice Details")
        current_pending = float(p_data.get("Pending Amount", 0))
        if current_pending > 0: st.markdown(f'<div class="urgent-alert">⚠️ Patient has pending dues: ₹ {current_pending}</div><br>', unsafe_allow_html=True)
        
        valid_auto_select = [t for t in selected_advice_treat if t in TREATMENT_PRICES]
        
        sel_treats = st.multiselect(
            "Treatments Performed (Auto-Filled from Advice):", 
            options=list(TREATMENT_PRICES.keys()), 
            default=valid_auto_select
        )
        
        invoice_lines = []
        bill_total = 0
        if sel_treats:
            for t in sel_treats:
                c1, c2 = st.columns([3, 1])
                with c1: st.write(f"**{t}**")
                with c2: 
                    p = st.number_input(f"₹ Price ({t})", value=TREATMENT_PRICES[t], step=100)
                    bill_total += p
                    invoice_lines.append((t, p))
            
            st.markdown(f"#### Bill Total: ₹ {bill_total}")
            c_pay1, c_pay2 = st.columns(2)
            with c_pay1: amount_paid = st.number_input("Amount Paid Today", min_value=0, max_value=int(bill_total + current_pending), value=int(bill_total))
            final_balance = (bill_total + current_pending) - amount_paid
            with c_pay2:
                if final_balance > 0: st.warning(f"Remaining Balance: ₹ {final_balance}")
                elif final_balance < 0: st.success(f"Change to Return: ₹ {abs(final_balance)}")
                else: st.success("Full Payment Received ✅")
        else:
            amount_paid = 0
            final_balance = current_pending

        st.markdown("---")
        col_pdf, col_wa = st.columns([1, 1])
        today_date_str = datetime.date.today().strftime("%d-%m-%Y")
        pdf_filename = f"{patient}_{int(p_data['Age'])}_{today_date_str}.pdf"
        pdf_path = os.path.join(PRESCRIPTION_FOLDER, pdf_filename)
        
        with col_pdf:
            if st.button("🖨️ Generate PDF & Save"):
                # --- HISTORY APPEND LOGIC ---
                new_entry = f"\n\n--- VISIT: {today_date_str} ---\n"
                if selected_diag: new_entry += f"Diagnosis: {', '.join(selected_diag)}\n"
                if sel_treats: new_entry += f"Tx Done: {', '.join(sel_treats)}\n"
                if meds: new_entry += f"Meds: {', '.join(meds)}\n"
                if custom_notes: new_entry += f"Note: {custom_notes}"
                
                old_notes = str(p_data.get("Treatment Notes", ""))
                updated_notes = old_notes + new_entry
                
                df.loc[df["Name"] == patient, "Treatment Notes"] = updated_notes
                df.loc[df["Name"] == patient, "Next Appointment"] = final_next_visit_str
                if sel_treats or amount_paid > 0: 
                    df.loc[df["Name"] == patient, "Pending Amount"] = final_balance
                save_data(df)
                
                if sel_treats:
                    new_bill = pd.DataFrame([{ "Date": today_date_str, "Patient Name": patient, "Treatments": ", ".join([x[0] for x in invoice_lines]), "Total Amount": bill_total, "Paid Amount": amount_paid, "Balance Due": final_balance }])
                    billing_df = pd.concat([billing_df, new_bill], ignore_index=True)
                    save_billing(billing_df)
                
                pdf = PDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(30, 8, "Patient Name:", 0, 0)
                pdf.set_font("Arial", '', 11)
                pdf.cell(70, 8, patient, 0, 0)
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(20, 8, "Date:", 0, 0)
                pdf.set_font("Arial", '', 11)
                pdf.cell(40, 8, today_date_str, 0, 1)
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(30, 8, "Age/Sex:", 0, 0)
                pdf.set_font("Arial", '', 11)
                pdf.cell(70, 8, f"{p_data['Age']} / {p_data['Gender']}", 0, 0)
                pdf.set_font("Arial", 'B', 11)
                pdf.set_text_color(27, 94, 85)
                pdf.cell(35, 8, "Next Visit:", 0, 0)
                pdf.set_font("Arial", '', 11)
                pdf.set_text_color(0)
                pdf.cell(40, 8, final_next_visit_str, 0, 1)
                pdf.line(10, pdf.get_y()+2, 200, pdf.get_y()+2)
                pdf.ln(6)
                pdf.set_font("Arial", 'B', 12)
                pdf.set_text_color(27, 94, 85)
                pdf.cell(0, 8, "Diagnosis / Findings:", 0, 1)
                pdf.set_font("Arial", '', 11)
                pdf.set_text_color(0)
                if selected_diag:
                    for d in selected_diag: pdf.cell(10); pdf.cell(0, 6, f"- {d}", 0, 1)
                if pd.notna(p_data["Medical History"]) and p_data["Medical History"]: pdf.cell(10); pdf.cell(0, 6, f"History: {p_data['Medical History']}", 0, 1)
                pdf.ln(3)
                if selected_advice_treat:
                    pdf.set_font("Arial", 'B', 12)
                    pdf.set_text_color(27, 94, 85)
                    pdf.cell(0, 8, "Advised Treatment:", 0, 1)
                    pdf.set_font("Arial", '', 11)
                    pdf.set_text_color(0)
                    for t in selected_advice_treat: pdf.cell(10); pdf.cell(0, 6, f"- {t}", 0, 1)
                    pdf.ln(3)
                pdf.set_font("Arial", 'B', 14)
                pdf.set_text_color(27, 94, 85)
                pdf.cell(0, 10, "Rx (Medicines):", 0, 1)
                pdf.set_font("Arial", '', 11)
                pdf.set_text_color(0)
                idx = 1
                for m in meds: pdf.cell(10); pdf.cell(0, 7, f"{idx}. {m}", 0, 1); idx+=1
                if custom_notes:
                    for line in custom_notes.split('\n'): pdf.cell(10); pdf.cell(0, 7, f"{idx}. {line}", 0, 1); idx+=1
                pdf.ln(5)
                if inst:
                    pdf.set_font("Arial", 'B', 11)
                    pdf.set_text_color(27, 94, 85)
                    pdf.cell(0, 8, "Advice:", 0, 1)
                    pdf.set_font("Arial", '', 10)
                    pdf.set_text_color(0)
                    for i in inst: pdf.cell(10); pdf.cell(0, 6, f"- {i}", 0, 1)
                if os.path.exists(DIAGRAM_FILENAME): pdf.image(DIAGRAM_FILENAME, x=20, y=200, w=170)
                if sel_treats:
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 16)
                    pdf.set_text_color(0)
                    pdf.cell(0, 15, "INVOICE / RECEIPT", 0, 1, 'C')
                    pdf.set_font("Arial", '', 12)
                    pdf.cell(0, 10, f"Patient Name: {patient}", 0, 1)
                    pdf.cell(0, 10, f"Date: {today_date_str}", 0, 1)
                    pdf.line(10, 45, 200, 45)
                    pdf.ln(10)
                    pdf.set_fill_color(240, 248, 245)
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(140, 10, "Description", 1, 0, 'L', 1)
                    pdf.cell(50, 10, "Amount (INR)", 1, 1, 'R', 1)
                    pdf.set_font("Arial", '', 12)
                    for t, p in invoice_lines:
                        pdf.cell(140, 10, f" {t}", 1, 0)
                        pdf.cell(50, 10, f"{p} ", 1, 1, 'R')
                    pdf.ln(5)
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(140, 10, "Total Amount", 1, 0)
                    pdf.cell(50, 10, f"{bill_total}", 1, 1, 'R')
                    pdf.cell(140, 10, "Paid Today", 1, 0)
                    pdf.cell(50, 10, f"{amount_paid}", 1, 1, 'R')
                    if final_balance > 0:
                        pdf.set_text_color(200, 0, 0)
                        pdf.cell(140, 10, "Balance Due", 1, 0)
                        pdf.cell(50, 10, f"{final_balance}", 1, 1, 'R')
                pdf.output(pdf_path)
                try:
                    subprocess.Popen(f'explorer /select,"{os.path.abspath(pdf_path)}"')
                    st.success(f"Saved: {pdf_filename}")
                except: st.success("Saved! Check Prescriptions folder.")

        with col_wa:
            st.markdown("### 📲 Send")
            raw_phone = str(p_data['Contact']).replace(" ", "").replace("-", "")
            if not raw_phone.startswith("+"): raw_phone = "+91" + raw_phone 
            if sel_treats and final_balance > 0: msg = f"Hello {patient}, pending amount is Rs. {final_balance}. Please pay at next visit."
            else: msg = f"Hello {patient}, here is your digital record. - Sudantam Clinic"
            encoded_msg = urllib.parse.quote(msg)
            wa_link = f"https://web.whatsapp.com/send?phone={raw_phone}&text={encoded_msg}"
            st.markdown(f'''<a href="{wa_link}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:12px; border-radius:5px; font-weight:bold; cursor:pointer; width:100%;">1. Open WhatsApp</button></a><p style="font-size:12px; margin-top:5px;">2. Drag the highlighted file from the opened folder.</p>''', unsafe_allow_html=True)

elif choice == "📢  Marketing / WhatsApp":
    st.header("📢 Clinic Marketing & Mass Messaging")
    st.info("Download your contact list, save it to your phone, and perform a WhatsApp Broadcast.")
    filter_option = st.selectbox("Select Audience:", ["All Patients", "Defaulters (Pending Dues)", "Patients with Scheduled Next Visit"])
    filtered_df = df.copy()
    if filter_option == "Defaulters (Pending Dues)": filtered_df = df[df["Pending Amount"] > 0]
    elif filter_option == "Patients with Scheduled Next Visit": filtered_df = df[df["Next Appointment"] != "Not Required"]
    if filtered_df.empty: st.warning("No patients match this filter.")
    else:
        st.write(f"Found **{len(filtered_df)}** patients.")
        vcf_data = generate_vcf(filtered_df)
        st.download_button(label="📂 Download Phone Contacts (VCF)", data=vcf_data, file_name="Sudantam_Patients.vcf", mime="text/vcard")
        st.info("💡 **Instructions:** \n1. Download this file.\n2. Send it to your phone.\n3. Open it and tap 'Save All'.\n4. Search for **'pt '** in WhatsApp to verify they are saved.\n5. Create a Broadcast List and select all 'pt ...' contacts.")
        st.markdown("---")
        st.subheader("Or Send Manually (One by One)")
        default_msg = "Hello! Special offer at Sudantam Dental Clinic: 50% OFF on Scaling this week. Book now!"
        custom_msg = st.text_area("Message Content:", value=default_msg)
        for index, row in filtered_df.iterrows():
            c1, c2, c3 = st.columns([2, 2, 1])
            with c1: st.write(f"**{row['Name']}**")
            with c2: st.write(f"📞 {row['Contact']}")
            with c3:
                raw_phone = str(row['Contact']).replace(" ", "").replace("-", "")
                if not raw_phone.startswith("+"): raw_phone = "+91" + raw_phone
                final_msg = f"Hello {row['Name']}, {custom_msg}"
                encoded_msg = urllib.parse.quote(final_msg)
                link = f"https://web.whatsapp.com/send?phone={raw_phone}&text={encoded_msg}"
                st.markdown(f'''<a href="{link}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:5px 10px; border-radius:5px; cursor:pointer;">Send 📤</button></a>''', unsafe_allow_html=True)

elif choice == "💰  Manage Defaulters":
    st.header("💰 Manage Pending Dues")
    defaulters_df = df[df["Pending Amount"] > 0]
    if defaulters_df.empty: st.success("🎉 No pending dues! Everyone is paid up.")
    else:
        st.dataframe(defaulters_df[["Name", "Contact", "Pending Amount"]], use_container_width=True)
        st.markdown("---")
        target_person = st.selectbox("Select Patient to Update", defaulters_df["Name"].tolist())
        if target_person:
            idx = df.index[df["Name"] == target_person].tolist()[0]
            current_due = df.at[idx, "Pending Amount"]
            st.info(f"**{target_person}** currently owes **₹ {current_due}**")
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Edit Amount")
                new_val = st.number_input("New Pending Amount", value=int(current_due), step=100)
                if st.button("💾 Update Dues"):
                    df.at[idx, "Pending Amount"] = new_val
                    save_data(df)
                    st.success("Updated! Refreshing...")
                    st.rerun()
            with c2:
                st.subheader("Clear Entry")
                st.write("Remove from defaulters list?")
                if st.button("✅ Mark Paid (Clear 0)"):
                    df.at[idx, "Pending Amount"] = 0
                    save_data(df)
                    st.success("Cleared! Patient removed from defaulters.")
                    st.rerun()

elif choice == "🔧  Manage Data":
    st.header("🔧 Manage Patient Data")
    names_sorted = sorted(df["Name"].tolist())
    patient_to_edit = st.selectbox("Select Patient to Edit/Delete", [""] + names_sorted)
    if patient_to_edit:
        idx = df.index[df["Name"] == patient_to_edit].tolist()[0]
        p_data = df.iloc[idx]
        st.info(f"Editing: {patient_to_edit}")
        
        with st.expander("✏️ Edit Details", expanded=True):
            # Form block
            with st.form("edit_form"):
                c1, c2 = st.columns(2)
                new_name = c1.text_input("Name", value=p_data["Name"])
                new_age = c1.number_input("Age", value=int(p_data["Age"]))
                
                # Handle Gender Index Safely
                g_opts = ["Male", "Female", "Other"]
                try: g_idx = g_opts.index(p_data["Gender"])
                except: g_idx = 0
                new_gender = c2.selectbox("Gender", g_opts, index=g_idx)
                
                new_contact = c2.text_input("Contact", value=str(p_data["Contact"]))
                new_pending = st.number_input("Pending Amount Adjustment (₹)", value=int(p_data.get("Pending Amount", 0)))
                
                st.write("---")
                
                # Logic for Next Appointment Date
                existing_app_str = str(p_data.get("Next Appointment", "Not Required"))
                is_scheduled = (existing_app_str != "Not Required" and existing_app_str != "nan")
                schedule_edit = st.checkbox("Scheduled Next Visit?", value=is_scheduled)
                
                if schedule_edit:
                    try: def_date = pd.to_datetime(existing_app_str, format="%d-%m-%Y").date()
                    except: def_date = datetime.date.today() + datetime.timedelta(days=7)
                    new_app_date = st.date_input("Next Visit", value=def_date, format="DD-MM-YYYY")
                    final_edit_app_str = new_app_date.strftime("%d-%m-%Y")
                else: 
                    final_edit_app_str = "Not Required"

                submitted = st.form_submit_button("💾 Update Info")

                if submitted:
                    df.at[idx, "Name"] = new_name
                    df.at[idx, "Age"] = new_age
                    df.at[idx, "Gender"] = new_gender
                    df.at[idx, "Contact"] = new_contact
                    df.at[idx, "Pending Amount"] = new_pending
                    df.at[idx, "Next Appointment"] = final_edit_app_str
                    save_data(df)
                    st.success("Updated Successfully!")
                    st.rerun()

        with st.expander("❌ Delete Patient (Danger Zone)"):
            if st.button(f"🗑️ Delete {patient_to_edit}"):
                df = df.drop(idx)
                save_data(df)
                st.success("Deleted.")
                st.rerun()

elif choice == "🔍  Search Registry":
    st.header("🔍 Registry")
    q = st.text_input("Search Name")
    if q: st.dataframe(df[df["Name"].str.contains(q, case=False, na=False)], use_container_width=True)
    else: st.dataframe(df, use_container_width=True)

elif choice == "🗓️  Today's Queue":
    st.header("Today's Queue")
    today_str = datetime.date.today().strftime("%d-%m-%Y")
    st.table(df[df["Last Visit"] == today_str][["Name", "Contact", "Treatments Done"]])
