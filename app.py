import streamlit as st
import pandas as pd
import datetime
import os
import time
import urllib.parse
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. CLOUD CONNECTION (BY ID = SYNCED)
# ==========================================
# 👇 PASTE THE SAME SHEET ID YOU USED FOR PC 👇
SHEET_ID = "120wdQHfL9mZB7OnYyHg-9o2Px-6cZogctcuNEHjhD9Q"

def get_db_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = None
    try:
        # Check for Secrets (Mobile Deployment)
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        # Check for Local Key (PC Testing)
        elif os.path.exists("key.json"):
            creds = Credentials.from_service_account_file("key.json", scopes=scope)
        else:
            return None
        
        # Connect using the ID
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).sheet1
    except Exception as e:
        return None

# ==========================================
# 2. DATA ENGINE
# ==========================================
def load_data():
    sheet = get_db_connection()
    if sheet:
        try:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            cols = ["Name", "Age", "Gender", "Contact", "Pending Amount", "Visit Log", "Medical History", "Last Visit"]
            for c in cols:
                if c not in df.columns: df[c] = ""
            return df.astype(str)
        except:
            pass
    return pd.DataFrame(columns=["Name", "Age", "Gender", "Contact", "Pending Amount", "Visit Log", "Medical History", "Last Visit"])

def save_to_cloud(df):
    sheet = get_db_connection()
    if sheet:
        try:
            sheet.clear()
            sheet.update([df.columns.values.tolist()] + df.values.tolist())
            return True
        except:
            return False
    return False

df = load_data()

# ==========================================
# 3. MOBILE UI THEME
# ==========================================
st.set_page_config(page_title="Sudantam Mobile", layout="wide", page_icon="🦷")

st.markdown("""
    <style>
        :root { color-scheme: light !important; }
        .stApp { background-color: #FFFFFF !important; color: black !important; }

        /* MOBILE TABS */
        .stTabs [data-baseweb="tab-list"] {
            gap: 5px; background-color: #f0f2f6; padding: 5px; border-radius: 10px;
            overflow-x: auto; white-space: nowrap;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: #FFFFFF !important; color: #2C7A6F !important;
            border: 1px solid #2C7A6F !important; border-radius: 20px !important;
            padding: 8px 15px !important; font-weight: bold !important;
        }
        .stTabs [aria-selected="true"] { background-color: #2C7A6F !important; color: #FFFFFF !important; }

        /* LARGE TOUCH BUTTONS */
        div.stButton > button {
            background-color: #2C7A6F !important; color: #FFFFFF !important;
            font-weight: 800 !important; font-size: 18px !important;
            height: 60px !important; border-radius: 15px !important;
            width: 100% !important; border: none !important; margin-top: 10px;
        }

        /* INPUTS */
        input, select, textarea, [data-baseweb="select"] > div {
            background-color: #FFFFFF !important; color: #000000 !important;
            border: 2px solid #2C7A6F !important; border-radius: 10px !important;
            height: 50px !important;
        }
        
        [data-testid="stImage"] { display: flex; justify-content: center; }
        [data-testid="stImage"] img { width: 80% !important; max-width: 300px; border-radius: 15px; }
        label, p, h1, h2, h3 { color: #000000 !important; }
        #MainMenu, footer, header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 4. PDF GENERATOR
# ==========================================
def clean_text(text):
    if not isinstance(text, str): return str(text)
    text = text.replace("₹", "Rs.")
    return text.encode('latin-1', 'replace').decode('latin-1')

class SudantamPDF(FPDF):
    def header(self):
        if os.path.exists("logo.jpeg"): self.image("logo.jpeg", 10, 8, 30)
        self.set_font('Arial', 'B', 18)
        self.set_text_color(44, 122, 111)
        self.cell(0, 10, 'SUDANTAM DENTAL CLINIC', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.set_text_color(80)
        self.cell(0, 5, 'Dr. Sugam Jangid (BDS) | +91-8078656835', 0, 1, 'C')
        self.ln(10); self.set_draw_color(44, 122, 111); self.line(10, 35, 200, 35); self.ln(5)

    def section_title(self, title):
        self.set_fill_color(230, 240, 238)
        self.set_font('Arial', 'B', 11)
        self.set_text_color(0)
        self.cell(0, 8, title, 0, 1, 'L', fill=True)
        self.ln(2)

if 'temp_rx' not in st.session_state: st.session_state.temp_rx = []
if 'temp_tx' not in st.session_state: st.session_state.temp_tx = []
if 'pdf_ready' not in st.session_state: st.session_state.pdf_ready = None
if 'wa_link' not in st.session_state: st.session_state.wa_link = None

# ==========================================
# 5. MOBILE APP INTERFACE
# ==========================================
if os.path.exists("logo.jpeg"): st.image("logo.jpeg")

tabs = st.tabs(["📋 REG", "🦷 CLINIC", "📂 DATA", "💰 DUES", "☁️ SYNC"])

# --- TAB 1: REGISTRATION ---
with tabs[0]:
    st.markdown("### 📋 New Patient")
    with st.form("reg_form", clear_on_submit=True):
        name = st.text_input("FULL NAME")
        phone = st.text_input("PHONE")
        c1, c2 = st.columns(2)
        age = c1.number_input("AGE", min_value=0, step=1, value=0)
        gender = c2.selectbox("SEX", ["", "Male", "Female", "Other"])
        mh = st.multiselect("MEDICAL HISTORY", ["None", "Diabetes", "BP", "Thyroid", "Asthma", "Allergy"])
        
        if st.form_submit_button("✅ REGISTER & SYNC"):
            if name and age > 0:
                today = datetime.date.today().strftime("%Y-%m-%d")
                new_row = {"Name": name, "Age": age, "Gender": gender, "Contact": phone, "Pending Amount": 0, "Visit Log": "", "Medical History": ", ".join(mh), "Last Visit": today}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                if save_to_cloud(df):
                    st.success(f"Saved: {name}")
                    st.rerun()
                else:
                    st.error("Check Internet!")
            else:
                st.error("Name & Age Required!")

# --- TAB 2: CLINICAL ---
with tabs[1]:
    st.markdown("### 🦷 Treatment")
    pt_select = st.selectbox("SELECT PATIENT", [""] + df["Name"].tolist())
    
    if pt_select:
        idx = df.index[df["Name"] == pt_select].tolist()[0]
        row = df.iloc[idx]
        
        # A. Procedure
        with st.expander("🛠️ Add Procedure", expanded=True):
            st.info("Select Tooth -> Treatment -> Add")
            c1, c2 = st.columns([1, 2])
            tooth = c1.selectbox("Tooth", ["", "18","17","16","15","14","13","12","11", "21","22","23","24","25","26","27","28", "48","47","46","45","44","43","42","41", "31","32","33","34","35","36","37","38", "Full Mouth"])
            tx = c2.selectbox("Tx", ["", 
                "Consultation", "Scaling", "Filling", "RCT", 
                "Extraction", "Surgical Ext", 
                "Metal Braces", "Ceramic Braces", "Invisalign",
                "PFM Crown", "Zirconia Crown", "Bridge", 
                "Denture", "RPD", "Implant", "Veneer", "X-Ray"])
            cost = st.number_input("Cost", step=100, value=0)
            
            if st.button("➕ Add Tx"):
                if tooth and tx:
                    st.session_state.temp_tx.append({"Tooth": tooth, "Tx": tx, "Cost": cost})
                    st.rerun()
            if st.session_state.temp_tx:
                st.dataframe(pd.DataFrame(st.session_state.temp_tx))
                if st.button("Clear Tx"): st.session_state.temp_tx = []; st.rerun()

        # B. Prescription
        with st.expander("💊 Add Medicine", expanded=False):
            m = st.selectbox("Drug", ["", "Amoxicillin 500", "Augmentin 625", "Zerodol-SP", "Ketorol DT", "Pan-D", "Metrogyl 400", "Chymoral Forte"])
            d = st.selectbox("Dose", ["", "1-0-1", "1-1-1", "1-0-0", "SOS"])
            dur = st.selectbox("Days", ["", "3 Days", "5 Days", "7 Days"])
            
            if st.button("➕ Add Rx"):
                if m and d:
                    st.session_state.temp_rx.append({"Medicine": m, "Dosage": d, "Duration": dur})
                    st.rerun()
            if st.session_state.temp_rx:
                st.table(pd.DataFrame(st.session_state.temp_rx))
                if st.button("Clear Rx"): st.session_state.temp_rx = []; st.rerun()

        # C. Finalize
        st.markdown("---")
        with st.form("finish"):
            st.markdown("#### 🧾 Invoice")
            notes = st.text_area("Notes")
            next_v = st.date_input("Next Visit", value=None)
            
            auto_tot = sum([x['Cost'] for x in st.session_state.temp_tx])
            bill = st.number_input("Total Bill", value=float(auto_tot))
            paid = st.number_input("Paid Now", step=100.0, value=0.0)
            
            if st.form_submit_button("💾 SAVE & GENERATE"):
                tx_s = ", ".join([f"{t['Tooth']}:{t['Tx']}" for t in st.session_state.temp_tx])
                rx_s = ", ".join([f"{m['Medicine']}" for m in st.session_state.temp_rx])
                
                old = float(row['Pending Amount']) if row['Pending Amount'] else 0
                due = old + (bill - paid)
                today = datetime.date.today().strftime("%Y-%m-%d")
                
                log = f"\n📅 {today}\nTx: {tx_s}\nRx: {rx_s}\nPaid: {paid}\nNext: {next_v}"
                df.at[idx, "Visit Log"] = str(row['Visit Log']) + log
                df.at[idx, "Pending Amount"] = due
                df.at[idx, "Last Visit"] = today
                
                save_to_cloud(df)
                
                pdf = SudantamPDF()
                pdf.add_page()
                pdf.set_font('Arial', '', 11)
                pdf.cell(0, 6, clean_text(f"Patient: {row['Name']} | Date: {today}"), 0, 1)
                pdf.ln(3)
                
                pdf.section_title("TREATMENT")
                pdf.set_font('Arial', '', 10)
                for t in st.session_state.temp_tx:
                    pdf.cell(0, 6, clean_text(f"{t['Tooth']} - {t['Tx']} (Rs. {t['Cost']})"), 0, 1)
                pdf.ln(3)
                
                if st.session_state.temp_rx:
                    pdf.section_title("PRESCRIPTION")
                    for r in st.session_state.temp_rx:
                        pdf.cell(0, 6, clean_text(f"{r['Medicine']} - {r['Dosage']} ({r['Duration']})"), 0, 1)
                    pdf.ln(3)
                
                pdf.ln(5)
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 6, f"Bill: {bill} | Paid: {paid}", 0, 1, 'R')
                if due > 0:
                    pdf.set_text_color(200, 0, 0)
                    pdf.cell(0, 6, f"TOTAL DUE: {due}", 0, 1, 'R')
                else:
                    pdf.set_text_color(0, 128, 0)
                    pdf.cell(0, 6, "All Clear", 0, 1, 'R')

                fname = f"Inv_{clean_text(row['Name']).replace(' ','_')}.pdf"
                pdf.output(fname)
                
                msg = urllib.parse.quote(f"Dear {row['Name']},\nHere is your invoice for today's treatment at Sudantam Dental Clinic.")
                wa = f"https://wa.me/91{row['Contact']}?text={msg}"
                
                st.session_state.pdf_ready = fname
                st.session_state.wa_link = wa
                st.session_state.temp_tx = []
                st.session_state.temp_rx = []
                st.rerun()

        if st.session_state.pdf_ready:
            c1, c2 = st.columns(2)
            with c1:
                with open(st.session_state.pdf_ready, "rb") as f:
                    st.download_button("📥 PDF", f, file_name=st.session_state.pdf_ready)
            with c2:
                st.link_button("📱 WhatsApp", st.session_state.wa_link)
            if st.button("✅ Done"): st.session_state.pdf_ready = None; st.rerun()

# --- TAB 3: RECORDS ---
with tabs[2]:
    st.markdown("### 📂 Records")
    sort = st.radio("Sort", ["Newest", "Oldest", "A-Z", "Dues"], horizontal=True)
    
    df_v = df.copy()
    df_v["Pending Amount"] = pd.to_numeric(df_v["Pending Amount"], errors='coerce').fillna(0)
    df_v["Last Visit"] = pd.to_datetime(df_v["Last Visit"], errors='coerce').fillna(pd.Timestamp("2024-01-01"))
    
    if sort == "Newest": df_v = df_v.sort_values("Last Visit", ascending=False)
    elif sort == "Oldest": df_v = df_v.sort_values("Last Visit", ascending=True)
    elif sort == "A-Z": df_v = df_v.sort_values("Name")
    elif sort == "Dues": df_v = df_v.sort_values("Pending Amount", ascending=False)

    pt = st.selectbox("Select Patient", [""] + df_v["Name"].tolist())
    if pt:
        idx = df.index[df["Name"] == pt].tolist()[0]
        row = df.iloc[idx]
        st.info(f"{row['Name']} | Due: Rs. {row['Pending Amount']}")
        st.text_area("History", row['Visit Log'], height=150)
        
        with st.expander("Edit / Delete"):
            n = st.text_input("Name", row['Name'])
            c = st.text_input("Phone", row['Contact'])
            if st.button("Save Edit"):
                df.at[idx, "Name"] = n; df.at[idx, "Contact"] = c
                save_to_cloud(df); st.rerun()
            if st.button("DELETE RECORD", type="primary"):
                df = df.drop(idx); save_to_cloud(df); st.rerun()

# --- TAB 4: DUES ---
with tabs[3]:
    st.markdown("### 💰 Dues")
    df["Pending Amount"] = pd.to_numeric(df["Pending Amount"], errors='coerce').fillna(0)
    defaulters = df[df["Pending Amount"] > 0]
    
    if not defaulters.empty:
        for i, r in defaulters.iterrows():
            with st.expander(f"🔴 {r['Name']} (Rs. {r['Pending Amount']})"):
                if st.button(f"✅ Clear Full ({r['Pending Amount']})", key=f"c_{i}"):
                    df.at[i, "Pending Amount"] = 0
                    save_to_cloud(df); st.rerun()
    else:
        st.success("No Dues!")

# --- TAB 5: SYNC ---
with tabs[4]:
    st.markdown("### ☁️ Sync")
    if st.button("🔄 Refresh Data"): st.cache_data.clear(); st.rerun()
