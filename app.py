import streamlit as st
import pandas as pd
import datetime
import os
from fpdf import FPDF

# ==========================================
# 1. UI & THEME LOCK
# ==========================================
st.set_page_config(page_title="Sudantam OS", layout="wide", page_icon="🦷")

st.markdown("""
    <style>
        :root { color-scheme: light !important; }
        .stApp { background-color: #FFFFFF !important; }
        [data-testid="stImage"] img { width: 250px !important; border-radius: 10px; margin-bottom: 20px; }
        label, p { color: #000000 !important; font-weight: 700 !important; }
        input, select, textarea, [data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            color: #000000 !important;
            border: 2px solid #2C7A6F !important;
        }
        div.stButton > button {
            background-color: #2C7A6F !important;
            color: #FFFFFF !important;
            font-weight: 800 !important;
            height: 50px !important;
            border-radius: 10px !important;
        }
        .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: #F0F2F6; padding: 10px; border-radius: 15px; }
        .stTabs [data-baseweb="tab"] { background-color: #FFFFFF !important; color: #2C7A6F !important; border-radius: 25px !important; padding: 8px 15px !important; }
        .stTabs [aria-selected="true"] { background-color: #2C7A6F !important; color: #FFFFFF !important; }
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

if 'temp_rx' not in st.session_state:
    st.session_state.temp_rx = []

def load_data():
    if os.path.exists(LOCAL_DB_FILE):
        return pd.read_csv(LOCAL_DB_FILE).astype(str)
    return pd.DataFrame(columns=["Patient ID", "Name", "Age", "Gender", "Contact", "Last Visit", "Medical History", "Pending Amount", "Visit Log"])

df = load_data()

# ==========================================
# 4. INTERFACE
# ==========================================
if os.path.exists(LOGO_FILENAME):
    st.image(LOGO_FILENAME)

tabs = st.tabs(["📝 REGISTRATION", "🦷 CLINICAL", "📂 RECORDS", "💰 DUES", "🔄 SYNC"])

# --- TAB 2: CLINICAL (The New Rx Logic) ---
with tabs[1]:
    st.markdown("### 🦷 Treatment & Advanced Prescription")
    pt_select = st.selectbox("SEARCH PATIENT", [""] + df["Name"].tolist())
    
    if pt_select:
        idx = df.index[df["Name"] == pt_select].tolist()[0]
        row = df.iloc[idx]
        
        # --- A. Tooth Selection ---
        st.info("🦷 FDI Tooth Selection")
        

[Image of FDI tooth numbering system]

        c1, c2, c3, c4 = st.columns(4)
        ur = c1.multiselect("UR", [str(x) for x in range(11, 19)])
        ul = c2.multiselect("UL", [str(x) for x in range(21, 29)])
        lr = c3.multiselect("LR", [str(x) for x in range(41, 49)])
        ll = c4.multiselect("LL", [str(x) for x in range(31, 39)])
        
        # --- B. Individual Medicine Entry ---
        st.markdown("#### 💊 Add Medicines")
        with st.container(border=True):
            r1, r2, r3 = st.columns([2, 1, 1])
            med_name = r1.selectbox("Drug", ["", "Amoxicillin 500", "Augmentin 625", "Zerodol-SP", "Ketorol DT", "Pan-D", "Metrogyl 400", "Chymoral Forte"])
            dosage = r2.selectbox("Dosage", ["1-0-1 (BD)", "1-1-1 (TDS)", "1-0-0 (OD)", "0-0-1 (HS)", "SOS"])
            duration = r3.selectbox("Days", ["3 Days", "5 Days", "1 Day", "7 Days"])
            
            if st.button("➕ Add to Prescription"):
                if med_name:
                    st.session_state.temp_rx.append({"Medicine": med_name, "Dosage": dosage, "Duration": duration})
        
        # --- C. Live Rx List ---
        if st.session_state.temp_rx:
            st.markdown("**Current Prescription List:**")
            rx_df = pd.DataFrame(st.session_state.temp_rx)
            st.table(rx_df)
            if st.button("🗑️ Clear List"):
                st.session_state.temp_rx = []
                st.rerun()

        # --- D. Finalize Treatment ---
        with st.form("final_tx_form"):
            tx_done = st.selectbox("TREATMENT", ["", "Scaling", "RCT", "Extraction", "Filling", "Crown", "Bridge"])
            notes = st.text_area("CLINICAL NOTES")
            c_b1, c_b2 = st.columns(2)
            bill = c_b1.number_input("BILL", step=100)
            paid = c_b2.number_input("PAID", step=100)
            
            if st.form_submit_button("💾 SAVE & DOWNLOAD PDF"):
                fdi = ", ".join(ur + ul + lr + ll)
                rx_text = " | ".join([f"{m['Medicine']} ({m['Dosage']} for {m['Duration']})" for m in st.session_state.temp_rx])
                due = (bill - paid) + float(row['Pending Amount'] if row['Pending Amount'] else 0)
                
                # Update Database
                log = f"\n📅 {datetime.date.today()}\nTx: {tx_done} (Teeth: {fdi})\nRx: {rx_text}\nPaid: {paid}"
                df.at[idx, "Visit Log"] = str(row['Visit Log']) + log
                df.at[idx, "Pending Amount"] = due
                df.to_csv(LOCAL_DB_FILE, index=False)
                
                # Generate PDF
                pdf = SudantamPDF()
                pdf.add_page()
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 10, f"Patient: {row['Name']} ({row['Age']}/{row['Gender']})", 0, 1)
                pdf.cell(0, 10, f"Date: {datetime.date.today()}", 0, 1)
                pdf.ln(5)
                pdf.cell(0, 10, f"Treatment: {tx_done} (Teeth: {fdi})", 0, 1)
                pdf.ln(5)
                pdf.cell(0, 10, "Prescription:", 0, 1)
                pdf.set_font('Arial', '', 11)
                for item in st.session_state.temp_rx:
                    pdf.cell(0, 8, f"- {item['Medicine']} : {item['Dosage']} for {item['Duration']}", 0, 1)
                
                pdf_file = f"Rx_{row['Name']}.pdf"
                pdf.output(pdf_file)
                st.session_state.temp_rx = [] # Reset for next
                
                with open(pdf_file, "rb") as f:
                    st.download_button("📥 DOWNLOAD PDF", f, file_name=pdf_file)
                st.success("Record Saved!")

# --- TAB 1: REGISTRATION ---
with tabs[0]:
    with st.form("reg"):
        name = st.text_input("NAME"); phone = st.text_input("PHONE")
        c1, c2 = st.columns(2)
        age = c1.number_input("AGE", min_value=1); gen = c2.selectbox("SEX", ["", "Male", "Female", "Other"])
        if st.form_submit_button("REGISTER"):
            new_row = {"Name": name, "Age": age, "Gender": gen, "Contact": phone, "Pending Amount": 0, "Visit Log": ""}
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df.to_csv(LOCAL_DB_FILE, index=False)
            st.success("Registered!")
