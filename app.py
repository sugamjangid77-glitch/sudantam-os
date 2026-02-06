import streamlit as st
import pandas as pd
import datetime
import os
import urllib.parse
import socket
import time
import base64
import json
import subprocess
import webbrowser

# Try importing Cloud libs, handle errors gracefully
try:
    import gspread
    from google.oauth2.service_account import Credentials
    CLOUD_AVAILABLE = True
except ImportError:
    CLOUD_AVAILABLE = False

from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF

# ==========================================
# 1. PAGE CONFIG & SEXY UI STYLING
# ==========================================
st.set_page_config(page_title="Sudantam Dental Clinic", layout="wide", page_icon="🦷")

PRIMARY_COLOR = "#2C7A6F"
SECONDARY_COLOR = "#F0F8F5"
LOGO_FILENAME = "logo.jpeg"
PRESCRIPTION_FOLDER = "Prescriptions"
LOCAL_DB_FILE = "sudantam_patients.csv" # Fallback database

if not os.path.exists(PRESCRIPTION_FOLDER):
    os.makedirs(PRESCRIPTION_FOLDER)

def get_base64_image(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return ""

st.markdown(f"""
<style>
    /* HIDE DEFAULT STREAMLIT JUNK */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
    
    /* MAIN BACKGROUND */
    .stApp {{ background-color: {SECONDARY_COLOR}; }}
    
    /* --- SEXY SIDEBAR STYLING --- */
    [data-testid="stSidebar"] {{ 
        background-color: white; 
        border-right: 1px solid #eee;
        box-shadow: 2px 0 10px rgba(0,0,0,0.02);
    }}
    
    /* MENU CARD STYLE */
    [data-testid="stSidebar"] div[role="radiogroup"] label {{
        background-color: white !important; 
        padding: 16px 20px !important;
        border-radius: 15px !important; 
        border: 1px solid transparent !important; 
        margin-bottom: 12px !important;
        color: #555 !important; 
        font-weight: 600;
        font-size: 16px !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.03) !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        position: relative;
        overflow: hidden;
    }}
    
    /* HOVER ANIMATION (Slide Right + Glow) */
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
        transform: translateX(8px) scale(1.02);
        box-shadow: 0 8px 15px rgba(44, 122, 111, 0.15) !important;
        border-color: {PRIMARY_COLOR} !important;
        color: {PRIMARY_COLOR} !important;
        background-color: #F7FCFB !important;
    }}
    
    /* ACTIVE STATE (Pop Out + Gradient) */
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] {{
        background: linear-gradient(135deg, {PRIMARY_COLOR}, #1B5E55) !important; 
        color: white !important; 
        border: none !important;
        transform: scale(1.05);
        box-shadow: 0 10px 20px rgba(44, 122, 111, 0.3) !important;
    }}
    
    /* HIDE DEFAULT RADIO CIRCLES */
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{ display: none; }}
    
    /* BUTTON STYLING */
    div.stButton > button {{
        background-color: {PRIMARY_COLOR}; 
        color: white; 
        height: 55px; 
        border-radius: 12px; 
        font-weight: bold; 
        font-size: 18px;
        border: none;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: transform 0.2s, box-shadow 0.2s;
    }}
    div.stButton > button:hover {{ 
        background-color: #1B5E55; 
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }}
    
    /* ANIMATED LOGO */
    .splash-logo {{ width: 220px; animation: breathe 3s infinite ease-in-out; }}
    @keyframes breathe {{ 0% {{ transform: scale(1); opacity: 0.95; }} 50% {{ transform: scale(1.05); opacity: 1; }} 100% {{ transform: scale(1); opacity: 0.95; }} }}
</style>
""", unsafe_allow_html=True)

# SPLASH SCREEN (Runs once)
if 'first_load' not in st.session_state:
    placeholder = st.empty()
    logo_b64 = get_base64_image(LOGO_FILENAME)
    logo_html = f'<img src="data:image/jpeg;base64,{logo_b64}" class="splash-logo">' if logo_b64 else f"<h1 style='font-size:80px;'>🦷</h1>"
    with placeholder.container():
        st.markdown(f"""<div style="position:fixed; top:0; left:0; width:100vw; height:100vh; background:white; z-index:9999; display:flex; flex-direction:column; justify-content:center; align-items:center;">
            {logo_html}<div style="margin-top:20px; color:{PRIMARY_COLOR}; font-family:sans-serif; font-weight:bold; letter-spacing:3px;">SUDANTAM OS LOADING...</div></div>""", unsafe_allow_html=True)
    time.sleep(1.2)
    placeholder.empty()
    st.session_state['first_load'] = True

# ==========================================
# 2. CLOUD COMPATIBILITY SETUP & DATABASE
# ==========================================
# Create key.json from Secrets if on Cloud
if not os.path.exists("key.json"):
    if "gcp_service_account" in st.secrets:
        try:
            with open("key.json", "w") as f:
                json.dump(st.secrets["gcp_service_account"], f)
        except: pass

@st.cache_resource
def get_cloud_engine():
    if not CLOUD_AVAILABLE or not os.path.exists("key.json"): return None, None
    try:
        creds = Credentials.from_service_account_file("key.json", scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        client = gspread.authorize(creds)
        sh = client.open("Sudantam_Cloud_DB")
        return sh.worksheet("Patients"), sh.worksheet("Finances")
    except: return None, None

pt_sheet, fn_sheet = get_cloud_engine()

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
    
    # 3. Auto-Repair Columns
    expected_cols = ["Patient ID", "Name", "Age", "Gender", "Contact", "Last Visit", "Next Appointment", "Treatment Notes", "Medical History", "Treatments Done", "Affected Teeth", "Pending Amount", "Visit Log"]
    if df.empty:
        df = pd.DataFrame(columns=expected_cols)
    else:
        for c in expected_cols:
            if c not in df.columns: df[c] = ""
    return df

def save_data_hybrid(df):
    df.to_csv(LOCAL_DB_FILE, index=False)
    if pt_sheet:
        try:
            pt_sheet.clear()
            pt_sheet.update([df.columns.values.tolist()] + df.values.tolist())
        except: pass

df = load_data()

# ==========================================
# 3. TOOTH CHART ENGINE
# ==========================================
def create_visual_tooth_chart(selected_teeth_str):
    base_image_path = "tooth_chart_base.png"
    if not os.path.exists(base_image_path):
        img = Image.new('RGB', (800, 300), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((10, 150), "ERROR: Upload 'tooth_chart_base.png' to folder", fill="red")
        img.save("temp_tooth_chart.png"); return "temp_tooth_chart.png"

    img = Image.open(base_image_path).convert("RGBA")
    overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
    d = ImageDraw.Draw(overlay)
    W, H = img.size
    
    y_upper, y_lower = int(H * 0.28), int(H * 0.72)
    center_x, gap = int(W / 2), int(W / 19)
    selected = [s.strip() for s in str(selected_teeth_str).split(",")]

    def highlight(x, y):
        r = int(gap / 2.2)
        d.ellipse([x-r, y-r, x+r, y+r], fill=(255, 0, 0, 80), outline=(255, 0, 0, 255), width=4)

    for i in range(1, 9):
        off = (i - 0.5) * gap
        if f"UR{i}" in selected: highlight(center_x - off, y_upper)
        if f"UL{i}" in selected: highlight(center_x + off, y_upper)
        if f"LR{i}" in selected: highlight(center_x - off, y_lower)
        if f"LL{i}" in selected: highlight(center_x + off, y_lower)

    Image.alpha_composite(img, overlay).convert("RGB").save("temp_tooth_chart.png")
    return "temp_tooth_chart.png"

def fdi_convert(t_str):
    if not t_str or t_str == "nan": return "-"
    conv = []
    for c in str(t_str).split(','):
        c = c.strip()
        if "UR" in c: conv.append("1" + c.replace("UR",""))
        elif "UL" in c: conv.append("2" + c.replace("UL",""))
        elif "LL" in c: conv.append("3" + c.replace("LL",""))
        elif "LR" in c: conv.append("4" + c.replace("LR",""))
        else: conv.append(c)
    return ", ".join(conv)

def render_tooth_selector(key):
    st.info("🦷 Select Teeth")
    sel = []
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Left (UL/LL)")
        cols = st.columns(8)
        for i in range(8,0,-1): 
            if cols[8-i].checkbox(f"{i}", key=f"{key}UL{i}"): sel.append(f"UL{i}")
        cols2 = st.columns(8)
        for i in range(8,0,-1): 
            if cols2[8-i].checkbox(f"{i}", key=f"{key}LL{i}"): sel.append(f"LL{i}")
    with c2:
        st.caption("Right (UR/LR)")
        cols = st.columns(8)
        for i in range(1,9): 
            if cols[i-1].checkbox(f"{i}", key=f"{key}UR{i}"): sel.append(f"UR{i}")
        cols2 = st.columns(8)
        for i in range(1,9): 
            if cols2[i-1].checkbox(f"{i}", key=f"{key}LR{i}"): sel.append(f"LR{i}")
    return ", ".join(sel)

# ==========================================
# 4. PDF ENGINE
# ==========================================
class PDF(FPDF):
    def header(self):
        if os.path.exists(LOGO_FILENAME): self.image(LOGO_FILENAME, 10, 8, 30)
        self.set_y(10)
        self.set_font('Arial', 'B', 22); self.set_text_color(44, 122, 111)
        self.cell(0, 10, 'Sudantam Dental Clinic', 0, 1, 'R')
        self.set_font('Arial', 'B', 10); self.set_text_color(100)
        self.cell(0, 5, 'Dr. Sugam Jangid (BDS) | +91-8078656835', 0, 1, 'R')
        self.cell(0, 5, 'Opposite Agrasen Bhawan, Kishangarh', 0, 1, 'R')
        self.ln(5); self.set_draw_color(44, 122, 111); self.set_line_width(0.8)
        self.line(10, 35, 200, 35); self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8); self.set_text_color(128)
        self.cell(0, 10, 'Thank you for choosing Sudantam!', 0, 0, 'C')

    def patient_info_block(self, name, age, gender, date):
        self.set_fill_color(245, 248, 248); self.rect(10, self.get_y(), 190, 18, 'F')
        self.set_y(self.get_y() + 4)
        self.set_font('Arial', 'B', 11); self.set_text_color(0)
        self.set_x(15); self.cell(20, 10, "Patient:", 0, 0)
        self.set_font('Arial', '', 11); self.cell(80, 10, name.title(), 0, 0)
        self.set_font('Arial', 'B', 11); self.cell(15, 10, "Date:", 0, 0)
        self.set_font('Arial', '', 11); self.cell(30, 10, date, 0, 1)
        self.set_x(15); self.set_font('Arial', 'B', 11); self.cell(20, 5, "Age/Sex:", 0, 0)
        self.set_font('Arial', '', 11); self.cell(80, 5, f"{age} Yrs / {gender}", 0, 1); self.ln(8)

    def section_title(self, title):
        self.set_font('Arial', 'B', 14); self.set_text_color(44, 122, 111)
        self.cell(0, 10, title, 0, 1); self.set_text_color(0)
        self.set_draw_color(200); self.set_line_width(0.2)
        self.line(10, self.get_y(), 200, self.get_y()); self.ln(4)

    def invoice_row(self, item, price, bold=False):
        self.set_font('Arial', 'B' if bold else '', 11)
        self.cell(145, 8, f" {item}", 1, 0, 'L'); self.cell(45, 8, f"{price} ", 1, 1, 'R')

# --- DATA LISTS ---
sudantam_medicine_db = [
    {"name": "Amoxicillin 500mg", "brand": "Novamox", "dose": "1 tab TDS", "type": "Antibiotic"},
    {"name": "Amox 500mg + Clav 125mg", "brand": "Augmentin 625", "dose": "1 tab BD", "type": "Antibiotic"},
    {"name": "Metronidazole 400mg", "brand": "Metrogyl 400", "dose": "1 tab TDS", "type": "Antibiotic"},
    {"name": "Azithromycin 500mg", "brand": "Azithral 500", "dose": "1 tab OD", "type": "Antibiotic"},
    {"name": "Doxycycline 100mg", "brand": "Doxy-1 L-DR", "dose": "1 tab BD", "type": "Antibiotic"},
    {"name": "Aceclofenac + Paracetamol", "brand": "Zerodol-P", "dose": "1 tab BD", "type": "Analgesic"},
    {"name": "Aceclo + Para + Serratio", "brand": "Zerodol-SP", "dose": "1 tab BD", "type": "Analgesic"},
    {"name": "Ketorolac 10mg DT", "brand": "Ketorol DT", "dose": "1 tab SOS", "type": "Analgesic"},
    {"name": "Paracetamol 650mg", "brand": "Dolo 650", "dose": "1 tab TDS or SOS", "type": "Analgesic"},
    {"name": "Triamcinolone Acetonide", "brand": "Kenacort 0.1%", "dose": "Apply TDS", "type": "Topical Steroid"},
    {"name": "Carbamazepine 200mg", "brand": "Tegretol", "dose": "100mg BD", "type": "Neuralgia"},
    {"name": "Multivitamin + Lycopene", "brand": "Smyle / LycoRed", "dose": "1 cap OD", "type": "Antioxidant"},
    {"name": "Chlorhexidine 0.2%", "brand": "Clohex / Hexidine", "dose": "Rinse BD", "type": "Mouthwash"},
    {"name": "Povidone Iodine 2%", "brand": "Betadine Gargle", "dose": "Rinse TDS", "type": "Mouthwash"},
    {"name": "Metronidazole Gel", "brand": "Metrogyl DG", "dose": "Apply BD", "type": "Topical Gel"}
]

TREATMENT_PRICES = {
    "Consultation": 200, "X-Ray (IOPA)": 150, "Scaling & Polishing": 800, "Extraction": 500, 
    "Restoration (GIC)": 1000, "Restoration (Composite)": 1000, 
    "Root Canal (RCT)": 3500, "Crown (Metal)": 2000, "Crown (PFM)": 2000, "Crown (Zirconia)": 5000, 
    "Implant": 15000, "Orthodontics (Braces)": 25000, "Bleaching": 5000, 
    "Complete Denture": 12000, "RPD": 3000
}
MED_HISTORY = ["Diabetes", "Hypertension", "Thyroid", "Cardiac", "Allergy", "Pregnancy"]
COMMON_DIAGNOSES = ["Dental Caries", "GDT", "Abscess", "Gingivitis", "Periodontitis", "Fracture", "Mobile", "Impaction"]
ADVICE = list(TREATMENT_PRICES.keys()) + ["Operculectomy", "Flap Surgery", "Medicine Only"]
DAYS_OPTIONS = [f"{i} Days" for i in range(1, 11)] + ["2 Weeks", "1 Month", "SOS"]

# ==========================================
# 5. APP LOGIC
# ==========================================
with st.sidebar:
    if os.path.exists(LOGO_FILENAME): st.image(Image.open(LOGO_FILENAME), use_container_width=True)
    menu = st.radio("Menu", ["➕ Registration", "💊 Rx & Invoice", "💰 Defaulters", "📂 Registry", "📢 Marketing", "🔧 Manage Data"], label_visibility="collapsed")
    st.divider()
    try:
        df["Pending Amount"] = pd.to_numeric(df["Pending Amount"], errors='coerce').fillna(0)
        due = df[df["Pending Amount"] > 0]["Pending Amount"].sum()
        if due > 0: st.warning(f"Total Market Due: ₹{due}")
    except: pass

if menu == "➕ Registration":
    st.header("📋 Register Patient")
    with st.form("reg"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name"); phone = c2.text_input("Phone")
        age = c1.number_input("Age", 1, 100); gender = c2.selectbox("Gender", ["Male", "Female"])
        hist = st.multiselect("Medical History", MED_HISTORY)
        st.divider(); teeth = render_tooth_selector("reg")
        if st.form_submit_button("Save"):
            new_id = len(df) + 101
            new_row = {
                "Patient ID": new_id, "Name": name, "Age": age, "Gender": gender, "Contact": phone, 
                "Last Visit": datetime.date.today().strftime("%d-%m-%Y"), "Next Appointment": "Not Required", 
                "Treatment Notes": "", "Medical History": ", ".join(hist), "Treatments Done": "", 
                "Affected Teeth": teeth, "Pending Amount": 0, "Visit Log": ""
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_data_hybrid(df)
            st.success("Saved!"); st.rerun()

elif menu == "💊 Rx & Invoice":
    st.header("📝 Clinical Session")
    pt_name = st.selectbox("Select Patient", [""] + df["Name"].tolist())
    
    if pt_name:
        idx = df.index[df["Name"] == pt_name].tolist()[0]
        row = df.iloc[idx]
        c1, c2 = st.columns(2)
        diag = c1.multiselect("Diagnosis", COMMON_DIAGNOSES)
        rx_teeth = render_tooth_selector("rx")
        
        st.markdown("---")
        st.subheader("💊 Prescription")
        med_selections = st.multiselect("Select Medicines", [m['name'] for m in sudantam_medicine_db])
        final_rx_list = []
        if med_selections:
            for med_name in med_selections:
                def_data = next((m for m in sudantam_medicine_db if m['name'] == med_name), None)
                if not def_data: continue
                c_m1, c_m2, c_m3 = st.columns([3, 2, 2])
                c_m1.write(f"**{med_name}**"); 
                new_dose = c_m2.text_input("Dose", def_data['dose'], key=f"d_{med_name}")
                new_days = c_m3.selectbox("Days", DAYS_OPTIONS, key=f"dy_{med_name}")
                final_rx_list.append(f"{med_name} ({def_data['brand']}) -- {new_dose} -- {new_days}")

        st.markdown("---")
        st.subheader("💳 Invoice")
        bill_items = st.multiselect("Procedures", list(TREATMENT_PRICES.keys()))
        total = 0; final_items = []
        if bill_items:
            for item in bill_items:
                c1, c2 = st.columns([3,1])
                c1.write(item); p = c2.number_input("₹", value=TREATMENT_PRICES[item], key=item)
                total += p; final_items.append((item, p))
        
        old_due = float(row["Pending Amount"]) if row["Pending Amount"] else 0
        grand_total = total + old_due
        c1, c2 = st.columns(2); c1.metric("Total Bill", f"₹ {grand_total}")
        paid = c2.number_input("Paid Amount", 0.0, float(grand_total), float(grand_total))
        new_bal = grand_total - paid
        
        if st.button("🖨️ Finalize & Generate PDF"):
            # 1. Update Treatments & Balance
            new_tx = (str(row["Treatments Done"]) + " | " + ", ".join([f"{x[0]}" for x in final_items])) if row["Treatments Done"] else ", ".join([f"{x[0]}" for x in final_items])
            
            # 2. CREATE DETAILED HISTORY LOG
            today_str = datetime.date.today().strftime("%d-%m-%Y")
            rx_str = ", ".join([x.split(' -- ')[0] for x in final_rx_list]) if final_rx_list else "None"
            tx_str = ", ".join([x[0] for x in final_items]) if final_items else "Checkup"
            diag_str = ", ".join(diag) if diag else "Routine"
            
            new_log_entry = f"📅 {today_str}\n   Dx: {diag_str}\n   Tx: {tx_str} (Teeth: {rx_teeth})\n   💊 Rx: {rx_str}\n   💰 Paid: {paid}, Due: {new_bal}\n   -----------------------------\n"
            
            current_log = str(row.get("Visit Log", ""))
            updated_log = new_log_entry + current_log
            
            # Save to DF
            df.at[idx, "Treatments Done"] = new_tx
            df.at[idx, "Pending Amount"] = new_bal
            df.at[idx, "Affected Teeth"] = rx_teeth
            df.at[idx, "Visit Log"] = updated_log
            save_data_hybrid(df)
            
            # 3. Generate PDF
            chart_img = create_visual_tooth_chart(rx_teeth)
            pdf_filename = f"{pt_name}_Bill.pdf"
            save_path = os.path.join(PRESCRIPTION_FOLDER, pdf_filename)

            pdf = PDF(); pdf.add_page()
            pdf.patient_info_block(pt_name, str(row['Age']), row['Gender'], today_str)
            if diag: pdf.section_title("Clinical Findings"); pdf.cell(0, 7, f"Diagnosis: {', '.join(diag)}", 0, 1); pdf.ln(3)
            if os.path.exists(chart_img): pdf.section_title("Treatment Chart"); pdf.image(chart_img, x=10, w=190); pdf.ln(5)
            if final_rx_list:
                pdf.section_title("Prescription (Rx)"); pdf.set_font("Arial", '', 11)
                for i, r in enumerate(final_rx_list, 1):
                    parts = r.split(" -- ")
                    pdf.cell(10, 7, f"{i}.",0,0); pdf.cell(90, 7, parts[0], 0, 0); pdf.cell(0, 7, f"{parts[1]} for {parts[2]}", 0, 1)
                pdf.ln(5)
            pdf.section_title("Invoice")
            for it, pr in final_items: pdf.invoice_row(it, pr)
            pdf.ln(5); pdf.invoice_row("Total Procedure Cost", total, True)
            if old_due > 0: pdf.invoice_row("Previous Dues", old_due)
            pdf.invoice_row("Net Payable", grand_total, True); pdf.invoice_row("Paid Amount", paid)
            pdf.invoice_row("Balance Due", new_bal, True)
            
            qr_file = "review_qr.png"
            if os.path.exists(qr_file): pdf.ln(10); pdf.cell(0, 5, "Scan to Rate Us:", 0, 1, 'C'); pdf.image(qr_file, x=90, w=25)
            
            pdf.output(save_path)
            st.success(f"Generated: {save_path}")
            
            # 4. Actions
            c1, c2 = st.columns(2)
            with c1:
                # PDF Download for Mobile
                with open(save_path, "rb") as f:
                    st.download_button("📂 Download PDF", f, file_name=pdf_filename, mime="application/pdf")
            with c2:
                ph = str(row['Contact']).replace(" ", "").replace("-", "").replace("+", "")
                if len(ph) == 10: ph = "91" + ph
                msg = f"Hello {pt_name}, Invoice from Sudantam Dental Clinic"
                link = f"https://wa.me/{ph}?text={urllib.parse.quote(msg)}"
                st.markdown(f'''<a href="{link}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:15px; width:100%; border-radius:10px; font-weight:bold; font-size:18px; cursor:pointer;">📲 Send to WhatsApp</button></a>''', unsafe_allow_html=True)

elif menu == "💰 Defaulters":
    st.header("💰 Manage Dues")
    df["Pending Amount"] = pd.to_numeric(df["Pending Amount"], errors='coerce').fillna(0)
    st.dataframe(df[df["Pending Amount"] > 0][["Name", "Contact", "Pending Amount"]], use_container_width=True)

elif menu == "📂 Registry":
    st.header("📂 Registry (FDI Supported)")
    q = st.text_input("Search Patient Name")
    filter_date = c2.checkbox("Filter by Date") if q else False # Simplified UI
    res = df[df["Name"].str.contains(q, case=False, na=False)] if q else df
    
    if res.empty: st.warning("No patients found.")
    else:
        h1, h2, h3, h4 = st.columns([2, 2, 3, 1])
        h1.markdown("**Patient**"); h2.markdown("**Contact**"); h3.markdown("**Treatment**"); h4.markdown("**Chat**")
        st.divider()
        for idx, r in res.iterrows():
            with st.container():
                col1, col2, col3, col4 = st.columns([2, 2, 3, 1])
                col1.write(f"**{r['Name']}** ({r['Age']})")
                col2.write(f"{r['Contact']}")
                
                tx = r['Treatments Done'] if r['Treatments Done'] and r['Treatments Done'] != "nan" else "New"
                teeth = fdi_convert(r['Affected Teeth'])
                if len(tx) > 25: tx = tx[:25] + "..."
                col3.write(f"{tx} \n(Teeth: {teeth})")
                
                ph = str(r['Contact']).replace(" ", "").replace("-", "").replace("+", "")
                if len(ph) == 10: ph = "91" + ph
                wa_url = f"https://wa.me/{ph}"
                col4.markdown(f"[![Chat](https://img.icons8.com/color/30/whatsapp--v1.png)]({wa_url})")
                
                # --- HISTORY EXPANDER ---
                with st.expander(f"📜 View History / Old Rx for {r['Name']}"):
                    if r.get("Visit Log") and r["Visit Log"] != "nan":
                        st.text(r["Visit Log"])
                    else:
                        st.info("No history recorded yet.")
                st.divider()

elif menu == "📢 Marketing":
    st.header("📢 Marketing")
    st.info("Download all patient contacts (prefixed with 'pt').")
    vcf = ""
    for _, r in df.iterrows(): vcf += f"BEGIN:VCARD\nVERSION:3.0\nFN:pt {r['Name']}\nTEL;TYPE=CELL:{r['Contact']}\nEND:VCARD\n"
    st.download_button("Download Contacts (.vcf)", vcf, "sudantam_pts.vcf")
    
    st.divider()
    st.subheader("Patient List")
    search_q = st.text_input("🔍 Filter")
    m_df = df[df["Name"].str.contains(search_q, case=False, na=False)] if search_q else df
    
    c1, c2, c3, c4 = st.columns([2, 2, 3, 1])
    c1.markdown("**Name**"); c2.markdown("**Contact**"); c3.markdown("**Tx (Teeth)**"); c4.markdown("**Action**")
    
    for i, r in m_df.iterrows():
        c1, c2, c3, c4 = st.columns([2, 2, 3, 1])
        c1.write(f"**{r['Name']}**")
        c2.write(r['Contact'])
        tx = r['Treatments Done'] if r['Treatments Done'] and r['Treatments Done'] != "nan" else "-"
        teeth = fdi_convert(r['Affected Teeth'])
        if len(tx) > 20: tx = tx[:20] + "..."
        c3.write(f"{tx} ({teeth})")
        
        ph = str(r['Contact']).replace(" ", "").replace("-", "").replace("+", "")
        if len(ph) == 10: ph = "91" + ph
        link = f"https://wa.me/{ph}"
        c4.markdown(f"[Chat]({link})")
        st.markdown("<hr style='margin: 5px 0;'>", unsafe_allow_html=True)

elif menu == "🔧 Manage Data":
    st.header("🔧 Data Tools")
    st.info("Upload 'sudantam_patients.csv' to restore.")
    up = st.file_uploader("Upload CSV")
    if up:
        old = pd.read_csv(up)
        df = pd.concat([df, old], ignore_index=True)
        save_data_hybrid(df)
        st.success("Restored!")