import streamlit as st
import pandas as pd
import datetime
import os
import socket
import time
import shutil
import urllib.parse
from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials

# --- AI AND VISION LIBRARIES ---
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# ==========================================
# 0. AUTO-GENERATE ASSETS
# ==========================================
def generate_assets():
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
    if not os.path.exists("review_qr.png"):
        try:
            img = Image.new('RGB', (200, 200), color='white')
            d = ImageDraw.Draw(img)
            d.rectangle([10, 10, 190, 190], outline="black", width=5)
            d.text((40, 90), "SCAN TO REVIEW", fill="black")
            img.save("review_qr.png")
        except: pass

generate_assets()

# --- MEDIA HELPERS ---
def rotate_image(img, angle_str):
    if angle_str == "90° Right": return img.rotate(-90, expand=True)
    elif angle_str == "180°": return img.rotate(180, expand=True)
    elif angle_str == "90° Left": return img.rotate(90, expand=True)
    return img

def enhance_before_image(image_pil):
    """Adds contrast and sharpens to highlight defects."""
    if not CV2_AVAILABLE: return image_pil
    img_cv = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)
    
    lab = cv2.cvtColor(img_cv, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    cl = clahe.apply(l)
    limg = cv2.merge((cl,a,b))
    contrast_img = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    
    gaussian = cv2.GaussianBlur(contrast_img, (9,9), 10.0)
    sharpened = cv2.addWeighted(contrast_img, 1.5, gaussian, -0.5, 0)
    
    return Image.fromarray(cv2.cvtColor(sharpened, cv2.COLOR_BGR2RGB))

def enhance_after_image(image_pil):
    """Smooths tissues, brightens, and polishes the look."""
    if not CV2_AVAILABLE: return image_pil
    img_cv = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)
    
    smooth = cv2.bilateralFilter(img_cv, d=9, sigmaColor=75, sigmaSpace=75)
    bright = cv2.convertScaleAbs(smooth, alpha=1.05, beta=15)
    
    hsv = cv2.cvtColor(bright, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    s = cv2.add(s, 10) 
    final_hsv = cv2.merge((h, s, v))
    final = cv2.cvtColor(final_hsv, cv2.HSV2BGR)
    
    return Image.fromarray(cv2.cvtColor(final, cv2.COLOR_BGR2RGB))

def rotate_frame(frame, angle_str):
    if angle_str == "90° Right": return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    elif angle_str == "180°": return cv2.rotate(frame, cv2.ROTATE_180)
    elif angle_str == "90° Left": return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame

# ==========================================
# 1. GOOGLE SHEETS & CACHE
# ==========================================
SHEET_ID = "120wdQHfL9mZB7OnYyHg-9o2Px-6cZogctcuNEHjhD9Q"

@st.cache_resource
def get_sheet_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = None
    try:
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    except: pass
    if not creds and os.path.exists("key.json"):
        creds = Credentials.from_service_account_file("key.json", scopes=scope)
    if not creds: return None
    for attempt in range(3):
        try: return gspread.authorize(creds).open_by_key(SHEET_ID)
        except: time.sleep(1)
    return None

@st.cache_data(ttl=60)
def load_data():
    standard_cols = ["Patient ID", "Name", "Age", "Gender", "Contact", "Last Visit", "Next Appointment", "Treatment Notes", "Medical History", "Treatments Done", "Affected Teeth", "Pending Amount"]
    sh = get_sheet_client()
    if not sh: return None
    for attempt in range(3):
        try:
            ws = sh.worksheet("Patients")
            df = pd.DataFrame(ws.get_all_records())
            for c in standard_cols:
                if c not in df.columns: df[c] = ""
            df["Pending Amount"] = pd.to_numeric(df["Pending Amount"], errors='coerce').fillna(0)
            return df
        except gspread.WorksheetNotFound:
            try:
                ws = sh.add_worksheet(title="Patients", rows=100, cols=20)
                ws.append_row(standard_cols)
                return pd.DataFrame(columns=standard_cols)
            except: pass
        except Exception as e:
            if attempt == 2: 
                st.error("⚠️ Connection Error. Safe-lock activated.")
                return None
            time.sleep(2) 

@st.cache_data(ttl=60)
def load_billing():
    sh = get_sheet_client()
    if not sh: return None
    for attempt in range(3):
        try:
            df = pd.DataFrame(sh.worksheet("Finances").get_all_records())
            df["Paid Amount"] = pd.to_numeric(df.get("Paid Amount", pd.Series()), errors='coerce').fillna(0)
            return df
        except: 
            if attempt == 2: return None
            time.sleep(2)

@st.cache_data(ttl=60)
def load_expenses():
    sh = get_sheet_client()
    if not sh: return None
    for attempt in range(3):
        try:
            df = pd.DataFrame(sh.worksheet("Expenses").get_all_records())
            df["Amount"] = pd.to_numeric(df.get("Amount", pd.Series()), errors='coerce').fillna(0)
            return df
        except:
            if attempt == 2: return None
            time.sleep(2)

@st.cache_data(ttl=60)
def load_lab_data():
    sh = get_sheet_client()
    if not sh: return None
    for attempt in range(3):
        try: return pd.DataFrame(sh.worksheet("LabWorks").get_all_records())
        except: 
            if attempt == 2: return None
            time.sleep(2)

@st.cache_data(ttl=60)
def load_inventory():
    standard_cols = ["Item Name", "Description", "Quantity", "Image_File"]
    sh = get_sheet_client()
    if not sh: return None
    for attempt in range(3):
        try:
            ws = sh.worksheet("Inventory")
            df = pd.DataFrame(ws.get_all_records())
            for c in standard_cols:
                if c not in df.columns: df[c] = ""
            df["Quantity"] = pd.to_numeric(df["Quantity"], errors='coerce').fillna(0).astype(int)
            return df
        except gspread.WorksheetNotFound:
            try:
                ws = sh.add_worksheet(title="Inventory", rows=100, cols=10)
                ws.append_row(standard_cols)
                return pd.DataFrame(columns=standard_cols)
            except: pass
        except Exception:
            if attempt == 2: return None
            time.sleep(2)

def save_data(df, ws_name):
    if df is None: return 
    sh = get_sheet_client()
    if sh:
        try:
            ws = sh.worksheet(ws_name)
            data_to_save = [df.columns.values.tolist()] + df.astype(str).values.tolist()
            ws.clear()
            try: ws.update("A1", data_to_save)
            except: ws.update(data_to_save)
            st.cache_data.clear()
        except: pass

def save_billing(df): save_data(df, "Finances")
def save_expenses(df): save_data(df, "Expenses")
def save_lab_data(df): save_data(df, "LabWorks")
def save_inventory(df): save_data(df, "Inventory")

# ==========================================
# 2. CONFIG & CONSTANTS
# ==========================================
LOGO_FILENAME = "logo.jpeg"
PRESCRIPTION_FOLDER = "Prescriptions"
CONSENT_FOLDER = "Consent_Forms"
GALLERY_FOLDER = "Patient_Gallery"
INVENTORY_FOLDER = "Inventory_Images"
CARESTREAM_EXPORT_FOLDER = "C:/Sudantam_XRays" 
PRIMARY_COLOR = "#2C7A6F"  
SECONDARY_COLOR = "#F0F8F5" 

TREATMENT_PRICES = {
    "Consultation": 200, "X-Ray (IOPA)": 150, "Scaling & Polishing": 800, "Deep Scaling / Root Planing": 1500,
    "Extraction (Simple)": 500, "Extraction (Surgical/Impaction)": 3000, "Extraction (Deciduous/Kids)": 300,
    "Restoration (GIC)": 800, "Restoration (Composite Anterior)": 1200, "Restoration (Composite Posterior)": 1500,
    "Pit & Fissure Sealant": 500, "Root Canal (Anterior)": 2500, "Root Canal (Posterior)": 3500, "Re-RCT": 4500,
    "Pulpectomy (Kids)": 2000, "Crown (Metal)": 2000, "Crown (PFM / Ceramic)": 4000, "Crown (Zirconia)": 7000,
    "Crown (E-Max / All Ceramic)": 8500, "Post & Core": 1500, "Complete Denture": 15000, "RPD (Acrylic)": 3000,
    "Cast Partial Denture": 8000, "Dental Implant": 20000, "Implant Crown": 8000, "Orthodontics (Metal Braces)": 25000,
    "Orthodontics (Ceramic Braces)": 35000, "Clear Aligners": 50000, "Retainers": 3000, "Bleaching (Whitening)": 5000,
    "Veneer (Composite)": 3000, "Veneer (Ceramic)": 8000, "Operculectomy": 1000, "Flap Surgery (Per Quad)": 4000,
    "Gingivectomy": 2000, "Splinting": 2500, "Space Maintainer": 1500
}

MED_HISTORY_OPTIONS = ["Diabetes", "Hypertension", "Thyroid", "Cardiac History", "Allergy", "Pregnancy", "Currently on medication"]
COMMON_DIAGNOSES = ["Dental Caries (Decay)", "Grossly Decayed Tooth", "Periapical Abscess", "Gingival Abscess", "Periodontitis (Gum Disease)", "Gingivitis", "Fractured Tooth / Cracked Tooth", "Mobile Tooth", "Impacted Wisdom Tooth", "Pulpitis (Sensitivity/Pain)", "Apthous Ulcer", "Mucocele", "Leukoplakia", "Traumatic Ulcer"]
COMMON_ADVICED_TREATMENTS = list(TREATMENT_PRICES.keys()) + ["Medicine Only"]

COMMON_MEDICINES = [
    "Tab Augmentin 625mg (1-0-1 x 5 Days)", "Tab Amoxicillin 500mg (1-1-1 x 5 Days)", "Tab Metrogyl 400mg (1-0-1 x 5 Days)",
    "Cap Clindamycin 300mg (1-0-1 x 5 Days)", "Tab Azithromycin 500mg (1-0-0 x 3 Days)", "Tab Cefixime 200mg (1-0-1 x 5 Days)",
    "Tab Zerodol-SP (1-0-1 x 3 Days)", "Tab Zerodol-P (1-0-1 x 3 Days)", "Tab Ketorol-DT 10mg (1 tab SOS for severe pain)",
    "Tab Combiflam (1-0-1 x 3 Days)", "Tab Enzoflam (1-0-1 x 3 Days)", "Tab Chymoral Forte (1-1-1 x 3 Days)",
    "Tab Dolo 650mg (1 tab SOS for fever/pain)", "Cap Pan-D (1-0-0 Empty Stomach x 5 Days)", "Tab Omee 20mg (1-0-0 Empty Stomach x 5 Days)",
    "Tab Myoril 4mg (1-0-1 x 3 Days)", "Cap Becosules Z (1-0-0 x 10 Days)", "Tab Limcee 500mg (1-0-0 x 15 Days)",
    "Mouthwash Hexidine 0.2% (Rinse twice daily x 15 Days)", "Mouthwash Betadine 2% (Rinse twice daily x 7 Days)",
    "Gel Metrohex (Apply on affected gums thrice daily)", "Gel Mucopain (Apply on ulcer 10 mins before meals)",
    "Paste Sensoform (Apply on sensitive teeth for 5 mins)", "Gum Paint Stolin (Massage on gums twice daily)"
]

COMMON_INSTRUCTIONS = ["Warm saline rinses 3-4 times a day.", "Soft diet for 24 hours.", "Avoid hot/spicy food.", "Take medicines after food.", "Do not spit or rinse for 24 hours (if extraction done)."]
CONSENT_TEMPLATES = {
    "Extraction (Tooth Removal)": "I hereby authorize Dr. Sugam Jangid to perform the extraction...",
    "Root Canal Treatment (RCT)": "I hereby authorize Dr. Sugam Jangid to perform Root Canal Treatment...",
    "Dental Implant Surgery": "I hereby authorize Dr. Sugam Jangid to place Dental Implants...",
    "Orthodontic Treatment (Braces)": "I hereby consent to Orthodontic treatment..."
}
EXPENSE_CATEGORIES = ["Materials/Consumables", "Lab Fees", "Salaries", "Utility Bills (Elec/Water)", "Maintenance/Repairs", "Marketing", "Rent", "Other"]

class PDF(FPDF):
    def header(self):
        if os.path.exists("logo.jpeg"): self.image("logo.jpeg", 10, 8, 25)
        self.set_font('Helvetica', 'B', 22); self.set_text_color(44, 122, 111)
        self.cell(0, 8, 'Sudantam Dental Clinic', 0, 1, 'R')
        self.set_font('Helvetica', 'B', 10); self.set_text_color(80, 80, 80)
        self.cell(0, 5, 'Dr. Sugam Jangid (BDS)', 0, 1, 'R')
        self.cell(0, 5, 'Reg No: A-9254 | +91-8078656835', 0, 1, 'R')
        self.set_font('Helvetica', '', 9)
        self.cell(0, 5, 'Opp. Agrasen Bhawan, Madanganj, Kishangarh - 305801', 0, 1, 'R')
        self.ln(5); self.set_draw_color(44, 122, 111); self.set_line_width(1.5)
        self.line(10, 38, 200, 38); self.ln(8)
    def footer(self):
        self.set_y(-15); self.set_font('Helvetica', 'I', 8); self.set_text_color(150, 150, 150)
        self.cell(0, 10, 'Sudantam Dental Clinic - Excellence in Dentistry', 0, 0, 'C')
    def add_qr_section(self):
        if os.path.exists("review_qr.png"):
            try:
                with Image.open("review_qr.png") as img:
                    img_w, img_h = img.size
            except:
                img_w, img_h = 1, 1

            y_current = self.get_y()
            safe_bottom = 275 
            space_left = safe_bottom - y_current

            if space_left < 40:
                self.add_page()
                y_current = self.get_y()
                space_left = safe_bottom - y_current
            
            self.ln(5)
            self.set_draw_color(200, 200, 200)
            self.set_line_width(0.5)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(5)
            self.set_font('Helvetica', 'B', 12)
            self.set_text_color(44, 122, 111)
            self.cell(0, 5, "Satisfied with your treatment?", 0, 1, 'C')
            self.set_font('Helvetica', '', 10)
            self.set_text_color(50, 50, 50)
            self.cell(0, 5, "Scan to leave us a 5-Star Google Review!", 0, 1, 'C')
            self.ln(2)
            
            y_img = self.get_y()
            max_img_h = safe_bottom - y_img 
            ratio = img_w / img_h
            
            target_h = min(max_img_h, 90)
            target_w = target_h * ratio
            
            if target_w > 150:
                target_w = 150
                target_h = target_w / ratio
                
            qr_x = (210 - target_w) / 2
            self.image("review_qr.png", x=qr_x, y=y_img, w=target_w, h=target_h)
            self.set_y(y_img + target_h)

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

def generate_wa_link(phone, message):
    phone = str(phone).replace(" ", "").replace("-", "")
    if not phone.startswith("+"): phone = "+91" + phone
    encoded_msg = urllib.parse.quote(message)
    return f"https://web.whatsapp.com/send?phone={phone}&text={encoded_msg}"

# --- APP START ---
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
    .urgent-alert {{
        background-color: #ffe6e6; border: 2px solid #ff4d4d;
        color: #cc0000; padding: 15px; border-radius: 10px; font-weight: bold; text-align: center; margin-bottom: 20px;
    }}
    .history-box {{
        background-color: #f8f9fa; padding: 25px; border-radius: 12px; 
        border-left: 6px solid {PRIMARY_COLOR}; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
        white-space: pre-wrap; line-height: 1.8; color: #333; font-size: 16px;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.05); margin-top: 10px; margin-bottom: 20px;
    }}
    .inv-card {{
        background-color: white; padding: 15px; border-radius: 10px; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.1); border-left: 4px solid {PRIMARY_COLOR};
        margin-bottom: 10px;
    }}
</style>
""", unsafe_allow_html=True)

df = load_data()
if df is None:
    st.stop()

billing_df = load_billing()
expenses_df = load_expenses()
lab_df = load_lab_data()
inventory_df = load_inventory()

for folder in [PRESCRIPTION_FOLDER, CONSENT_FOLDER, GALLERY_FOLDER, INVENTORY_FOLDER]:
    if not os.path.exists(folder): os.makedirs(folder)
if not os.path.exists(CARESTREAM_EXPORT_FOLDER): 
    try: os.makedirs(CARESTREAM_EXPORT_FOLDER)
    except: pass

with st.sidebar:
    if os.path.exists(LOGO_FILENAME): st.image(Image.open(LOGO_FILENAME), use_container_width=True)
    else: st.title("🦷 Sudantam")
    st.write("") 
    menu_options = [
        "➕  Add New Patient", 
        "💊  Actions (Rx & Bill)", 
        "💸  Expenses & Profit", 
        "📦  Inventory (Sustock)",
        "🧪  Lab Tracking", 
        "🧠  AI Assistant",
        "🧮  Pediatric Dosage", 
        "✍️  Consent Forms", 
        "📢  Marketing / WhatsApp", 
        "💰  Manage Defaulters", 
        "🔧  Manage Data", 
        "🔍  Search Registry", 
        "🗓️  Today's Queue"
    ]
    choice = st.radio("Main Menu", menu_options, label_visibility="collapsed")
    st.markdown("---")
    
    st.markdown(f"<h4 style='color:{PRIMARY_COLOR}'>🔔 Alerts</h4>", unsafe_allow_html=True)
    today_str = datetime.date.today().strftime("%d-%m-%Y")
    if not df.empty and "Next Appointment" in df.columns:
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
        else: st.success("✅ No pending dues")

if choice == "➕  Add New Patient":
    st.header("📋 Register New Patient")
    with st.form("entry_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1: name = st.text_input("Name*"); age = st.number_input("Age", 1, 120); gender = st.selectbox("Gender", ["Male", "Female", "Other"])
        with c2: contact = st.text_input("Phone Number*"); visit_date = st.date_input("Date", datetime.date.today(), format="DD-MM-YYYY")
        st.markdown("---"); c3, c4 = st.columns(2)
        with c3: st.subheader("Medical History"); hist = create_checkbox_grid(MED_HISTORY_OPTIONS, 2)
        with c4: st.subheader("Treatments Done"); treat = create_checkbox_grid(list(TREATMENT_PRICES.keys()), 2)
        st.markdown("---"); teeth = render_tooth_diagram(); st.markdown("---"); c5, c6 = st.columns([2,1])
        with c5: notes = st.text_area("Notes")
        with c6: 
            schedule_next = st.checkbox("Schedule Next Visit?", value=True)
            if schedule_next: next_app_date = st.date_input("Next Visit Date", datetime.date.today() + datetime.timedelta(days=7), format="DD-MM-YYYY"); next_app_str = next_app_date.strftime("%d-%m-%Y")
            else: next_app_str = "Not Required"
        if st.form_submit_button("✅ Save Patient Record"):
            if name and contact:
                new_id = len(df) + 101
                new_data = pd.DataFrame([{
                    "Patient ID": new_id, "Name": name, "Age": age, "Gender": gender, "Contact": contact,
                    "Last Visit": visit_date.strftime("%d-%m-%Y"), "Next Appointment": next_app_str,
                    "Treatment Notes": f"[{visit_date.strftime('%d-%m-%Y')}]\n{notes}", 
                    "Medical History": hist, "Treatments Done": treat, "Affected Teeth": teeth, "Pending Amount": 0
                }])
                df = pd.concat([df, new_data], ignore_index=True)
                save_data(df, "Patients")
                st.success("Patient Saved Successfully!")
            else: st.error("Name & Phone Required")

elif choice == "💊  Actions (Rx & Bill)":
    st.header("📝 Visit Record & Gallery")
    names_sorted = sorted(df["Name"].tolist()) if not df.empty else []
    patient = st.selectbox("Select Patient (Search Name)", [""] + names_sorted)
    
    if patient and not df.empty:
        p_data = df[df["Name"] == patient].iloc[0]
        
        # --- CARESTREAM RVG BRIDGE ---
        st.markdown("---")
        st.markdown("### 🦷 Carestream RVG Sync")
        col_cs1, col_cs2 = st.columns([3, 1])
        with col_cs1:
            cs_path_input = st.text_input("Carestream Export Folder Path:", value=CARESTREAM_EXPORT_FOLDER)
        with col_cs2:
            st.write("") 
            st.write("")
            if st.button("📥 Pull Latest X-Ray"):
                if os.path.exists(cs_path_input):
                    valid_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')
                    files = [os.path.join(cs_path_input, f) for f in os.listdir(cs_path_input) if os.path.isfile(os.path.join(cs_path_input, f)) and f.lower().endswith(valid_exts)]
                    
                    if files:
                        latest_file = max(files, key=os.path.getmtime)
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        new_filename = f"{patient}_RVG_{timestamp}.jpg"
                        dest_path = os.path.join(GALLERY_FOLDER, new_filename)
                        try:
                            Image.open(latest_file).convert('RGB').save(dest_path)
                            imported_folder = os.path.join(cs_path_input, "Imported_to_App")
                            if not os.path.exists(imported_folder):
                                os.makedirs(imported_folder)
                            shutil.move(latest_file, os.path.join(imported_folder, os.path.basename(latest_file)))
                            
                            st.success(f"✅ Successfully pulled X-Ray and archived original!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error reading or moving image: {e}")
                    else:
                        st.warning(f"No NEW images found in {cs_path_input}. Please save an image from Carestream into this folder first.")
                else:
                    st.error(f"Folder '{cs_path_input}' not found. Please create this folder on your computer first.")
        # ----------------------------------------------------------------------
        
        with st.expander("📸 Patient Gallery (Manual Upload & View X-Rays/Photos)", expanded=False):
            uploaded_files = st.file_uploader("Upload Local Images Manually", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
            if uploaded_files:
                for uploaded_file in uploaded_files:
                    try:
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        safe_name = f"{patient}_{timestamp}.jpg"
                        save_path = os.path.join(GALLERY_FOLDER, safe_name)
                        img = Image.open(uploaded_file)
                        img.save(save_path)
                        st.success(f"Saved: {safe_name}")
                        time.sleep(1)
                        st.rerun()
                    except: pass
            
            gallery_images = [f for f in os.listdir(GALLERY_FOLDER) if patient in f]
            if gallery_images:
                cols = st.columns(3)
                for idx, img_file in enumerate(gallery_images):
                    with cols[idx % 3]: 
                        img_path = os.path.join(GALLERY_FOLDER, img_file)
                        st.image(img_path, use_container_width=True)
                        if st.button("🗑️ Delete", key=f"del_img_{idx}"):
                            try:
                                os.remove(img_path)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Could not delete: {e}")

        st.markdown("---")
        st.markdown(f"### 📜 Clinical Chart: **{patient}**")
        med_history = p_data.get('Medical History', '')
        if med_history:
            st.markdown(f"<div style='background-color:#ffe6e6; padding:15px; border-left:5px solid red; border-radius:5px; margin-bottom:15px;'><b style='color:#cc0000;'>🚨 MEDICAL ALERT:</b> <span style='color:#333;'>{med_history}</span></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='background-color:#e6ffe6; padding:15px; border-left:5px solid green; border-radius:5px; margin-bottom:15px;'><b style='color:#006600;'>✅ MEDICAL HISTORY:</b> <span style='color:#333;'>No known conditions reported.</span></div>", unsafe_allow_html=True)
            
        st.markdown("#### 📅 Visit Timeline")
        notes_raw = str(p_data.get("Treatment Notes", ""))
        if notes_raw.strip():
            st.markdown(f"<div style='background-color:#f8f9fa; padding:20px; border-radius:10px; border: 1px solid #ddd; white-space: pre-wrap; font-size:16px; line-height:1.6; color:#333; box-shadow: inset 0 1px 3px rgba(0,0,0,0.05);'>{notes_raw}</div>", unsafe_allow_html=True)
        else:
            st.caption("No previous visit records found for this patient.")
        
        st.markdown("---"); st.markdown("### 1. New Visit Entry (Rx)")
        col_diag, col_adv = st.columns(2)
        with col_diag: selected_diag = st.multiselect("Diagnosis / Findings:", COMMON_DIAGNOSES)
        with col_adv: selected_advice_treat = st.multiselect("Advised Treatment:", COMMON_ADVICED_TREATMENTS)
        
        col_med, col_inst = st.columns(2)
        final_meds = []
        with col_med: 
            meds_selected = st.multiselect("Select Medicines (Then Edit Dosage Below):", COMMON_MEDICINES)
            for m in meds_selected:
                final_meds.append(st.text_input(f"Edit: {m.split(' (')[0]}", value=m, key=f"dose_{m}"))
        with col_inst: inst = st.multiselect("Instructions:", COMMON_INSTRUCTIONS)

        # --- AUTO-DEDUCT INVENTORY DISPENSER ---
        st.markdown("#### 📦 Dispense from Inventory")
        st.caption("Select products you are giving to the patient. They will be automatically deducted from your Sustock inventory.")
        dispensed_items = []
        if inventory_df is not None and not inventory_df.empty:
            in_stock_items = inventory_df[inventory_df["Quantity"] > 0]["Item Name"].tolist()
            if in_stock_items:
                dispensed_items = st.multiselect("Select products to dispense (auto-deducts 1 unit):", in_stock_items)
            else:
                st.warning("⚠️ All inventory items are currently out of stock.")
        # ----------------------------------------

        col_note, col_next_date = st.columns([2, 1])
        with col_note: custom_notes = st.text_area("Custom Notes (Rx)", height=60)
        with col_next_date: 
            if st.checkbox("Schedule Next Visit?", value=True): 
                final_next_visit_str = st.date_input("Date:", value=datetime.date.today() + datetime.timedelta(days=7), format="DD-MM-YYYY").strftime("%d-%m-%Y")
            else: final_next_visit_str = "Not Required"
        
        st.markdown("---"); st.markdown("### 2. Invoice Details")
        current_pending = float(p_data.get("Pending Amount", 0))
        if current_pending > 0: st.markdown(f'<div class="urgent-alert">⚠️ Patient has pending dues: ₹ {current_pending}</div><br>', unsafe_allow_html=True)
        
        valid_auto_select = [t for t in selected_advice_treat if t in TREATMENT_PRICES]
        sel_treats = st.multiselect("Treatments Performed:", options=list(TREATMENT_PRICES.keys()), default=valid_auto_select)
        
        invoice_lines = []
        subtotal = 0
        loyalty_discount = 0

        if sel_treats:
            st.markdown("#### Itemize Treatments")
            for i, t in enumerate(sel_treats):
                c_item1, c_item2, c_item3 = st.columns([3, 1, 1])
                with c_item1: desc = st.text_input(f"Details {i+1}", value=t, key=f"desc_{t}")
                with c_item2: qty = st.number_input("Qty", min_value=1, value=1, key=f"qty_{t}")
                with c_item3: u_price = st.number_input("Price (₹)", value=TREATMENT_PRICES[t], step=100, key=f"price_{t}")
                
                row_total = u_price * qty
                subtotal += row_total
                invoice_lines.append((f"{desc} (x{qty})" if qty > 1 else desc, row_total))
            
            st.markdown("---"); st.markdown("#### Loyalty & Discounts")
            loyalty_discount = st.number_input("Discount Amount (₹)", min_value=0, value=0, step=50)

            bill_total = max(0, subtotal - loyalty_discount)
            st.markdown(f"### Grand Total: ₹ {bill_total}")
            
            c_pay1, c_pay2 = st.columns(2)
            with c_pay1: 
                amount_paid = st.number_input("Amount Paid Today (₹)", min_value=0, value=int(bill_total))
            
            final_balance = (bill_total + current_pending) - amount_paid
            with c_pay2:
                if final_balance > 0: st.warning(f"Remaining Balance: ₹ {final_balance}")
                elif final_balance < 0: st.success(f"Change to Return: ₹ {abs(final_balance)}")
                else: st.success("Full Payment Received ✅")
        else: 
            amount_paid = 0; final_balance = current_pending; bill_total = 0
        
        st.markdown("---")
        
        st.markdown("#### 📎 Attachments")
        gallery_images = [f for f in os.listdir(GALLERY_FOLDER) if patient in f]
        selected_rx_images = []
        if gallery_images:
            selected_rx_images = st.multiselect("Select X-Rays/Photos to print on Prescription:", gallery_images, format_func=lambda x: " ".join(x.split('_')[1:]).replace('.jpg', ''))
        else:
            st.caption("No images found in gallery for this patient.")
        st.write("")
        
        wa_invoice_msg = f"Hello {patient}, your dental visit is complete. Total: {bill_total}. Paid: {amount_paid}. Balance: {final_balance}. - Sudantam Clinic"
        wa_invoice_link = generate_wa_link(p_data["Contact"], wa_invoice_msg)
        st.markdown(f'''<a href="{wa_invoice_link}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; width:100%; border-radius:5px; font-weight:bold;">📲 Open WhatsApp Web (Send Bill)</button></a>''', unsafe_allow_html=True)

        if st.button("🖨️ Generate PDF & Save"):
            today_date_str = datetime.date.today().strftime("%d-%m-%Y")
            
            new_entry = f"\n\n--- VISIT: {today_date_str} ---\n"
            if selected_diag: new_entry += f"• Diagnosis: {', '.join(selected_diag)}\n"
            if sel_treats: new_entry += f"• Tx Done: {', '.join([x[0] for x in invoice_lines])}\n"
            if final_meds: new_entry += f"• Meds: {', '.join(final_meds)}\n"
            if dispensed_items: new_entry += f"• Dispensed: {', '.join(dispensed_items)}\n"
            if custom_notes: new_entry += f"• Note: {custom_notes}"
            
            df.loc[df["Name"] == patient, "Treatment Notes"] += new_entry
            df.loc[df["Name"] == patient, "Next Appointment"] = final_next_visit_str
            if sel_treats or amount_paid > 0: df.loc[df["Name"] == patient, "Pending Amount"] = final_balance
            save_data(df, "Patients")
            
            if sel_treats:
                new_bill = pd.DataFrame([{ "Date": today_date_str, "Patient Name": patient, "Treatments": ", ".join([x[0] for x in invoice_lines]), "Total Amount": bill_total, "Paid Amount": amount_paid, "Balance Due": final_balance }])
                billing_df = pd.concat([billing_df, new_bill], ignore_index=True)
                save_billing(billing_df)
                
            # AUTO DEDUCT INVENTORY HERE
            if dispensed_items and inventory_df is not None:
                for d_item in dispensed_items:
                    idx_inv = inventory_df.index[inventory_df["Item Name"] == d_item].tolist()[0]
                    inventory_df.at[idx_inv, "Quantity"] = max(0, int(inventory_df.at[idx_inv, "Quantity"]) - 1)
                save_inventory(inventory_df)
            
            pdf_filename = f"{patient}_{int(p_data['Age'])}_{today_date_str}.pdf"
            pdf_path = os.path.join(PRESCRIPTION_FOLDER, pdf_filename)
            pdf = PDF(); pdf.add_page()
            
            pdf.set_fill_color(245, 245, 245)
            pdf.rect(10, pdf.get_y(), 190, 25, 'F')
            pdf.set_font("Helvetica", 'B', 12)
            pdf.cell(100, 8, f"Patient Name: {patient}", 0, 0); pdf.cell(90, 8, f"Date: {today_date_str}", 0, 1, 'R')
            pdf.set_font("Helvetica", '', 11)
            pdf.cell(100, 8, f"Age/Gender: {p_data['Age']} / {p_data['Gender']}", 0, 0); pdf.cell(90, 8, f"Contact: {p_data['Contact']}", 0, 1, 'R')
            pdf.ln(10)

            if selected_diag:
                pdf.set_font("Helvetica", 'B', 12); pdf.set_text_color(44, 122, 111)
                pdf.cell(0, 8, "Diagnosis / Clinical Findings", 0, 1); pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", '', 11)
                for d in selected_diag: pdf.cell(5); pdf.cell(0, 6, f"- {d}", 0, 1)
                pdf.ln(5)

            if final_meds or dispensed_items:
                pdf.set_font("Helvetica", 'B', 12); pdf.set_text_color(44, 122, 111)
                pdf.cell(0, 8, "Rx (Medicines & Products Advised)", 0, 1); pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", '', 11)
                idx = 1
                for m in final_meds:
                    pdf.cell(5); pdf.cell(0, 7, f"{idx}. {m}", 0, 1); idx += 1
                for d_item in dispensed_items:
                    pdf.cell(5); pdf.cell(0, 7, f"{idx}. Dispensed: {d_item}", 0, 1); idx += 1
                pdf.ln(5)

            if sel_treats:
                pdf.ln(5); pdf.set_font("Helvetica", 'B', 14); pdf.set_fill_color(44, 122, 111); pdf.set_text_color(255, 255, 255)
                pdf.cell(140, 10, "  Description", 1, 0, 'L', True); pdf.cell(50, 10, "Amount (INR)  ", 1, 1, 'R', True)
                pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", '', 11)
                for t, p in invoice_lines: pdf.cell(140, 10, f"  {t}", 1, 0); pdf.cell(50, 10, f"{p}  ", 1, 1, 'R')
                
                if loyalty_discount > 0:
                    pdf.set_font("Helvetica", 'B', 11); pdf.set_text_color(0, 150, 0)
                    pdf.cell(140, 10, "  Special Loyalty Discount", 1, 0); pdf.cell(50, 10, f"- {loyalty_discount}  ", 1, 1, 'R')
                    pdf.set_text_color(0, 0, 0)

                pdf.set_font("Helvetica", 'B', 12)
                pdf.cell(140, 10, "  Grand Total", 1, 0); pdf.cell(50, 10, f"{bill_total}  ", 1, 1, 'R')
                pdf.set_font("Helvetica", 'B', 11)
                pdf.cell(140, 10, "  Paid Amount", 1, 0); pdf.cell(50, 10, f"{amount_paid}  ", 1, 1, 'R')
            
            pdf.add_qr_section()
            
            if selected_rx_images:
                for img_file in selected_rx_images:
                    img_path = os.path.join(GALLERY_FOLDER, img_file)
                    try:
                        with Image.open(img_path) as img:
                            w, h = img.size
                            ratio = w / h
                        pdf.add_page()
                        pdf.set_font("Helvetica", 'B', 14)
                        pdf.set_text_color(44, 122, 111)
                        pdf.cell(0, 10, f"Clinical Radiograph / Image ({today_date_str})", 0, 1, 'C')
                        pdf.ln(5)
                        
                        max_w = 170
                        max_h = 220
                        target_w = max_w
                        target_h = target_w / ratio
                        
                        if target_h > max_h:
                            target_h = max_h
                            target_w = target_h * ratio
                        
                        x_pos = (210 - target_w) / 2
                        pdf.image(img_path, x=x_pos, y=pdf.get_y(), w=target_w, h=target_h)
                    except: pass

            pdf.output(pdf_path)
            with open(pdf_path, "rb") as f: st.download_button("⬇️ Download Prescription", f, file_name=pdf_filename)
            st.success(f"Saved: {pdf_filename}")
            time.sleep(1)
            st.rerun()

elif choice == "📦  Inventory (Sustock)":
    st.header("📦 Sustock Inventory Management")
    
    with st.expander("➕ Add New Product to Inventory", expanded=False):
        with st.form("add_inv_form", clear_on_submit=True):
            col_inv1, col_inv2 = st.columns(2)
            i_name = col_inv1.text_input("Product Name (e.g. Freshchlor Mouthwash)")
            i_qty = col_inv2.number_input("Starting Quantity", min_value=0, value=1)
            i_desc = st.text_area("Details (Price, Expiry Date, Supplier Notes)")
            i_img = st.file_uploader("Upload Product Image (Optional)", type=["jpg", "png", "jpeg"])
            
            if st.form_submit_button("✅ Save Product"):
                if i_name:
                    img_filename = ""
                    if i_img:
                        img_filename = f"inv_{int(time.time())}.jpg"
                        Image.open(i_img).convert('RGB').save(os.path.join(INVENTORY_FOLDER, img_filename))
                    
                    new_item = pd.DataFrame([{"Item Name": i_name, "Description": i_desc, "Quantity": i_qty, "Image_File": img_filename}])
                    inventory_df = pd.concat([inventory_df, new_item], ignore_index=True)
                    save_inventory(inventory_df)
                    st.success(f"Added {i_name} to Inventory!")
                    st.rerun()
                else:
                    st.error("Product Name is required.")

    st.markdown("### Current Stock Levels")
    if inventory_df is not None and not inventory_df.empty:
        for idx, row in inventory_df.iterrows():
            with st.container():
                st.markdown('<div class="inv-card">', unsafe_allow_html=True)
                col1, col2, col3 = st.columns([1, 3, 2])
                with col1:
                    if row["Image_File"] and os.path.exists(os.path.join(INVENTORY_FOLDER, str(row["Image_File"]))):
                        st.image(os.path.join(INVENTORY_FOLDER, str(row["Image_File"])), use_container_width=True)
                    else:
                        st.info("No Image")
                with col2:
                    st.markdown(f"#### {row['Item Name']}")
                    st.caption(str(row['Description']))
                with col3:
                    st.markdown(f"<h3 style='color:{PRIMARY_COLOR};'>Qty: {row['Quantity']}</h3>", unsafe_allow_html=True)
                    
                    c_btn1, c_btn2, c_btn3 = st.columns(3)
                    if c_btn1.button("➖", key=f"minus_{idx}"):
                        inventory_df.at[idx, "Quantity"] = max(0, int(row["Quantity"]) - 1)
                        save_inventory(inventory_df)
                        st.rerun()
                    if c_btn2.button("➕", key=f"plus_{idx}"):
                        inventory_df.at[idx, "Quantity"] = int(row["Quantity"]) + 1
                        save_inventory(inventory_df)
                        st.rerun()
                    if c_btn3.button("🗑️", key=f"del_inv_{idx}"):
                        inventory_df = inventory_df.drop(idx)
                        save_inventory(inventory_df)
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Inventory is empty. Click 'Add New Product' to start building your stock.")

elif choice == "💸  Expenses & Profit":
    st.header("💸 Daily Expenses & Profit")
    total_income = billing_df["Paid Amount"].sum() if billing_df is not None and not billing_df.empty else 0
    total_expense = expenses_df["Amount"].sum() if expenses_df is not None and not expenses_df.empty else 0
    profit = total_income - total_expense
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Income", f"₹ {total_income:,.0f}"); col2.metric("Total Expenses", f"₹ {total_expense:,.0f}"); col3.metric("Net Profit", f"₹ {profit:,.0f}", delta_color="normal")
    st.divider()
    st.subheader("➕ Add New Expense")
    with st.form("expense_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        ex_date = c1.date_input("Date", datetime.date.today())
        ex_cat = c2.selectbox("Category", EXPENSE_CATEGORIES)
        c3, c4 = st.columns(2)
        ex_amt = c3.number_input("Amount (₹)", min_value=0, step=10)
        ex_pay = c4.selectbox("Payment Mode", ["Cash", "UPI", "Bank Transfer"])
        ex_desc = st.text_input("Description (e.g., Composite Kit, Electricity Bill)")
        if st.form_submit_button("Log Expense"):
            new_ex = pd.DataFrame([{"Date": ex_date.strftime("%d-%m-%Y"), "Category": ex_cat, "Description": ex_desc, "Amount": ex_amt, "Payment Mode": ex_pay}])
            expenses_df = pd.concat([expenses_df, new_ex], ignore_index=True)
            save_expenses(expenses_df); st.success("Expense Added!"); st.rerun()
    st.divider(); st.subheader("📜 Expense Log")
    if expenses_df is not None and not expenses_df.empty: st.dataframe(expenses_df, use_container_width=True)
    else: st.info("No expenses logged yet.")

elif choice == "🧪  Lab Tracking":
    st.header("🧪 Lab Work Tracker")
    with st.expander("➕ Add New Lab Order", expanded=False):
        with st.form("lab_form", clear_on_submit=True):
            names_sorted = sorted(df["Name"].tolist()) if not df.empty else []
            l_pt = st.selectbox("Patient", [""] + names_sorted)
            c1, c2 = st.columns(2)
            l_lab = c1.text_input("Lab Name")
            l_item = c2.text_input("Item (e.g. PFM Crown)")
            c3, c4 = st.columns(2)
            l_teeth = c3.text_input("Teeth Numbers")
            l_cost = c4.number_input("Lab Cost (₹)", min_value=0, step=100)
            l_due = st.date_input("Due Date", datetime.date.today() + datetime.timedelta(days=4))
            if st.form_submit_button("Save Order"):
                new_lab = pd.DataFrame([{"Order Date": datetime.date.today().strftime("%d-%m-%Y"), "Patient Name": l_pt, "Lab Name": l_lab, "Item Type": l_item, "Teeth": l_teeth, "Due Date": l_due.strftime("%d-%m-%Y"), "Status": "Sent", "Cost": l_cost}])
                lab_df = pd.concat([lab_df, new_lab], ignore_index=True)
                save_lab_data(lab_df); st.success("Order Saved!"); st.rerun()
    st.subheader("📦 Pending Orders")
    if lab_df is not None and not lab_df.empty:
        pending = lab_df[lab_df["Status"] == "Sent"]
        for idx, row in pending.iterrows():
            with st.container():
                c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                c1.write(f"**{row['Patient Name']}**"); c1.caption(row['Item Type'])
                c2.write(row['Lab Name']); c2.caption(f"Due: {row['Due Date']}")
                c3.write(f"Cost: ₹{row['Cost']}")
                if c4.button("✅ Recv", key=f"rec_{idx}"):
                    lab_df.at[idx, "Status"] = "Received"; save_lab_data(lab_df); st.rerun()

elif choice == "🧠  AI Assistant":
    st.header("🧠 Gemini AI Clinic Assistant")
    
    if not GEMINI_AVAILABLE:
        st.error("⚠️ **Google AI Library Missing!**")
        st.info("To use the AI, open your **Command Prompt (cmd)** and run:\n\n`pip install google-generativeai`\n\nOnce installed, refresh the app.")
    else:
        api_key = "AIzaSyDOU5OvEx_x_UrEnh1MyAZX6eRxia6di14"
        
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            st.success("✅ AI Connected! I am ready to assist you, Dr. Sugam.")
            
            t1, t2, t3 = st.tabs(["🔔 Smart Reminders", "📝 Auto-Clinical Notes", "📸 X-Ray Analysis"])
            
            with t1:
                st.subheader("Tomorrow's Appointments")
                if not df.empty:
                    tmrw = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%d-%m-%Y")
                    apps = df[df["Next Appointment"].astype(str) == tmrw]
                    if not apps.empty:
                        for _, r in apps.iterrows():
                            st.write(f"**{r['Name']}** (Contact: {r['Contact']})")
                            if st.button(f"Generate Reminder for {r['Name']}"):
                                with st.spinner("Writing message..."):
                                    prompt = f"Write a polite, friendly WhatsApp reminder for dental patient {r['Name']} for their appointment tomorrow at Sudantam Dental Clinic with Dr. Sugam Jangid. Keep it under 3 sentences."
                                    msg = model.generate_content(prompt).text
                                    st.write(msg)
                                    st.markdown(f'''<a href="{generate_wa_link(r["Contact"], msg)}" target="_blank"><button style="background-color:#25D366; color:white; padding:8px; border-radius:5px; border:none;">📲 Send to {r['Name']}</button></a>''', unsafe_allow_html=True)
                            st.divider()
                    else: st.success("No appointments scheduled for tomorrow.")
            
            with t2:
                st.subheader("Shorthand to Professional Notes")
                
                c_n1, c_n2 = st.columns(2)
                names_sorted = sorted(df["Name"].tolist()) if not df.empty else []
                note_pt = c_n1.selectbox("Select Patient for Note", [""] + names_sorted, key="ai_pt")
                note_dt = c_n2.date_input("Date", datetime.date.today(), format="DD-MM-YYYY", key="ai_dt")
                
                proc_stage = st.selectbox("Procedure Category / Stage", [
                    "General / Consultation",
                    "RCT - Access Opening & Extirpation",
                    "RCT - Biomechanical Preparation (BMP) & Medicament",
                    "RCT - Obturation",
                    "Extraction",
                    "Restoration / Filling",
                    "Prostho - Crown Prep & Impression",
                    "Prostho - Crown Cementation",
                    "Perio - Scaling & Root Planing",
                    "Ortho - Wire Change / Adjustment"
                ])
                
                short = st.text_area("Type shorthand (e.g., '31 41 rct completed pain med given')")
                
                if st.button("✨ Expand Note"):
                    if short:
                        with st.spinner("Expanding into professional medico-legal note..."):
                            prompt = f"""
                            You are an expert dentist. Expand this shorthand into a professional, medico-legal clinical note for patient records.
                            
                            Patient Name: {note_pt if note_pt else 'Patient'}
                            Date: {note_dt.strftime('%d-%m-%Y')}
                            Procedure Category: {proc_stage}
                            Shorthand Notes: '{short}'
                            
                            CRITICAL INSTRUCTION: You MUST interpret all tooth numbers using the FDI World Dental Federation Two-Digit notation (e.g., 11 = Maxillary Right Central Incisor, 31 = Mandibular Left Central Incisor, 46 = Mandibular Right First Molar). DO NOT use the Universal numbering system.
                            
                            Do NOT include any placeholder brackets (like [Insert Time] or [Dentist Name]). Write the final, complete chart entry ready for pasting.
                            """
                            st.session_state["generated_note"] = model.generate_content(prompt).text
                    else:
                        st.warning("Please type some shorthand notes first.")
                        
                if "generated_note" in st.session_state:
                    final_note = st.text_area("Final Clinical Note (Edit if needed):", st.session_state["generated_note"], height=250)
                    if note_pt and st.button("💾 Save to Patient Record"):
                        idx = df.index[df["Name"] == note_pt].tolist()[0]
                        df.at[idx, "Treatment Notes"] += f"\n\n--- AI GENERATED NOTE: {note_dt.strftime('%d-%m-%Y')} ---\n{final_note}"
                        save_data(df, "Patients")
                        st.success(f"✅ Note safely added to {note_pt}'s records!")
                        del st.session_state["generated_note"]
                        st.rerun()
                    
            with t3:
                st.subheader("AI Second Opinion")
                img_file = st.file_uploader("Upload X-Ray/Photo for Analysis", type=["jpg", "png", "jpeg"])
                if img_file and st.button("Analyze Image"):
                    with st.spinner("Analyzing clinical data..."):
                        img = Image.open(img_file)
                        st.image(img, width=300)
                        prompt = ["You are an expert oral radiologist and dentist. Describe the clinical findings, bone levels, caries, or anomalies in this dental image.", img]
                        st.write(model.generate_content(prompt).text)
        except Exception as e:
            st.error(f"Error connecting to AI: {e}")

elif choice == "🧮  Pediatric Dosage":
    st.header("🧮 Pediatric Dosage Calculator")
    weight = st.number_input("Child's Weight (kg)", min_value=1.0, max_value=50.0, step=0.5, value=10.0)
    if weight:
        amox = weight * 10; metro = weight * 10; ibu = weight * 10
        st.markdown(f"**Amoxicillin:** {amox}mg per dose. **Metrogyl:** {metro}mg per dose. **Ibuprofen:** {ibu}mg per dose.")

elif choice == "✍️  Consent Forms":
    st.header("✍️ Consent Form Generator")
    cf_name = st.text_input("Patient Name")
    proc = st.selectbox("Procedure", list(CONSENT_TEMPLATES.keys()))
    text = st.text_area("Text", value=CONSENT_TEMPLATES[proc], height=200)
    if st.button("Generate"):
        pdf = PDF(); pdf.add_page(); pdf.set_font("Helvetica", '', 12); pdf.multi_cell(0, 10, text)
        pdf.output(os.path.join(CONSENT_FOLDER, "consent.pdf")); st.success("Generated!")

elif choice == "📢  Marketing / WhatsApp":
    st.header("📢 Clinic Marketing")
    
    t1, t2, t3 = st.tabs(["📲 Message/Recall", "📂 Data Export", "📸 Branded Content Maker"])
    
    with t1:
        st.subheader("Direct & Recall Messaging")
        if not df.empty:
            names_sorted = sorted(df["Name"].tolist())
            target_pt = st.selectbox("Select Patient to Message", [""] + names_sorted)
            if target_pt:
                t_data = df[df["Name"] == target_pt].iloc[0]
                st.write(f"Messaging: **{target_pt}** ({t_data['Contact']})")
                wa_text = st.text_area("Message:", value="Hello, this is a reminder from Sudantam Dental Clinic...")
                if wa_text:
                    direct_link = generate_wa_link(t_data["Contact"], wa_text)
                    st.markdown(f'''<a href="{direct_link}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; width:100%; font-weight:bold;">📨 Open WhatsApp Web</button></a>''', unsafe_allow_html=True)
        
        st.divider()
        st.subheader("🔄 Smart Recall System (6 Months+)")
        if not df.empty and "Last Visit" in df.columns:
            today = datetime.date.today()
            recall_list = []
            for index, row in df.iterrows():
                try:
                    last_visit = pd.to_datetime(str(row["Last Visit"]), format="%d-%m-%Y").date()
                    if (today - last_visit).days > 180: recall_list.append(row)
                except: pass
            if recall_list: st.dataframe(pd.DataFrame(recall_list)[["Name", "Contact", "Last Visit"]], hide_index=True)
            else: st.success("No old patients found to recall.")

    with t2:
        st.subheader("Bulk Data Export")
        filter_option = st.selectbox("Select Audience:", ["All Patients", "Defaulters", "Patients with Scheduled Next Visit"])
        filtered_df = df.copy()
        if not df.empty:
            if filter_option == "Defaulters": filtered_df = df[df["Pending Amount"] > 0]
            elif filter_option == "Patients with Scheduled Next Visit": filtered_df = df[df["Next Appointment"] != "Not Required"]
            st.write(f"Found **{len(filtered_df)}** patients.")
            if not filtered_df.empty:
                vcf_data = generate_vcf(filtered_df)
                st.download_button(label="📂 Download VCF", data=vcf_data, file_name="Sudantam_Patients.vcf")

    with t3:
        st.subheader("📸 Clinical Media Brander")
        
        media_type = st.radio("What are you uploading?", ["📸 Photos (JPG/PNG)", "🎥 Videos (MP4/MOV)"])
        
        if media_type == "📸 Photos (JPG/PNG)":
            post_type = st.radio("Format:", ["Side-by-Side Image", "Swipeable Images (Carousel)"])
            auto_enhance = st.checkbox("✨ Smart AI Filter (Sharpens 'Before', Smooths 'After')") 
            
            c1, c2 = st.columns(2)
            with c1:
                img_before = st.file_uploader("Upload 'Before' Photo", type=["jpg", "png", "jpeg"])
                rot_b = st.selectbox("Rotate 'Before'", ["None", "90° Right", "180°", "90° Left"], key="rb_p")
            with c2:
                img_after = st.file_uploader("Upload 'After' Photo", type=["jpg", "png", "jpeg"])
                rot_a = st.selectbox("Rotate 'After'", ["None", "90° Right", "180°", "90° Left"], key="ra_p")
            
            if img_before and img_after and st.button("Generate Branded Content"):
                try:
                    i1 = Image.open(img_before).convert("RGB")
                    i2 = Image.open(img_after).convert("RGB")
                    
                    i1 = rotate_image(i1, rot_b)
                    i2 = rotate_image(i2, rot_a)
                    
                    if auto_enhance: 
                        i1 = enhance_before_image(i1)
                        i2 = enhance_after_image(i2)
                    
                    base_height = 800
                    w1 = int(i1.width * (base_height / i1.height))
                    w2 = int(i2.width * (base_height / i2.height))
                    i1 = i1.resize((w1, base_height), Image.Resampling.LANCZOS)
                    i2 = i2.resize((w2, base_height), Image.Resampling.LANCZOS)

                    border = 20; header_h = 60; footer_h = 80
                    try: 
                        font = ImageFont.truetype("arial.ttf", 35)
                        font_footer = ImageFont.truetype("arial.ttf", 45)
                    except: 
                        font = ImageFont.load_default(); font_footer = ImageFont.load_default()
                    
                    ft_logo = None; logo_w = 0
                    if os.path.exists("logo.jpeg"):
                        try:
                            temp_logo = Image.open("logo.jpeg").convert("RGBA")
                            logo_h = footer_h - 20
                            logo_w = int(temp_logo.width * (logo_h / temp_logo.height))
                            ft_logo = temp_logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
                        except: pass
                    
                    phone_text = "  |  +91 8078656835"
                    try:
                        text_w = ImageDraw.Draw(Image.new('RGB', (1,1))).textbbox((0,0), phone_text, font=font_footer)[2]
                        text_h = ImageDraw.Draw(Image.new('RGB', (1,1))).textbbox((0,0), phone_text, font=font_footer)[3]
                    except: text_w = 400; text_h = 20
                        
                    total_content_w = logo_w + text_w

                    if post_type == "Side-by-Side Image":
                        total_width = w1 + w2 + (border * 3)
                        total_height = base_height + header_h + footer_h + border
                        combined = Image.new('RGB', (total_width, total_height), 'white')
                        draw = ImageDraw.Draw(combined)
                        
                        draw.text((border, 10), "Pre-Treatment (Before)", fill="black", font=font)
                        draw.text((w1 + border*2, 10), "Post-Treatment (After)", fill="black", font=font)
                        
                        combined.paste(i1, (border, header_h))
                        combined.paste(i2, (w1 + border*2, header_h))
                        
                        footer_y = total_height - footer_h
                        draw.rectangle([0, footer_y, total_width, total_height], fill="#2C7A6F")
                        
                        start_x = total_width - total_content_w - 30 
                        if ft_logo: combined.paste(ft_logo, (int(start_x), int(footer_y + 10)), ft_logo if ft_logo.mode == 'RGBA' else None)
                            
                        text_y = footer_y + (footer_h - text_h)/2 - 10
                        draw.text((start_x + logo_w, text_y), phone_text, fill="white", font=font_footer)
                        
                        st.image(combined, caption="Final Branded Image", use_container_width=True)
                        combined.save("marketing_post.jpg")
                        with open("marketing_post.jpg", "rb") as f: 
                            st.download_button("⬇️ Download High-Res File", f, file_name="Sudantam_Transformation.jpg", mime="image/jpeg")

                    else: 
                        def create_single_slide(img, img_w, title_text):
                            t_width = img_w + (border * 2)
                            t_height = base_height + header_h + footer_h + border
                            canvas = Image.new('RGB', (t_width, t_height), 'white')
                            draw_slide = ImageDraw.Draw(canvas)
                            
                            try: title_w = draw_slide.textbbox((0,0), title_text, font=font)[2]
                            except: title_w = 200
                            title_x = (t_width - title_w) / 2
                            draw_slide.text((title_x, 10), title_text, fill="black", font=font)
                            
                            canvas.paste(img, (border, header_h))
                            f_y = t_height - footer_h
                            draw_slide.rectangle([0, f_y, t_width, t_height], fill="#2C7A6F")
                            
                            if t_width > (total_content_w + 60): s_x = t_width - total_content_w - 30
                            else:
                                s_x = (t_width - total_content_w) / 2
                                if s_x < 10: s_x = 10 
                                
                            if ft_logo: canvas.paste(ft_logo, (int(s_x), int(f_y + 10)), ft_logo if ft_logo.mode == 'RGBA' else None)
                                
                            t_y = f_y + (footer_h - text_h)/2 - 10
                            draw_slide.text((s_x + logo_w, t_y), phone_text, fill="white", font=font_footer)
                            return canvas

                        slide1 = create_single_slide(i1, w1, "Pre-Treatment (Before)")
                        slide2 = create_single_slide(i2, w2, "Post-Treatment (After)")

                        col_s1, col_s2 = st.columns(2)
                        with col_s1:
                            st.image(slide1, caption="Slide 1 (Before)", use_container_width=True)
                            slide1.save("slide1.jpg")
                            with open("slide1.jpg", "rb") as f: st.download_button("⬇️ Download Slide 1", f, file_name="Sudantam_IG_Slide1.jpg", mime="image/jpeg")
                        with col_s2:
                            st.image(slide2, caption="Slide 2 (After)", use_container_width=True)
                            slide2.save("slide2.jpg")
                            with open("slide2.jpg", "rb") as f: st.download_button("⬇️ Download Slide 2", f, file_name="Sudantam_IG_Slide2.jpg", mime="image/jpeg")
                except Exception as e: 
                    st.error(f"Error processing images: {e}")

        elif media_type == "🎥 Videos (MP4/MOV)":
            if not CV2_AVAILABLE:
                st.error("⚠️ **Video Rendering Engine Missing!**")
                st.info("To generate videos, open your **Command Prompt (cmd)** on Windows and run this exact command:\n\n`pip install opencv-python numpy`\n\nOnce installed, refresh the app and it will work instantly.")
            else:
                c1, c2 = st.columns(2)
                with c1:
                    vid_before = st.file_uploader("Upload 'Before' Video", type=["mp4", "mov"])
                    rot_b_v = st.selectbox("Rotate 'Before'", ["None", "90° Right", "180°", "90° Left"], key="rb_v")
                with c2:
                    vid_after = st.file_uploader("Upload 'After' Video", type=["mp4", "mov"])
                    rot_a_v = st.selectbox("Rotate 'After'", ["None", "90° Right", "180°", "90° Left"], key="ra_v")
                
                if vid_before and vid_after:
                    if st.button("🎬 Generate Branded Side-by-Side Video"):
                        with st.spinner("Processing video frames... This might take a minute..."):
                            try:
                                with open("temp_b.mp4", "wb") as f: f.write(vid_before.read())
                                with open("temp_a.mp4", "wb") as f: f.write(vid_after.read())
                                
                                cap1 = cv2.VideoCapture("temp_b.mp4")
                                cap2 = cv2.VideoCapture("temp_a.mp4")
                                fps = int(cap1.get(cv2.CAP_PROP_FPS))
                                if fps == 0: fps = 30
                                
                                ret1, f1 = cap1.read()
                                ret2, f2 = cap2.read()
                                
                                if not ret1 or not ret2:
                                    st.error("Could not read one of the videos.")
                                else:
                                    f1 = rotate_frame(f1, rot_b_v)
                                    f2 = rotate_frame(f2, rot_a_v)
                                    
                                    h1, w1_orig = f1.shape[:2]
                                    h2, w2_orig = f2.shape[:2]
                                    
                                    base_height = 800
                                    w1 = int(w1_orig * (base_height / h1))
                                    w2 = int(w2_orig * (base_height / h2))
                                    
                                    border = 20; header_h = 60; footer_h = 80
                                    total_width = w1 + w2 + (border * 3)
                                    total_height = base_height + header_h + footer_h + border
                                    
                                    bg_img = Image.new('RGB', (total_width, total_height), 'white')
                                    draw = ImageDraw.Draw(bg_img)
                                    
                                    try: 
                                        font = ImageFont.truetype("arial.ttf", 35)
                                        font_footer = ImageFont.truetype("arial.ttf", 45)
                                    except: 
                                        font = ImageFont.load_default(); font_footer = ImageFont.load_default()
                                        
                                    draw.text((border, 10), "Pre-Treatment (Before)", fill="black", font=font)
                                    draw.text((w1 + border*2, 10), "Post-Treatment (After)", fill="black", font=font)
                                    
                                    footer_y = total_height - footer_h
                                    draw.rectangle([0, footer_y, total_width, total_height], fill="#2C7A6F")
                                    
                                    ft_logo = None; logo_w = 0
                                    if os.path.exists("logo.jpeg"):
                                        try:
                                            temp_logo = Image.open("logo.jpeg").convert("RGBA")
                                            logo_h = footer_h - 20
                                            logo_w = int(temp_logo.width * (logo_h / temp_logo.height))
                                            ft_logo = temp_logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
                                        except: pass
                                    
                                    phone_text = "  |  +91 8078656835"
                                    try:
                                        text_w = ImageDraw.Draw(Image.new('RGB', (1,1))).textbbox((0,0), phone_text, font=font_footer)[2]
                                        text_h = ImageDraw.Draw(Image.new('RGB', (1,1))).textbbox((0,0), phone_text, font=font_footer)[3]
                                    except: text_w = 400; text_h = 20
                                        
                                    total_content_w = logo_w + text_w
                                    start_x = total_width - total_content_w - 30 
                                    if ft_logo: bg_img.paste(ft_logo, (int(start_x), int(footer_y + 10)), ft_logo if ft_logo.mode == 'RGBA' else None)
                                    text_y = footer_y + (footer_h - text_h)/2 - 10
                                    draw.text((start_x + logo_w, text_y), phone_text, fill="white", font=font_footer)
                                    
                                    bg_np = cv2.cvtColor(np.array(bg_img), cv2.COLOR_RGB2BGR)
                                    
                                    out = cv2.VideoWriter("branded_video_out.mp4", cv2.VideoWriter_fourcc(*'mp4v'), fps, (total_width, total_height))
                                    
                                    cap1.set(cv2.CAP_PROP_POS_FRAMES, 0)
                                    cap2.set(cv2.CAP_PROP_POS_FRAMES, 0)
                                    
                                    last_f1 = cv2.resize(f1, (w1, base_height))
                                    last_f2 = cv2.resize(f2, (w2, base_height))
                                    
                                    while True:
                                        r1, frame1 = cap1.read()
                                        r2, frame2 = cap2.read()
                                        
                                        if not r1 and not r2: break
                                        
                                        if r1: 
                                            frame1 = rotate_frame(frame1, rot_b_v)
                                            last_f1 = cv2.resize(frame1, (w1, base_height))
                                        if r2: 
                                            frame2 = rotate_frame(frame2, rot_a_v)
                                            last_f2 = cv2.resize(frame2, (w2, base_height))
                                            
                                        canvas = bg_np.copy()
                                        canvas[header_h:header_h+base_height, border:border+w1] = last_f1
                                        canvas[header_h:header_h+base_height, border*2+w1:border*2+w1+w2] = last_f2
                                        
                                        out.write(canvas)
                                        
                                    cap1.release()
                                    cap2.release()
                                    out.release()
                                    
                                    st.success("✅ Video Processed Successfully!")
                                    st.info("Note: Social media platforms natively mute side-by-side videos, so you can easily add trending music over this reel directly in the Instagram app!")
                                    with open("branded_video_out.mp4", "rb") as f:
                                        st.download_button("⬇️ Download Branded Video Reel", f, file_name="Sudantam_Video_Reel.mp4", mime="video/mp4")
                            except Exception as e:
                                st.error(f"Error generating video: {e}")

elif choice == "💰  Manage Defaulters":
    st.header("💰 Manage Pending Dues")
    if not df.empty:
        defaulters_df = df[df["Pending Amount"] > 0]
        st.dataframe(defaulters_df[["Name", "Contact", "Pending Amount"]], use_container_width=True)
        target_person = st.selectbox("Select Patient to Update", [""] + defaulters_df["Name"].tolist())
        if target_person:
            idx = df.index[df["Name"] == target_person].tolist()[0]
            current_due = df.at[idx, "Pending Amount"]
            st.info(f"Owes: ₹ {current_due}")
            if st.button("✅ Mark Paid (Clear 0)"):
                df.at[idx, "Pending Amount"] = 0; save_data(df, "Patients"); st.success("Cleared!"); st.rerun()

elif choice == "🔧  Manage Data":
    st.header("🔧 Manage Patient Data")
    if not df.empty:
        names_sorted = sorted(df["Name"].tolist())
        patient_to_edit = st.selectbox("Select Patient to Edit/Delete", [""] + names_sorted)
        if patient_to_edit:
            idx = df.index[df["Name"] == patient_to_edit].tolist()[0]
            p_data = df.iloc[idx]
            with st.form("edit_form"):
                st.subheader("✏️ Edit Details")
                c1, c2 = st.columns(2)
                new_name = c1.text_input("Name", value=p_data["Name"])
                new_contact = c2.text_input("Contact", value=str(p_data["Contact"]))
                st.write("---")
                try:
                    raw_date = str(p_data.get("Next Appointment", ""))
                    parsed = pd.to_datetime(raw_date, format="%d-%m-%Y", errors='coerce')
                    if pd.isna(parsed): default_date = datetime.date.today() + datetime.timedelta(days=7)
                    else: default_date = parsed.date()
                except: default_date = datetime.date.today() + datetime.timedelta(days=7)
                is_scheduled = (str(p_data.get("Next Appointment")) not in ["Not Required", "nan", "NaT"])
                schedule_edit = st.checkbox("Scheduled Next Visit?", value=is_scheduled)
                if schedule_edit: new_app_date = st.date_input("Next Visit", value=default_date, format="DD-MM-YYYY"); final_edit_app_str = new_app_date.strftime("%d-%m-%Y")
                else: final_edit_app_str = "Not Required"
                if st.form_submit_button("💾 Update Info"):
                    df.at[idx, "Name"] = new_name; df.at[idx, "Contact"] = new_contact; df.at[idx, "Next Appointment"] = final_edit_app_str
                    save_data(df, "Patients"); st.success("Updated!"); st.rerun()
            st.markdown("---")
            st.subheader("❌ Delete Record")
            st.warning(f"Are you sure you want to delete **{patient_to_edit}**? This cannot be undone.")
            col_del1, col_del2 = st.columns([1, 4])
            with col_del1:
                if st.button("🗑️ YES, DELETE", type="primary", use_container_width=True): df = df.drop(idx); save_data(df, "Patients"); st.success(f"Deleted {patient_to_edit}."); st.rerun()

elif choice == "🔍  Search Registry":
    st.header("🔍 Registry")
    q = st.text_input("Search Name")
    if not df.empty and q: 
        results = df[df["Name"].str.contains(q, case=False, na=False)]
        st.dataframe(results, use_container_width=True)
    elif not df.empty: 
        st.dataframe(df, use_container_width=True)
        results = df
    st.markdown("---")
    if not df.empty:
        st.subheader("🗑️ Delete Entry")
        st.caption("Select a patient from the search results to delete them.")
        if q: available_names = results["Name"].tolist()
        else: available_names = df["Name"].tolist()
        delete_target = st.selectbox("Select Patient to Delete", [""] + sorted(available_names), key="del_reg")
        if delete_target:
            idx = df.index[df["Name"] == delete_target].tolist()[0]
            st.error(f"⚠️ Warning: You are about to delete **{delete_target}**.")
            if st.button("❌ CONFIRM DELETE", type="primary"): df = df.drop(idx); save_data(df, "Patients"); st.success(f"Deleted {delete_target}"); st.rerun()

elif choice == "🗓️  Today's Queue":
    st.header("Today's Queue")
    if not df.empty:
        today_str = datetime.date.today().strftime("%d-%m-%Y")
        st.table(df[df["Last Visit"] == today_str][["Name", "Contact", "Treatments Done"]])
