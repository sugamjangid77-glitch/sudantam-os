import streamlit as st
import pandas as pd
import datetime
import os
import urllib.parse
import json
from fpdf import FPDF

# ==========================================
# 1. PROFESSIONAL THEME & UI LOCK
# ==========================================
st.set_page_config(page_title="Sudantam OS", layout="wide", page_icon="🦷")

st.markdown("""
    <style>
        :root { color-scheme: light !important; }
        .stApp { background-color: #FFFFFF !important; color: #000000 !important; }
        [data-testid="stImage"] img { width: 280px !important; border-radius: 15px; margin-bottom: 20px; }
        label, p, .stMarkdown { color: #000000 !important; font-weight: 700 !important; }
        input, textarea, [data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            color: #000000 !important;
            border: 2px solid #2C7A6F !important;
            border-radius: 8px !important;
        }
        div.stButton > button {
            background-color: #2C7A6F !important;
            color: #FFFFFF !important;
            font-weight: 800 !important;
            font-size: 18px !important;
            height: 60px !important;
            border-radius: 12px !important;
        }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: #F0F2F6; padding: 10px; border-radius: 15px; }
        .stTabs [data-baseweb="tab"] {
            background-color: #FFFFFF !important;
            color: #2C7A6F !important;
            border: 1px solid #2C7A6F !important;
            border-radius: 30px !important;
            padding: 8px 15px !important;
            font-weight: bold !important;
        }
        .stTabs [aria-selected="true"] { background-color: #2C7A6F !important; color: #FFFFFF !important; }
        #MainMenu, footer, header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. PDF GENERATION ENGINE
# ==========================================
class SudantamPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.set_text_color(44, 122, 111)
        self.cell(0, 10, 'SUDANTAM DENTAL CLINIC', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.set_text_color(100)
        self.cell(0, 5, 'Dr. Sugam Jangid (BDS) | +91-8078656835', 0, 1, 'C')
        self.ln(10)
        self.set_draw_color(44, 122, 111)
        self.line(10, 30, 200, 30)

    def patient_info(self, name, age, gender, date):
        self.set_font('Arial', 'B', 11)
        self.set_text_color(0)
        self.cell(100, 8, f"Patient Name: {name}", 0, 0)
        self.cell(0, 8, f"Date: {date}", 0, 1, 'R')
        self.cell(0, 8, f"Age/Sex: {age} / {gender}", 0, 1)
        self.ln(5)

# ==========================================
# 3. DATA ENGINE
# ==========================================
LOCAL_DB_FILE = "sudantam_patients.csv"
LOGO_FILENAME = "logo.jpeg"

def load_data():
    if os.path.exists(LOCAL_DB_FILE):
        return pd.read_csv(LOCAL_DB_FILE).astype(str)
    return pd.DataFrame(columns=["Patient ID", "Name", "Age", "Gender", "Contact", "Last Visit", "Medical History", "Pending Amount", "Visit Log", "Affected Teeth"])

def save_data(df):
    df.to_csv(LOCAL_DB_FILE, index=False)

df = load_data()

# ==========================================
# 4. APP INTERFACE
# ==========================================
if os.path.exists(LOGO_FILENAME):
    st.image(LOGO_FILENAME)

tabs = st.tabs(["📋 REGISTRATION", "🦷 CLINICAL", "📂 RECORDS", "💰 DUES", "🔄 SYNC"])

# --- TAB 1: REGISTRATION ---
with tabs[0]:
    with st.form("reg_form", clear_on_submit=True):
        st.markdown("### 📝 New Patient Entry")
        name = st.text_input("FULL NAME")
        phone = st.text_input("CONTACT NUMBER")
        c1, c2 = st.columns(2)
        with c1: age = st.number_input("AGE", min_value=1, step=1)
        with c2: gender = st.selectbox("GENDER", ["", "Male", "Female", "Other"])
        mh = st.multiselect("MEDICAL HISTORY", ["None", "Diabetes", "BP", "Thyroid", "Asthma", "Allergy"])
        
        if st.form_submit_button("✅ REGISTER PATIENT"):
            if name:
                new_pt = {"Patient ID": len(df)+101, "Name": name, "Age": age, "Gender": gender, "Contact": phone, "Last Visit": datetime.date.today().strftime("%d-%m-%Y"), "Medical History": ", ".join(mh), "Pending Amount": 0, "Visit Log": ""}
                df = pd.concat([df, pd.DataFrame([new_pt])], ignore_index=True)
                save_data(df)
                st.success(f"Registered: {name}")
                st.rerun()

# --- TAB 2: CLINICAL (FDI SYSTEM + PDF) ---
with tabs[1]:
    st.markdown("### 🦷 Treatment & Prescription")
    pt_select = st.selectbox("SEARCH PATIENT", [""] + df["Name"].tolist())
    
    if pt_select:
        idx = df.index[df["Name"] == pt_select].tolist()[0]
        row = df.iloc[idx]
        
        with st.form("tx_form"):
            st.info("🦷 FDI Tooth Selection")
            c1, c2 = st.columns(2)
            ur = c1.multiselect("UR (11-18)", [str(x) for x in range(11, 19)][::-1])
            ul = c2.multiselect("UL (21-28)", [str(x) for x in range(21, 29)])
            c3, c4 = st.columns(2)
            lr = c3.multiselect("LR (41-48)", [str(x) for x in range(41, 49)][::-1])
            ll = c4.multiselect("LL (31-38)", [str(x) for x in range(31, 39)])
            
            st.markdown("---")
            tx_dropdown = st.selectbox("TREATMENT DONE", ["", "Scaling", "RCT", "Extraction", "Filling", "Crown", "Bridge", "Other"])
            tx_notes = st.text_area("CLINICAL NOTES / FINDINGS")
            
            st.markdown("**💊 PRESCRIPTION & DOSAGE**")
            col_m1, col_m2 = st.columns([2, 1])
            m1 = col_m1.multiselect("MEDICINES", ["Amoxicillin", "Augmentin 625", "Zerodol-SP", "Ketorol DT", "Pan-D", "Metrogyl"])
            dosage = col_m2.selectbox("FREQUENCY", ["", "1-0-1 (BD)", "1-1-1 (TDS)", "1-0-0 (OD)", "SOS (Emergency)"])
            
            st.markdown("---")
            c_bill1, c_bill2 = st.columns(2)
            bill = c_bill1.number_input("BILL AMOUNT", step=100)
            paid = c_bill2.number_input("PAID NOW", step=100)
            
            if st.form_submit_button("💾 SAVE & GENERATE PDF"):
                fdi = ", ".join(ur + ul + lr + ll)
                due = (bill - paid) + float(row['Pending Amount'] if row['Pending Amount'] else 0)
                log_entry = f"\n📅 {datetime.date.today()}\nTx: {tx_dropdown}\nTeeth: {fdi}\nRx: {', '.join(m1)} ({dosage})\nPaid: {paid}"
                
                df.at[idx, "Visit Log"] = str(row['Visit Log']) + log_entry
                df.at[idx, "Pending Amount"] = due
                save_data(df)
                
                # Generate PDF for download
                pdf = SudantamPDF()
                pdf.add_page()
                pdf.patient_info(row['Name'], row['Age'], row['Gender'], datetime.date.today().strftime("%d-%m-%Y"))
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 10, f"Rx & Treatment: {tx_dropdown}", 0, 1)
                pdf.set_font('Arial', '', 11)
                pdf.multi_cell(0, 8, f"Teeth: {fdi}\nFindings: {tx_notes}\n\nPrescription:\n{', '.join(m1)} --- {dosage}\n\nTotal Bill: {bill}\nPaid: {paid}\nBalance: {due}")
                
                pdf_output = f"Rx_{row['Name']}.pdf"
                pdf.output(pdf_output)
                
                with open(pdf_output, "rb") as f:
                    st.download_button("📥 DOWNLOAD PDF PRESCRIPTION", f, file_name=pdf_output)
                st.success("Record Saved Successfully!")

# --- TAB 3: RECORDS (HISTORY PDF) ---
with tabs[2]:
    search_q = st.text_input("🔍 Search Registry")
    if search_q:
        results = df[df["Name"].str.contains(search_q, case=False, na=False)]
        for i, r in results.iterrows():
            with st.expander(f"{r['Name']} (Age: {r['Age']})"):
                st.write(f"📞 Contact: {r['Contact']}")
                st.write(f"⚠️ Medical History: {r['Medical History']}")
                st.text_area("Full History", r['Visit Log'], height=200)
                
                # Download History PDF logic
                pdf_hist = SudantamPDF()
                pdf_hist.add_page()
                pdf_hist.patient_info(r['Name'], r['Age'], r['Gender'], "Full Record")
                pdf_hist.set_font('Arial', '', 10)
                pdf_hist.multi_cell(0, 6, str(r['Visit Log']))
                hist_name = f"History_{r['Name']}.pdf"
                pdf_hist.output(hist_name)
                with open(hist_name, "rb") as f:
                    st.download_button(f"📥 DOWNLOAD HISTORY PDF", f, file_name=hist_name)

# --- TAB 4: DUES ---
with tabs[3]:
    df["Pending Amount"] = pd.to_numeric(df["Pending Amount"], errors='coerce').fillna(0)
    defaulters = df[df["Pending Amount"] > 0]
    if not defaulters.empty:
        st.dataframe(defaulters[["Name", "Contact", "Pending Amount"]], use_container_width=True)
        with st.form("pay_form"):
            payer = st.selectbox("Select Payer", [""] + defaulters["Name"].tolist())
            rec = st.number_input("Received Amount", step=100)
            if st.form_submit_button("✅ UPDATE BALANCE"):
                if payer:
                    p_idx = df.index[df["Name"] == payer].tolist()[0]
                    df.at[p_idx, "Pending Amount"] = float(df.at[p_idx, "Pending Amount"]) - rec
                    save_data(df)
                    st.rerun()

# --- TAB 5: SYNC ---
with tabs[4]:
    if st.button("🔄 REFRESH SYSTEM"):
        st.rerun()
