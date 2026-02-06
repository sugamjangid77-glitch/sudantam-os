import streamlit as st
import pandas as pd
import datetime
import os
from fpdf import FPDF

# ==========================================
# 1. UI CONFIGURATION & THEME LOCK
# ==========================================
st.set_page_config(page_title="Sudantam OS", layout="wide", page_icon="🦷")

st.markdown("""
    <style>
        :root { color-scheme: light !important; }
        .stApp { background-color: #FFFFFF !important; color: #000000 !important; }
        
        /* --- LARGE CENTERED LOGO --- */
        [data-testid="stImage"] { display: flex; justify-content: center; }
        [data-testid="stImage"] img { width: 320px !important; border-radius: 15px; }

        /* --- LABELS & INPUTS --- */
        label, p, .stMarkdown { color: #000000 !important; font-weight: 700 !important; }
        input, select, textarea, [data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            color: #000000 !important;
            border: 2px solid #2C7A6F !important;
            border-radius: 8px !important;
        }

        /* --- PILL TABS WITH ICONS --- */
        .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: #F0F2F6; padding: 10px; border-radius: 15px; }
        .stTabs [data-baseweb="tab"] {
            background-color: #FFFFFF !important;
            color: #2C7A6F !important;
            border: 1px solid #2C7A6F !important;
            border-radius: 30px !important;
            padding: 10px 20px !important;
            font-weight: bold !important;
        }
        .stTabs [aria-selected="true"] { background-color: #2C7A6F !important; color: #FFFFFF !important; }

        /* --- ACTION BUTTONS: TEAL & WHITE --- */
        div.stButton > button {
            background-color: #2C7A6F !important;
            color: #FFFFFF !important;
            font-weight: 800 !important;
            font-size: 18px !important;
            height: 55px !important;
            border-radius: 12px !important;
            border: none !important;
        }
        
        /* Dropdown Arrow Fix */
        svg[data-testid="chevron-down"] { fill: #2C7A6F !important; }

        #MainMenu, footer, header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. PDF ENGINE
# ==========================================
class SudantamPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.set_text_color(44, 122, 111)
        self.cell(0, 10, 'SUDANTAM DENTAL CLINIC', 0, 1, 'C')
        self.set_font('Arial', '', 10); self.set_text_color(100)
        self.cell(0, 5, 'Dr. Sugam Jangid (BDS) | +91-8078656835', 0, 1, 'C')
        self.ln(10); self.set_draw_color(44, 122, 111); self.line(10, 30, 200, 30)

# ==========================================
# 3. DATA & STATE MANAGEMENT
# ==========================================
LOCAL_DB_FILE = "sudantam_patients.csv"
LOGO_FILENAME = "logo.jpeg"

if 'temp_rx' not in st.session_state: st.session_state.temp_rx = []
if 'pdf_ready' not in st.session_state: st.session_state.pdf_ready = None

def load_data():
    if os.path.exists(LOCAL_DB_FILE):
        return pd.read_csv(LOCAL_DB_FILE).astype(str)
    return pd.DataFrame(columns=["Name", "Age", "Gender", "Contact", "Pending Amount", "Visit Log"])

df = load_data()

# ==========================================
# 4. APP INTERFACE
# ==========================================
if os.path.exists(LOGO_FILENAME):
    st.image(LOGO_FILENAME)

tabs = st.tabs(["📝 REGISTRATION", "🦷 CLINICAL", "📂 RECORDS", "💰 DUES", "🔄 SYNC"])

# --- TAB 1: REGISTRATION ---
with tabs[0]:
    st.markdown("### 📝 Patient Registration")
    with st.form("reg_form", clear_on_submit=True):
        name = st.text_input("FULL NAME")
        phone = st.text_input("PHONE NUMBER")
        c1, c2 = st.columns(2)
        with c1: age = st.number_input("AGE", min_value=1, step=1)
        with c2: gender = st.selectbox("GENDER", ["", "Male", "Female", "Other"])
        mh = st.multiselect("MEDICAL HISTORY", ["Diabetes", "BP", "Thyroid", "Asthma", "Allergy"])
        
        if st.form_submit_button("✅ REGISTER PATIENT"):
            if name:
                new_row = {"Name": name, "Age": age, "Gender": gender, "Contact": phone, "Pending Amount": 0, "Visit Log": ""}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df.to_csv(LOCAL_DB_FILE, index=False)
                st.success(f"Registered: {name}")
                st.rerun()

# --- TAB 2: CLINICAL (FIXED SYNTAX) ---
with tabs[1]:
    st.markdown("### 🦷 Treatment & Prescription")
    pt_select = st.selectbox("SEARCH PATIENT", [""] + df["Name"].tolist())
    
    if pt_select:
        idx = df.index[df["Name"] == pt_select].tolist()[0]
        row = df.iloc[idx]
        
        st.info("🦷 FDI Tooth Selection Reference (11-48)")
        
        c1, c2 = st.columns(2)
        ur = c1.multiselect("UR (11-18)", [str(x) for x in range(11, 19)][::-1])
        ul = c2.multiselect("UL (21-28)", [str(x) for x in range(21, 29)])
        c3, c4 = st.columns(2)
        lr = c3.multiselect("LR (41-48)", [str(x) for x in range(41, 49)][::-1])
        ll = c4.multiselect("LL (31-38)", [str(x) for x in range(31, 39)])
        
        st.markdown("#### 💊 Add Medicines")
        with st.container(border=True):
            r1, r2, r3 = st.columns([2, 1, 1])
            med_name = r1.selectbox("Drug", ["", "Amoxicillin 500", "Augmentin 625", "Zerodol-SP", "Ketorol DT", "Pan-D", "Metrogyl 400"])
            dosage = r2.selectbox("Dosage", ["", "1-0-1 (BD)", "1-1-1 (TDS)", "1-0-0 (OD)", "0-0-1 (HS)", "SOS"])
            duration = r3.selectbox("Days", ["", "1 Day", "3 Days", "5 Days", "7 Days"])
            
            if st.button("➕ Add to Prescription"):
                if med_name and dosage:
                    st.session_state.temp_rx.append({"Medicine": med_name, "Dosage": dosage, "Duration": duration})
                    st.rerun()
        
        if st.session_state.temp_rx:
            st.table(pd.DataFrame(st.session_state.temp_rx))
            if st.button("🗑️ Clear Rx"):
                st.session_state.temp_rx = []
                st.rerun()

        with st.form("final_tx"):
            tx_done = st.selectbox("TREATMENT DONE", ["", "Consultation", "Scaling", "RCT", "Extraction", "Filling", "Crown"])
            notes = st.text_area("CLINICAL NOTES")
            b1, b2 = st.columns(2)
            bill = b1.number_input("BILL", step=100)
            paid = b2.number_input("PAID", step=100)
            
            if st.form_submit_button("💾 SAVE TREATMENT"):
                fdi = ", ".join(ur + ul + lr + ll)
                rx_str = " | ".join([f"{m['Medicine']} ({m['Dosage']})" for m in st.session_state.temp_rx])
                due = (bill - paid) + float(row['Pending Amount'] if row['Pending Amount'] else 0)
                
                log = f"\n📅 {datetime.date.today()}\nTx: {tx_done} (Teeth: {fdi})\nNotes: {notes}\nRx: {rx_str}\nPaid: {paid}"
                df.at[idx, "Visit Log"] = str(row['Visit Log']) + log
                df.at[idx, "Pending Amount"] = due
                df.to_csv(LOCAL_DB_FILE, index=False)
                
                # Create PDF
                pdf = SudantamPDF()
                pdf.add_page()
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 10, f"Patient: {row['Name']} ({row['Age']}/{row['Gender']})", 0, 1)
                pdf.cell(0, 10, f"Treatment: {tx_done} (Teeth: {fdi})", 0, 1)
                pdf.set_font('Arial', '', 11)
                pdf.multi_cell(0, 8, f"Notes: {notes}\nPrescription:\n" + "\n".join([f"- {m['Medicine']} ({m['Dosage']})" for m in st.session_state.temp_rx]))
                
                pdf_name = f"Rx_{row['Name']}.pdf"
                pdf.output(pdf_name)
                st.session_state.pdf_ready = pdf_name
                st.session_state.temp_rx = [] 
                st.rerun()

        if st.session_state.pdf_ready:
            with open(st.session_state.pdf_ready, "rb") as f:
                st.download_button("📥 DOWNLOAD PDF PRESCRIPTION", f, file_name=st.session_state.pdf_ready)
            if st.button("✅ Done (Clear)"):
                st.session_state.pdf_ready = None
                st.rerun()

# --- TAB 3: RECORDS ---
with tabs[2]:
    search_q = st.text_input("🔍 Search Registry")
    if search_q:
        res = df[df["Name"].str.contains(search_q, case=False, na=False)]
        for i, r in res.iterrows():
            with st.expander(f"{r['Name']} (Age: {r['Age']})"):
                st.write(f"📞 Contact: {r['Contact']}")
                st.text_area("History", r['Visit Log'], height=150)
                
                pdf_h = SudantamPDF()
                pdf_h.add_page()
                pdf_h.set_font('Arial', 'B', 12); pdf_h.cell(0, 10, f"Record: {r['Name']}", 0, 1)
                pdf_h.set_font('Arial', '', 10); pdf_h.multi_cell(0, 7, str(r['Visit Log']))
                h_file = f"Record_{r['Name']}.pdf"
                pdf_h.output(h_file)
                with open(h_file, "rb") as f:
                    st.download_button("📥 DOWNLOAD HISTORY PDF", f, file_name=h_file)

# --- TAB 4: DUES ---
with tabs[3]:
    df["Pending Amount"] = pd.to_numeric(df["Pending Amount"], errors='coerce').fillna(0)
    defaulters = df[df["Pending Amount"] > 0]
    if not defaulters.empty:
        st.dataframe(defaulters[["Name", "Contact", "Pending Amount"]], use_container_width=True)
        with st.form("payment"):
            payer = st.selectbox("Payer", [""] + defaulters["Name"].tolist())
            rec = st.number_input("Received", step=100)
            if st.form_submit_button("✅ UPDATE ACCOUNT"):
                p_idx = df.index[df["Name"] == payer].tolist()[0]
                df.at[p_idx, "Pending Amount"] = float(df.at[p_idx, "Pending Amount"]) - rec
                df.to_csv(LOCAL_DB_FILE, index=False)
                st.rerun()

# --- TAB 5: SYNC ---
with tabs[4]:
    if st.button("🔄 REFRESH SYSTEM"): st.rerun()
