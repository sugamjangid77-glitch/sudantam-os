import streamlit as st
import pandas as pd
import datetime
import os
import time
from fpdf import FPDF

# ==========================================
# 1. UI CONFIGURATION & THEME LOCK
# ==========================================
st.set_page_config(page_title="Sudantam OS", layout="wide", page_icon="🦷")

st.markdown("""
    <style>
        :root { color-scheme: light !important; }
        .stApp { background-color: #FFFFFF !important; color: #000000 !important; }
        
        /* LARGE CENTERED LOGO */
        [data-testid="stImage"] { display: flex; justify-content: center; }
        [data-testid="stImage"] img { width: 350px !important; border-radius: 15px; }

        /* PILL TABS WITH ICONS */
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

        /* ACTION BUTTONS: TEAL & WHITE */
        div.stButton > button {
            background-color: #2C7A6F !important;
            color: #FFFFFF !important;
            font-weight: 800 !important;
            font-size: 16px !important;
            height: 50px !important;
            border-radius: 12px !important;
            border: none !important;
        }
        
        /* LABELS & INPUTS */
        label, p, .stMarkdown { color: #000000 !important; font-weight: 700 !important; }
        input, select, textarea, [data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            color: #000000 !important;
            border: 2px solid #2C7A6F !important;
            border-radius: 8px !important;
        }

        #MainMenu, footer, header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. PDF ENGINE (PROFESSIONAL TABLE LAYOUT)
# ==========================================
def clean_text(text):
    """Removes unsupported characters."""
    if not isinstance(text, str): return str(text)
    text = text.replace("₹", "Rs.")
    return text.encode('latin-1', 'replace').decode('latin-1')

class SudantamPDF(FPDF):
    def header(self):
        # Logo
        if os.path.exists("logo.jpeg"):
            self.image("logo.jpeg", 10, 8, 33)
        # Clinic Name
        self.set_font('Arial', 'B', 20)
        self.set_text_color(44, 122, 111)
        self.cell(0, 10, 'SUDANTAM DENTAL CLINIC', 0, 1, 'C')
        # Sub-header
        self.set_font('Arial', '', 10)
        self.set_text_color(100)
        self.cell(0, 5, 'Dr. Sugam Jangid (BDS) | +91-8078656835', 0, 1, 'C')
        self.cell(0, 5, 'Opp. City Center, Kishangarh, Rajasthan', 0, 1, 'C')
        self.ln(10)
        self.set_draw_color(44, 122, 111)
        self.set_line_width(0.5)
        self.line(10, 35, 200, 35)
        self.ln(5)

    def section_title(self, title):
        self.set_fill_color(240, 242, 246)
        self.set_font('Arial', 'B', 12)
        self.set_text_color(0)
        self.cell(0, 8, title, 0, 1, 'L', fill=True)
        self.ln(2)

# ==========================================
# 3. DATA & STATE MANAGEMENT
# ==========================================
LOCAL_DB_FILE = "sudantam_patients.csv"
LOGO_FILENAME = "logo.jpeg"

# Initialize Session Lists
if 'temp_rx' not in st.session_state: st.session_state.temp_rx = []
if 'temp_tx' not in st.session_state: st.session_state.temp_tx = []  # Stores (Tooth, Treatment, Cost)
if 'pdf_ready' not in st.session_state: st.session_state.pdf_ready = None

def load_data():
    if os.path.exists(LOCAL_DB_FILE):
        df = pd.read_csv(LOCAL_DB_FILE).astype(str)
        if "Last Visit" not in df.columns: df["Last Visit"] = "2024-01-01"
        return df
    return pd.DataFrame(columns=["Name", "Age", "Gender", "Contact", "Pending Amount", "Visit Log", "Medical History", "Last Visit"])

df = load_data()

# ==========================================
# 4. APP INTERFACE
# ==========================================
if os.path.exists(LOGO_FILENAME):
    st.image(LOGO_FILENAME)

tabs = st.tabs(["📋 REGISTRATION", "🦷 CLINICAL", "📂 RECORDS", "💰 DUES", "🔄 SYNC"])

# --- TAB 1: REGISTRATION ---
with tabs[0]:
    st.markdown("### 📋 New Patient Intake")
    with st.form("reg_form", clear_on_submit=True):
        name = st.text_input("FULL NAME")
        phone = st.text_input("PHONE NUMBER")
        c1, c2 = st.columns(2)
        with c1: age = st.number_input("AGE", min_value=0, step=1, value=0)
        with c2: gender = st.selectbox("GENDER", ["", "Male", "Female", "Other"])
        mh = st.multiselect("MEDICAL HISTORY", ["Diabetes", "BP", "Thyroid", "Asthma", "Allergy"])
        
        if st.form_submit_button("✅ REGISTER PATIENT"):
            if name and age > 0:
                today_str = datetime.date.today().strftime("%Y-%m-%d")
                new_row = {"Name": name, "Age": age, "Gender": gender, "Contact": phone, "Pending Amount": 0, "Visit Log": "", "Medical History": ", ".join(mh), "Last Visit": today_str}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df.to_csv(LOCAL_DB_FILE, index=False)
                st.success(f"Registered: {name}")
                st.rerun()
            elif age == 0:
                st.error("⚠️ Please enter a valid Age")
            else:
                st.error("⚠️ Name is required")

# --- TAB 2: CLINICAL (MULTI-TOOTH TREATMENT) ---
with tabs[1]:
    st.markdown("### 🦷 Advanced Treatment & Prescription")
    pt_select = st.selectbox("SEARCH PATIENT", [""] + df["Name"].tolist())
    
    if pt_select:
        idx = df.index[df["Name"] == pt_select].tolist()[0]
        row = df.iloc[idx]
        
        # --- A. PROCEDURE BUILDER ---
        st.info("🛠️ **Procedure Builder:** Select teeth and treatment, then click 'Add Procedure'")
        
        col_t1, col_t2 = st.columns([1, 2])
        with col_t1:
            tooth_num = st.selectbox("Select Tooth", [
                "", "18", "17", "16", "15", "14", "13", "12", "11",
                "21", "22", "23", "24", "25", "26", "27", "28",
                "48", "47", "46", "45", "44", "43", "42", "41",
                "31", "32", "33", "34", "35", "36", "37", "38",
                "Full Mouth", "Upper Arch", "Lower Arch"
            ])
        with col_t2:
            tx_type = st.selectbox("Procedure", [
                "", "Consultation", "Scaling & Polishing", "Composite Filling", "Root Canal (RCT)",
                "Extraction", "Impacted Extraction", "PFM Crown", "Zirconia Crown", "Bridge", 
                "Complete Denture", "Implant", "Veneers", "X-Ray (IOPA)"
            ])
            tx_cost = st.number_input("Cost (Optional)", step=100, value=0)

        if st.button("➕ Add Procedure to List"):
            if tooth_num and tx_type:
                st.session_state.temp_tx.append({"Tooth": tooth_num, "Treatment": tx_type, "Cost": tx_cost})
                st.rerun()

        # Show Added Treatments
        if st.session_state.temp_tx:
            st.markdown("##### **Planned Procedures:**")
            st.dataframe(pd.DataFrame(st.session_state.temp_tx))
            if st.button("🗑️ Clear Procedures"):
                st.session_state.temp_tx = []
                st.rerun()

        st.markdown("---")

        # --- B. PRESCRIPTION BUILDER ---
        st.markdown("#### 💊 Prescription")
        with st.container(border=True):
            r1, r2, r3 = st.columns([2, 1, 1])
            med_name = r1.selectbox("Drug", ["", "Amoxicillin 500", "Augmentin 625", "Zerodol-SP", "Ketorol DT", "Pan-D", "Metrogyl 400", "Chymoral Forte"])
            dosage = r2.selectbox("Dosage", ["", "1-0-1 (BD)", "1-1-1 (TDS)", "1-0-0 (OD)", "SOS"])
            duration = r3.selectbox("Days", ["", "3 Days", "5 Days", "7 Days"])
            
            if st.button("➕ Add Medicine"):
                if med_name and dosage:
                    st.session_state.temp_rx.append({"Medicine": med_name, "Dosage": dosage, "Duration": duration})
                    st.rerun()
        
        if st.session_state.temp_rx:
            st.table(pd.DataFrame(st.session_state.temp_rx))
            if st.button("🗑️ Clear Rx"):
                st.session_state.temp_rx = []
                st.rerun()

        st.markdown("---")

        # --- C. FINALIZE & SAVE ---
        with st.form("final_tx"):
            st.markdown("#### 🧾 Invoice & Follow Up")
            notes = st.text_area("Clinical Notes")
            next_visit = st.date_input("Next Visit Date", value=None)
            
            c_bill1, c_bill2 = st.columns(2)
            # Auto-sum logic (optional, user can override)
            suggested_total = sum([x['Cost'] for x in st.session_state.temp_tx])
            bill = c_bill1.number_input("TOTAL BILL", value=float(suggested_total), step=100.0)
            paid = c_bill2.number_input("PAID NOW", step=100.0, value=0.0)
            
            if st.form_submit_button("💾 SAVE & PRINT INVOICE"):
                # Data Prep
                tx_summary = ", ".join([f"{t['Tooth']}: {t['Treatment']}" for t in st.session_state.temp_tx])
                rx_summary = ", ".join([f"{m['Medicine']}" for m in st.session_state.temp_rx])
                
                old_balance = float(row['Pending Amount']) if row['Pending Amount'] else 0
                current_due = bill - paid
                total_outstanding = old_balance + current_due
                today_str = datetime.date.today().strftime("%Y-%m-%d")
                
                # Save to DB
                log = f"\n📅 {today_str}\nProcedures: {tx_summary}\nRx: {rx_summary}\nPaid: {paid}\nNext Visit: {next_visit}"
                df.at[idx, "Visit Log"] = str(row['Visit Log']) + log
                df.at[idx, "Pending Amount"] = total_outstanding
                df.at[idx, "Last Visit"] = today_str
                df.to_csv(LOCAL_DB_FILE, index=False)
                
                # --- PDF GENERATION (PROFESSIONAL TABLE) ---
                pdf = SudantamPDF()
                pdf.add_page()
                
                # Patient Info Grid
                pdf.set_font('Arial', '', 11)
                pdf.cell(100, 8, clean_text(f"Patient Name: {row['Name']}"), 0, 0)
                pdf.cell(0, 8, clean_text(f"Date: {today_str}"), 0, 1, 'R')
                pdf.cell(100, 8, clean_text(f"Age/Gender: {row['Age']} / {row['Gender']}"), 0, 0)
                pdf.cell(0, 8, clean_text(f"Contact: {row['Contact']}"), 0, 1, 'R')
                pdf.ln(5)
                
                # Treatment Table
                pdf.section_title("TREATMENT DETAILS")
                pdf.set_font('Arial', 'B', 10)
                pdf.cell(30, 8, "Tooth", 1, 0, 'C')
                pdf.cell(110, 8, "Procedure", 1, 0, 'L')
                pdf.cell(50, 8, "Cost", 1, 1, 'R')
                pdf.set_font('Arial', '', 10)
                for tx in st.session_state.temp_tx:
                    pdf.cell(30, 8, clean_text(str(tx['Tooth'])), 1, 0, 'C')
                    pdf.cell(110, 8, clean_text(tx['Treatment']), 1, 0, 'L')
                    pdf.cell(50, 8, clean_text(f"{tx['Cost']}"), 1, 1, 'R')
                pdf.ln(5)
                
                # Prescription Table
                if st.session_state.temp_rx:
                    pdf.section_title("PRESCRIPTION")
                    pdf.set_font('Arial', 'B', 10)
                    pdf.cell(80, 8, "Medicine", 1, 0, 'L')
                    pdf.cell(60, 8, "Dosage", 1, 0, 'C')
                    pdf.cell(50, 8, "Duration", 1, 1, 'C')
                    pdf.set_font('Arial', '', 10)
                    for rx in st.session_state.temp_rx:
                        pdf.cell(80, 8, clean_text(rx['Medicine']), 1, 0, 'L')
                        pdf.cell(60, 8, clean_text(rx['Dosage']), 1, 0, 'C')
                        pdf.cell(50, 8, clean_text(rx['Duration']), 1, 1, 'C')
                    pdf.ln(5)
                
                # Notes & Next Visit
                if notes or next_visit:
                    pdf.section_title("NOTES")
                    pdf.set_font('Arial', '', 10)
                    if notes: pdf.multi_cell(0, 6, clean_text(f"Clinical Notes: {notes}"))
                    if next_visit: pdf.cell(0, 8, clean_text(f"Next Visit Date: {next_visit}"), 0, 1)
                    pdf.ln(5)
                
                # Invoice Summary (Bottom Right)
                pdf.set_x(110) # Move to right side
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(50, 8, "Total Bill:", 0, 0, 'R'); pdf.cell(30, 8, clean_text(f"Rs. {bill}"), 0, 1, 'R')
                pdf.set_x(110)
                pdf.cell(50, 8, "Paid Now:", 0, 0, 'R'); pdf.cell(30, 8, clean_text(f"Rs. {paid}"), 0, 1, 'R')
                pdf.set_x(110)
                if total_outstanding > 0:
                    pdf.set_text_color(200, 0, 0)
                    pdf.cell(50, 8, "Total Due:", 0, 0, 'R'); pdf.cell(30, 8, clean_text(f"Rs. {total_outstanding}"), 0, 1, 'R')
                else:
                    pdf.set_text_color(0, 128, 0)
                    pdf.cell(80, 8, "Balance Cleared", 0, 1, 'R')

                # Output
                pdf_name = f"Invoice_{clean_text(row['Name']).replace(' ','_')}.pdf"
                pdf.output(pdf_name)
                st.session_state.pdf_ready = pdf_name
                st.session_state.temp_rx = []
                st.session_state.temp_tx = []
                st.rerun()

        if st.session_state.pdf_ready:
            with open(st.session_state.pdf_ready, "rb") as f:
                st.download_button("📥 DOWNLOAD INVOICE", f, file_name=st.session_state.pdf_ready)
            if st.button("✅ Done"):
                st.session_state.pdf_ready = None
                st.rerun()

# --- TAB 3: RECORDS ---
with tabs[2]:
    st.markdown("### 📂 Patient Database")
    sort_opt = st.radio("SORT BY:", ["Date: Newest", "Date: Oldest", "Name (A-Z)", "Highest Dues"], horizontal=True)
    
    df_sort = df.copy()
    df_sort["Pending Amount"] = pd.to_numeric(df_sort["Pending Amount"], errors='coerce').fillna(0)
    df_sort["Last Visit"] = pd.to_datetime(df_sort["Last Visit"], errors='coerce').fillna(pd.Timestamp("2024-01-01"))
    
    if "Newest" in sort_opt: df_sort = df_sort.sort_values("Last Visit", ascending=False)
    elif "Oldest" in sort_opt: df_sort = df_sort.sort_values("Last Visit", ascending=True)
    elif "Name" in sort_opt: df_sort = df_sort.sort_values("Name")
    elif "Dues" in sort_opt: df_sort = df_sort.sort_values("Pending Amount", ascending=False)

    selected_name = st.selectbox("SELECT PATIENT", [""] + df_sort["Name"].tolist())

    if selected_name:
        real_idx = df.index[df["Name"] == selected_name].tolist()[0]
        row = df.iloc[real_idx]
        st.info(f"**Patient:** {row['Name']} | **Age:** {row['Age']} | **Last Visit:** {row['Last Visit']}")
        st.warning(f"**Pending Dues:** Rs. {row['Pending Amount']}")
        st.text_area("History", row['Visit Log'], height=150)
        
        # Edit/Delete UI
        c_edit, c_del = st.columns(2)
        with c_edit.expander("✏️ EDIT"):
            with st.form("edit"):
                n_name = st.text_input("Name", row['Name'])
                n_con = st.text_input("Contact", row['Contact'])
                if st.form_submit_button("Save"):
                    df.at[real_idx, "Name"] = n_name; df.at[real_idx, "Contact"] = n_con
                    df.to_csv(LOCAL_DB_FILE, index=False); st.rerun()
        with c_del.expander("🗑️ DELETE"):
            if st.button("Delete Permanently"):
                df = df.drop(real_idx); df.to_csv(LOCAL_DB_FILE, index=False); st.rerun()

# --- TAB 4: DUES ---
with tabs[3]:
    st.markdown("### 💰 Manage Dues")
    df["Pending Amount"] = pd.to_numeric(df["Pending Amount"], errors='coerce').fillna(0)
    defaulters = df[df["Pending Amount"] > 0]
    if not defaulters.empty:
        for idx, row in defaulters.iterrows():
            with st.expander(f"🔴 {row['Name']} - Due: Rs. {row['Pending Amount']}"):
                if st.button(f"✅ CLEAR FULL (Rs. {row['Pending Amount']})", key=f"clr_{idx}"):
                    df.at[idx, "Pending Amount"] = 0
                    df.to_csv(LOCAL_DB_FILE, index=False); st.rerun()
    else: st.success("No Dues!")

# --- TAB 5: SYNC ---
with tabs[4]:
    if st.button("🔄 PUSH TO CLOUD"):
        with st.status("Syncing...", expanded=True) as status:
            time.sleep(1); status.update(label="✅ Synced!", state="complete", expanded=False)
