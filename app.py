import streamlit as st
import pandas as pd
import datetime
import os
import urllib.parse
import json

# ==========================================
# 1. UI CONFIGURATION (PROFESSIONAL MEDICAL)
# ==========================================
st.set_page_config(page_title="Sudantam OS", layout="wide", page_icon="🦷")

st.markdown("""
    <style>
        :root { color-scheme: light !important; }
        .stApp { background-color: #FFFFFF !important; }
        
        /* --- CENTERED LARGE LOGO --- */
        [data-testid="stImage"] {
            text-align: center;
            display: flex;
            justify-content: center;
        }
        [data-testid="stImage"] img {
            width: 280px !important; 
            border-radius: 15px;
            margin-bottom: 20px;
        }

        /* --- TEXT & LABELS --- */
        label, p, .stMarkdown { color: #000000 !important; font-weight: 700 !important; }

        /* --- INPUT BOXES --- */
        input, textarea, [data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            color: #000000 !important;
            border: 2px solid #2C7A6F !important;
            border-radius: 8px !important;
        }

        /* --- ICON/PILL TABS --- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 12px;
            background-color: #F0F2F6;
            padding: 10px;
            border-radius: 15px;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: #FFFFFF !important;
            color: #2C7A6F !important;
            border: 1px solid #2C7A6F !important;
            border-radius: 30px !important;
            padding: 10px 25px !important;
            font-weight: bold !important;
        }
        .stTabs [aria-selected="true"] {
            background-color: #2C7A6F !important;
            color: #FFFFFF !important;
        }

        /* --- TEAL REGISTRATION BUTTON --- */
        div.stButton > button {
            background-color: #2C7A6F !important;
            color: #FFFFFF !important;
            font-weight: 800 !important;
            font-size: 18px !important;
            height: 60px !important;
            border-radius: 12px !important;
            border: none !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
        }
        
        /* Dropdown Arrow Fix */
        svg[data-testid="chevron-down"] { fill: #2C7A6F !important; }

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
# DISPLAY LARGE LOGO
if os.path.exists(LOGO_FILENAME):
    st.image(LOGO_FILENAME)

# TAB NAVIGATION WITH ICONS
tabs = st.tabs(["📋 REGISTRATION", "🦷 CLINICAL", "📂 RECORDS", "💰 DUES", "🔄 SYNC"])

# --- TAB 1: REGISTRATION ---
with tabs[0]:
    st.markdown("### Patient Registration")
    with st.form("registration_form", clear_on_submit=True):
        name = st.text_input("FULL NAME")
        phone = st.text_input("CONTACT NUMBER")
        
        c1, c2 = st.columns(2)
        with c1:
            age = st.number_input("AGE", min_value=1, step=1)
        with c2:
            gender = st.selectbox("GENDER", ["", "Male", "Female", "Other"])
        
        mh = st.multiselect("MEDICAL HISTORY", ["Diabetes", "BP", "Thyroid", "Asthma", "Allergy"])
        
        if st.form_submit_button("✅ COMPLETE REGISTRATION"):
            if not name:
                st.error("Name is required!")
            else:
                new_pt = {
                    "Patient ID": len(df)+101, "Name": name, "Age": age, "Gender": gender, "Contact": phone,
                    "Last Visit": datetime.date.today().strftime("%d-%m-%Y"),
                    "Medical History": ", ".join(mh), "Pending Amount": 0, "Visit Log": ""
                }
                df = pd.concat([df, pd.DataFrame([new_pt])], ignore_index=True)
                save_data(df)
                st.success(f"Registered: {name}")
                st.rerun()

# --- TAB 2: CLINICAL ---
with tabs[1]:
    st.markdown("### Treatment & Billing")
    pt_select = st.selectbox("SEARCH PATIENT", [""] + df["Name"].tolist())
    
    if pt_select:
        idx = df.index[df["Name"] == pt_select].tolist()[0]
        row = df.iloc[idx]
        
        with st.form("treatment_form"):
            st.info("🦷 FDI Tooth Selection")
            c1, c2 = st.columns(2)
            ur = c1.multiselect("UR (18-11)", [str(x) for x in range(11, 19)][::-1])
            ul = c2.multiselect("UL (21-28)", [str(x) for x in range(21, 29)])
            c3, c4 = st.columns(2)
            lr = c3.multiselect("LR (48-41)", [str(x) for x in range(41, 49)][::-1])
            ll = c4.multiselect("LL (31-38)", [str(x) for x in range(31, 39)])
            
            tx = st.text_input("TREATMENT DONE")
            c_bill1, c_bill2 = st.columns(2)
            bill = c_bill1.number_input("BILL", step=100)
            paid = c_bill2.number_input("PAID", step=100)
            
            if st.form_submit_button("💾 SAVE TREATMENT"):
                fdi = ", ".join(ur + ul + lr + ll)
                due = (bill - paid) + float(row['Pending Amount'] if row['Pending Amount'] else 0)
                log = f"\n📅 {datetime.date.today()} | Tx: {tx} | Teeth: {fdi} | Paid: {paid}"
                df.at[idx, "Visit Log"] = str(row['Visit Log']) + log
                df.at[idx, "Pending Amount"] = due
                save_data(df)
                st.success("Treatment Saved!")
                st.rerun()

# --- TAB 3: RECORDS ---
with tabs[2]:
    search_q = st.text_input("🔍 Search Registry")
    if search_q:
        results = df[df["Name"].str.contains(search_q, case=False, na=False)]
        for i, r in results.iterrows():
            with st.expander(f"{r['Name']} (Age: {r['Age']})"):
                c1, c2 = st.columns([3,1])
                c1.write(f"📞 {r['Contact']}\n💰 Due: ₹{r['Pending Amount']}")
                if r['Contact']:
                    c2.link_button("📲 Chat", f"https://wa.me/91{r['Contact']}")
                st.text_area("Visit History", r['Visit Log'], height=150)

# --- TAB 4: DUES (FIXED) ---
with tabs[3]:
    st.markdown("### Manage Dues")
    df["Pending Amount"] = pd.to_numeric(df["Pending Amount"], errors='coerce').fillna(0)
    defaulters = df[df["Pending Amount"] > 0]
    
    if not defaulters.empty:
        st.dataframe(defaulters[["Name", "Contact", "Pending Amount"]], use_container_width=True)
        
        with st.form("payment_form"):
            payer = st.selectbox("Select Payer", [""] + defaulters["Name"].tolist())
            rec = st.number_input("Amount Received", step=100)
            if st.form_submit_button("✅ UPDATE ACCOUNT"):
                if payer:
                    p_idx = df.index[df["Name"] == payer].tolist()[0]
                    df.at[p_idx, "Pending Amount"] = float(df.at[p_idx, "Pending Amount"]) - rec
                    save_data(df)
                    st.success("Balance Updated!")
                    st.rerun()
    else:
        st.success("No Dues Pending!")

# --- TAB 5: SYNC ---
with tabs[4]:
    if st.button("🔄 REFRESH DATA"):
        st.rerun()
