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
# 1. CORE CONFIGURATION
# ==========================================
SHEET_ID = "120wdQHfL9mZB7OnYyHg-9o2Px-6cZogctcuNEHjhD9Q"
st.set_page_config(page_title="Sudantam Mobile", layout="wide", page_icon="🦷")

# --- "OUT OF THE WORLD" MOBILE CSS ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');
        
        html, body, [class*="css"] { font-family: 'Poppins', sans-serif; }
        .stApp { background-color: #F8F9FA; }
        
        /* CARD STYLE FOR CONTAINERS */
        .css-1r6slb0, .stForm {
            background-color: white;
            padding: 20px;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            border: 1px solid #E0E0E0;
            margin-bottom: 15px;
        }

        /* CUSTOM TABS (PILLS) */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px; background-color: transparent; padding: 5px; overflow-x: auto;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: white !important; color: #444 !important;
            border: none !important; border-radius: 50px !important;
            padding: 10px 20px !important; font-weight: 600 !important;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #2C7A6F 0%, #1A5C53 100%) !important;
            color: white !important; box-shadow: 0 4px 10px rgba(44, 122, 111, 0.3);
        }

        /* INPUT FIELDS */
        .stTextInput input, .stNumberInput input, .stSelectbox div, .stDateInput input {
            border-radius: 12px !important; border: 1px solid #EEE !important;
            background-color: #F8F9FA !important; height: 50px;
        }
        .stTextInput input:focus { border-color: #2C7A6F !important; background-color: white !important; }

        /* HERO BUTTONS */
        div.stButton > button {
            background: linear-gradient(135deg, #2C7A6F 0%, #205E55 100%) !important;
            color: white !important; border: none !important;
            border-radius: 15px !important; height: 55px !important;
            font-size: 16px !important; font-weight: 600 !important;
            box-shadow: 0 4px 12px rgba(44, 122, 111, 0.2); transition: all 0.3s;
        }
        div.stButton > button:active { transform: scale(0.98); }

        /* HIDE JUNK */
        #MainMenu, footer, header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. FAST DATA ENGINE (CACHED)
# ==========================================
@st.cache_resource
def get_db_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = None
    try:
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        elif os.path.exists("key.json"):
            creds = Credentials.from_service_account_file("key.json", scopes=scope)
        else:
            return None
        return gspread.authorize(creds).open_by_key(SHEET_ID).sheet1
    except: return None

# CACHE DATA FOR 30 SECONDS TO MAKE APP SUPER FAST
@st.cache_data(ttl=30)
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
        except: pass
    return pd.DataFrame(columns=["Name", "Age", "Gender", "Contact", "Pending Amount", "Visit Log", "Medical History", "Last Visit"])

def save_to_cloud(df):
    sheet = get_db_connection()
    if sheet:
        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.values.tolist())
        st.cache_data.clear() # Clear cache so new data shows immediately
        return True
    return False

df = load_data()

# ==========================================
# 3. PDF ENGINE (UNCHANGED)
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
        self.set_font('Arial', '', 10); self.set_text_color(80)
        self.cell(0, 5, 'Dr. Sugam Jangid (BDS) | +91-8078656835', 0, 1, 'C')
        self.ln(10); self.set_draw_color(44, 122, 111); self.line(10, 35, 200, 35); self.ln(5)
    def section_title(self, title):
        self.set_fill_color(230, 240, 238); self.set_font('Arial', 'B', 11); self.set_text_color(0)
        self.cell(0, 8, title, 0, 1, 'L', fill=True); self.ln(2)

if 'temp_rx' not in st.session_state: st.session_state.temp_rx = []
if 'temp_tx' not in st.session_state: st.session_state.temp_tx = []
if 'pdf_ready' not in st.session_state: st.session_state.pdf_ready = None
if 'wa_link' not in st.session_state: st.session_state.wa_link = None

# ==========================================
# 4. BEAUTIFUL MOBILE UI
# ==========================================
# Header
c1, c2 = st.columns([1, 4])
with c1:
    if os.path.exists("logo.jpeg"): st.image("logo.jpeg", width=70)
with c2:
    st.markdown("<h2 style='margin:0; padding-top:10px; color:#2C7A6F;'>Sudantam<br><span style='font-size:14px; color:grey'>Mobile OS</span></h2>", unsafe_allow_html=True)

st.write("") # Spacer

tabs = st.tabs(["Patient", "Clinical", "History", "Finance", "Sync"])

# --- TAB 1: REGISTRATION ---
with tabs[0]:
    st.markdown("##### 👤 New Registration")
    with st.form("reg_form", clear_on_submit=True):
        name = st.text_input("Full Name", placeholder="e.g. Rahul Sharma")
        phone = st.text_input("Mobile Number", placeholder="10 digits")
        c1, c2 = st.columns(2)
        age = c1.number_input("Age", min_value=0, step=1)
        gender = c2.selectbox("Gender", ["", "Male", "Female", "Other"])
        mh = st.multiselect("Medical History", ["None", "Diabetes", "BP", "Thyroid", "Asthma", "Allergy"])
        
        st.write("")
        if st.form_submit_button("Create Patient Record"):
            if name and age > 0:
                today = datetime.date.today().strftime("%Y-%m-%d")
                new_row = {"Name": name, "Age": age, "Gender": gender, "Contact": phone, "Pending Amount": 0, "Visit Log": "", "Medical History": ", ".join(mh), "Last Visit": today}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                if save_to_cloud(df):
                    st.toast(f"✅ Welcome to Sudantam, {name}!")
                    time.sleep(1); st.rerun()
                else: st.error("Sync Failed")

# --- TAB 2: CLINICAL ---
with tabs[1]:
    st.markdown("##### 🦷 Treatment & Rx")
    pt_select = st.selectbox("Select Patient", [""] + df["Name"].tolist())
    
    if pt_select:
        idx = df.index[df["Name"] == pt_select].tolist()[0]
        row = df.iloc[idx]
        
        # Procedure Card
        with st.container():
            if os.path.exists("tooth.png"): st.image("tooth.png", width=40)
            c1, c2 = st.columns([1, 2])
            tooth = c1.selectbox("Tooth", ["", "18","17","16","15","14","13","12","11", "21","22","23","24","25","26","27","28", "48","47","46","45","44","43","42","41", "31","32","33","34","35","36","37","38", "Full Mouth"])
            tx = c2.selectbox("Treatment", ["", "Consultation", "Scaling", "Filling", "RCT", "Extraction", "Surgical Ext", "Metal Braces", "Ceramic Braces", "Invisalign", "PFM Crown", "Zirconia Crown", "Bridge", "Denture", "RPD", "Implant", "Veneer", "X-Ray"])
            cost = st.number_input("Procedure Cost", step=100)
            if st.button("Add Procedure"):
                if tooth and tx: st.session_state.temp_tx.append({"Tooth": tooth, "Tx": tx, "Cost": cost}); st.rerun()
            
            if st.session_state.temp_tx:
                st.dataframe(pd.DataFrame(st.session_state.temp_tx), hide_index=True)
                if st.button("🗑️ Reset List"): st.session_state.temp_tx = []; st.rerun()

        # Rx Card
        with st.container():
            if os.path.exists("rx.png"): st.image("rx.png", width=40)
            m = st.selectbox("Medicine", ["", "Amoxicillin 500", "Augmentin 625", "Zerodol-SP", "Ketorol DT", "Pan-D", "Metrogyl 400", "Chymoral Forte"])
            c1, c2 = st.columns(2)
            d = c1.selectbox("Dose", ["", "1-0-1", "1-1-1", "1-0-0", "SOS"])
            dur = c2.selectbox("Days", ["", "3 Days", "5 Days", "7 Days"])
            if st.button("Add Medicine"):
                if m and d: st.session_state.temp_rx.append({"Medicine": m, "Dosage": d, "Duration": dur}); st.rerun()
            
            if st.session_state.temp_rx:
                st.dataframe(pd.DataFrame(st.session_state.temp_rx), hide_index=True)
                if st.button("🗑️ Reset Rx"): st.session_state.temp_rx = []; st.rerun()

        # Finalize Card
        with st.form("invoice"):
            st.markdown("**📝 Finalize Visit**")
            notes = st.text_area("Clinical Notes", height=80)
            next_v = st.date_input("Next Visit", value=None)
            
            auto_tot = sum([x['Cost'] for x in st.session_state.temp_tx])
            st.markdown(f"**Total Estimated: Rs. {auto_tot}**")
            
            c1, c2 = st.columns(2)
            bill = c1.number_input("Final Bill", value=float(auto_tot))
            paid = c2.number_input("Paid Now", step=100.0)
            
            if st.form_submit_button("✅ SAVE & GENERATE"):
                # ... (Logic Unchanged) ...
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
                
                # PDF
                pdf = SudantamPDF(); pdf.add_page(); pdf.set_font('Arial', '', 11)
                pdf.cell(0, 6, clean_text(f"Patient: {row['Name']} | Date: {today}"), 0, 1); pdf.ln(3)
                pdf.section_title("TREATMENT")
                pdf.set_font('Arial', '', 10)
                for t in st.session_state.temp_tx: pdf.cell(0, 6, clean_text(f"{t['Tooth']} - {t['Tx']} (Rs. {t['Cost']})"), 0, 1)
                pdf.ln(3)
                if st.session_state.temp_rx:
                    pdf.section_title("PRESCRIPTION"); 
                    for r in st.session_state.temp_rx: pdf.cell(0, 6, clean_text(f"{r['Medicine']} - {r['Dosage']} ({r['Duration']})"), 0, 1)
                pdf.ln(5); pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 6, f"Bill: {bill} | Paid: {paid}", 0, 1, 'R')
                if due > 0: pdf.set_text_color(200, 0, 0); pdf.cell(0, 6, f"TOTAL DUE: {due}", 0, 1, 'R')
                else: pdf.set_text_color(0, 128, 0); pdf.cell(0, 6, "All Clear", 0, 1, 'R')
                
                fname = f"Inv_{clean_text(row['Name']).replace(' ','_')}.pdf"
                pdf.output(fname); st.session_state.pdf_ready = fname
                msg = urllib.parse.quote(f"Dear {row['Name']},\nInvoice from Sudantam Dental Clinic.")
                st.session_state.wa_link = f"https://wa.me/91{row['Contact']}?text={msg}"
                st.session_state.temp_tx = []; st.session_state.temp_rx = []; st.rerun()

        if st.session_state.pdf_ready:
            st.success("Invoice Ready!")
            c1, c2 = st.columns(2)
            with c1:
                with open(st.session_state.pdf_ready, "rb") as f: st.download_button("📥 PDF", f, file_name=st.session_state.pdf_ready)
            with c2: st.link_button("📱 WhatsApp", st.session_state.wa_link)
            if st.button("Close"): st.session_state.pdf_ready = None; st.rerun()

# --- TAB 3: RECORDS ---
with tabs[2]:
    st.markdown("##### 📂 Patient History")
    sort = st.radio("", ["Newest", "Oldest", "A-Z", "Dues"], horizontal=True)
    
    df_v = df.copy()
    df_v["Pending Amount"] = pd.to_numeric(df_v["Pending Amount"], errors='coerce').fillna(0)
    df_v["Last Visit"] = pd.to_datetime(df_v["Last Visit"], errors='coerce').fillna(pd.Timestamp("2024-01-01"))
    
    if sort == "Newest": df_v = df_v.sort_values("Last Visit", ascending=False)
    elif sort == "Oldest": df_v = df_v.sort_values("Last Visit", ascending=True)
    elif sort == "A-Z": df_v = df_v.sort_values("Name")
    elif sort == "Dues": df_v = df_v.sort_values("Pending Amount", ascending=False)

    pt = st.selectbox("Search Patient", [""] + df_v["Name"].tolist())
    if pt:
        idx = df.index[df["Name"] == pt].tolist()[0]; row = df.iloc[idx]
        
        with st.container():
            st.info(f"**{row['Name']}** ({row['Age']}/{row['Gender']})")
            st.error(f"Dues: Rs. {row['Pending Amount']}")
            st.text_area("Log", row['Visit Log'], height=150)
            
            # PDF DL
            pdf_h = SudantamPDF(); pdf_h.add_page(); pdf_h.set_font('Arial', '', 11)
            pdf_h.cell(0, 6, clean_text(f"Patient History: {row['Name']}"), 0, 1, 'C'); pdf_h.ln(5)
            pdf_h.multi_cell(0, 6, clean_text(str(row['Visit Log'])))
            h_file = f"History_{clean_text(row['Name']).replace(' ','_')}.pdf"; pdf_h.output(h_file)
            with open(h_file, "rb") as f: st.download_button("📥 Download History PDF", f, file_name=h_file)

        with st.expander("⚙️ Edit / Delete"):
            n = st.text_input("Edit Name", row['Name'])
            c = st.text_input("Edit Phone", row['Contact'])
            if st.button("Save Changes"):
                df.at[idx, "Name"] = n; df.at[idx, "Contact"] = c; save_to_cloud(df); st.rerun()
            if st.button("DELETE RECORD", type="primary"):
                df = df.drop(idx); save_to_cloud(df); st.rerun()

# --- TAB 4: DUES ---
with tabs[3]:
    st.markdown("##### 💰 Pending Payments")
    df["Pending Amount"] = pd.to_numeric(df["Pending Amount"], errors='coerce').fillna(0)
    defaulters = df[df["Pending Amount"] > 0]
    
    if not defaulters.empty:
        for i, r in defaulters.iterrows():
            with st.container():
                c1, c2 = st.columns([2,1])
                c1.write(f"**{r['Name']}**")
                c1.caption(f"Due: Rs. {r['Pending Amount']}")
                if c2.button("Clear", key=f"c_{i}"):
                    df.at[i, "Pending Amount"] = 0; save_to_cloud(df); st.rerun()
    else: st.success("🎉 No pending dues!")

# --- TAB 5: SYNC ---
with tabs[4]:
    st.markdown("##### ☁️ Cloud Sync")
    if st.button("🔄 Refresh Data Now"):
        st.cache_data.clear(); st.rerun()
    st.info("App syncs automatically on Save.")
