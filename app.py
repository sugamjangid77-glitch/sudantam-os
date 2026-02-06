import streamlit as st
import pandas as pd
import datetime
import os
import urllib.parse
import json

# ==========================================
# 1. SURGICAL UI FIXES (ANT-DARK MODE & PRO UI)
# ==========================================
st.set_page_config(page_title="Sudantam OS", layout="wide", page_icon="🦷")

st.markdown("""
    <style>
        /* FORCE LIGHT SCHEME - PREVENTS BLACKOUTS */
        :root { color-scheme: light !important; }
        .stApp { background-color: #FFFFFF !important; color: #000000 !important; }
        
        /* LOGO & HEADER */
        [data-testid="stImage"] { text-align: center; display: flex; justify-content: center; }
        [data-testid="stImage"] img { width: 300px !important; border-radius: 15px; margin-bottom: 20px; }

        /* INPUT VISIBILITY (THE FIX) */
        label, p, .stMarkdown, .stText { color: #000000 !important; font-weight: 700 !important; }
        
        input, textarea, [data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            color: #000000 !important;
            border: 2px solid #2C7A6F !important;
            border-radius: 8px !important;
        }

        /* DROPDOWN & MULTISELECT ICONS */
        svg[data-testid="chevron-down"], svg[title="Clear all"] { fill: #2C7A6F !important; }

        /* TAB NAVIGATION (MOBILE PILL STYLE) */
        .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: #F0F2F6; padding: 10px; border-radius: 15px; }
        .stTabs [data-baseweb="tab"] {
            background-color: #FFFFFF !important;
            color: #2C7A6F !important;
            border: 1px solid #2C7A6F !important;
            border-radius: 30px !important;
            padding: 8px 15px !important;
            font-weight: bold !important;
            font-size: 13px !important;
        }
        .stTabs [aria-selected="true"] { background-color: #2C7A6F !important; color: #FFFFFF !important; }

        /* ACTION BUTTONS (TEAL & BOLD) */
        div.stButton > button {
            background-color: #2C7A6F !important;
            color: #FFFFFF !important;
            font-weight: 800 !important;
            font-size: 18px !important;
            height: 60px !important;
            border-radius: 12px !important;
            border: none !important;
        }

        #MainMenu, footer, header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# Files
LOCAL_DB_FILE = "sudantam_patients.csv"
LOGO_FILENAME = "logo.jpeg"

# ==========================================
# 2. DATA ENGINE
# ==========================================
def load_data():
    if os.path.exists(LOCAL_DB_FILE):
        return pd.read_csv(LOCAL_DB_FILE).astype(str)
    return pd.DataFrame(columns=["Patient ID", "Name", "Age", "Gender", "Contact", "Last Visit", "Medical History", "Pending Amount", "Visit Log", "Affected Teeth"])

def save_data(df):
    df.to_csv(LOCAL_DB_FILE, index=False)

df = load_data()

# ==========================================
# 3. INTERFACE
# ==========================================
if os.path.exists(LOGO_FILENAME):
    st.image(LOGO_FILENAME)

tabs = st.tabs(["📋 REG", "🦷 CLINICAL", "📂 RECORDS", "💰 DUES", "🔄 SYNC"])

# --- TAB 1: REGISTRATION ---
with tabs[0]:
    with st.form("registration_form", clear_on_submit=True):
        st.markdown("### 📝 Patient Intake")
        name = st.text_input("FULL NAME")
        phone = st.text_input("CONTACT NUMBER")
        
        c1, c2 = st.columns(2)
        with c1: age = st.number_input("AGE", min_value=1, step=1)
        with c2: gender = st.selectbox("GENDER", ["", "Male", "Female", "Other"])
        
        mh = st.multiselect("MEDICAL HISTORY", ["None", "Diabetes", "Hypertension", "Thyroid", "Asthma", "Allergy", "Cardiac"])
        
        if st.form_submit_button("✅ COMPLETE REGISTRATION"):
            if name:
                new_pt = {"Patient ID": len(df)+101, "Name": name, "Age": age, "Gender": gender, "Contact": phone, "Last Visit": datetime.date.today().strftime("%d-%m-%Y"), "Medical History": ", ".join(mh), "Pending Amount": 0, "Visit Log": ""}
                df = pd.concat([df, pd.DataFrame([new_pt])], ignore_index=True)
                save_data(df)
                st.success(f"Registered: {name}")
                st.rerun()

# --- TAB 2: CLINICAL (FDI SYSTEM + DROPDOWNS) ---
with tabs[1]:
    st.markdown("### 🦷 Treatment & Billing")
    pt_select = st.selectbox("SEARCH PATIENT", [""] + df["Name"].tolist())
    
    if pt_select:
        idx = df.index[df["Name"] == pt_select].tolist()[0]
        row = df.iloc[idx]
        
        with st.form("treatment_form"):
            st.info("🦷 FDI Tooth Selection")
            c1, c2 = st.columns(2)
            ur = c1.multiselect("UR (11-18)", [str(x) for x in range(11, 19)][::-1])
            ul = c2.multiselect("UL (21-28)", [str(x) for x in range(21, 29)])
            c3, c4 = st.columns(2)
            lr = c3.multiselect("LR (41-48)", [str(x) for x in range(41, 49)][::-1])
            ll = c4.multiselect("LL (31-38)", [str(x) for x in range(31, 39)])
            
            st.markdown("---")
            # TREATMENT DROPDOWN (AS IN PC APP)
            tx_dropdown = st.selectbox("TREATMENT DONE", [
                "", "Consultation", "Scaling & Polishing", "Composite Filling", "RCT (Root Canal)", 
                "Extraction", "Impacted Extraction", "PFM Crown", "Zirconia Crown", "Bridge", 
                "Complete Denture", "Partial Denture", "Veneers", "Other (Type Below)"
            ])
            tx_custom = st.text_input("IF 'OTHER', TYPE HERE:")
            final_tx = tx_custom if tx_dropdown == "Other (Type Below)" else tx_dropdown
            
            # MEDICINE DROPDOWN
            meds = st.multiselect("PRESCRIPTION", ["Amoxicillin", "Augmentin", "Zerodol-P", "Zerodol-SP", "Ketorol DT", "Pan-D", "Metrogyl"])
            
            c_bill1, c_bill2 = st.columns(2)
            bill = c_bill1.number_input("BILL AMOUNT", step=100)
            paid = c_bill2.number_input("PAID NOW", step=100)
            
            if st.form_submit_button("💾 SAVE TREATMENT"):
                fdi = ", ".join(ur + ul + lr + ll)
                old_due = float(row['Pending Amount']) if row['Pending Amount'] else 0
                new_due = old_due + (bill - paid)
                
                log = f"\n📅 {datetime.date.today()} | Tx: {final_tx} | Teeth: {fdi} | Paid: {paid}"
                df.at[idx, "Visit Log"] = str(row['Visit Log']) + log
                df.at[idx, "Pending Amount"] = new_due
                save_data(df)
                st.success("Record Saved!")
                st.rerun()

# --- TAB 3: RECORDS ---
with tabs[2]:
    st.markdown("### 📂 Registry")
    search_q = st.text_input("🔍 Search by Name")
    if search_q:
        results = df[df["Name"].str.contains(search_q, case=False, na=False)]
        for i, r in results.iterrows():
            with st.expander(f"{r['Name']} (Age: {r['Age']})"):
                c1, c2 = st.columns([3,1])
                c1.write(f"📞 {r['Contact']}\n💰 Balance: ₹{r['Pending Amount']}")
                if r['Contact']:
                    c2.link_button("📲 Chat", f"https://wa.me/91{r['Contact']}")
                st.text_area("History", r['Visit Log'], height=200)

# --- TAB 4: DUES ---
with tabs[3]:
    st.markdown("### 💰 Manage Dues")
    df["Pending Amount"] = pd.to_numeric(df["Pending Amount"], errors='coerce').fillna(0)
    defaulters = df[df["Pending Amount"] > 0]
    
    if not defaulters.empty:
        st.dataframe(defaulters[["Name", "Contact", "Pending Amount"]], use_container_width=True)
        with st.form("payment_form"):
            payer = st.selectbox("Select Patient to Pay", [""] + defaulters["Name"].tolist())
            rec = st.number_input("Amount Received", step=100)
            if st.form_submit_button("✅ UPDATE ACCOUNT"):
                if payer:
                    p_idx = df.index[df["Name"] == payer].tolist()[0]
                    df.at[p_idx, "Pending Amount"] = float(df.at[p_idx, "Pending Amount"]) - rec
                    save_data(df)
                    st.success("Balance Updated!")
                    st.rerun()

# --- TAB 5: SYNC ---
with tabs[4]:
    if st.button("🔄 REFRESH DATA"):
        st.rerun()
