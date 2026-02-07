import streamlit as st
import pandas as pd

# -----------------------------------------------------------------------------
# MOBILE CONFIGURATION (Centered Mode)
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Sudantam Mobile", page_icon="🦷", layout="centered")

# --- NO SIDEBAR (Better for Mobile) ---
# Use a top selectbox for navigation instead
st.image("tooth.png", width=50)
st.write("### Sudantam Mobile 📱")

# Top Navigation Menu
page = st.selectbox("Go to:", ["Patient Details", "Clinical Notes", "Rx Prescription", "Billing"])

if 'meds_mobile' not in st.session_state:
    st.session_state.meds_mobile = []

# --- PAGE 1: PATIENT DETAILS ---
if page == "Patient Details":
    st.info("👤 New Patient Entry")
    name = st.text_input("Patient Name")
    mobile = st.text_input("Mobile No", type="password") # Hides number for privacy
    age = st.slider("Age", 0, 100, 25)
    if st.button("Save Entry", type="primary", use_container_width=True):
        st.success("Saved!")

# --- PAGE 2: CLINICAL NOTES ---
elif page == "Clinical Notes":
    st.info("🦷 Clinical Assessment")
    # Stacked vertically for phone screens
    st.write("**Chief Complaint**")
    cc = st.text_area("", placeholder="Enter complaint here...", height=100)
    
    st.write("**Diagnosis**")
    diag = st.text_input("", placeholder="e.g. Irreversible Pulpitis")
    
    st.write("**Treatment**")
    tx = st.selectbox("", ["RCT", "Extraction", "Scaling", "Restoration"])
    
    if st.button("Save Notes", type="primary", use_container_width=True):
        st.success("Notes Updated")

# --- PAGE 3: PRESCRIPTION ---
elif page == "Rx Prescription":
    st.info("💊 Quick Rx")
    
    # Simple form
    med = st.text_input("Medicine Name")
    col1, col2 = st.columns(2)
    with col1: freq = st.selectbox("Freq", ["1-0-1", "1-0-0", "SOS"])
    with col2: dur = st.text_input("Days", "5 days")
    
    if st.button("Add Medicine ➕", use_container_width=True):
        st.session_state.meds_mobile.append(f"{med} ({freq}) - {dur}")

    # Simple list view instead of complex table
    if st.session_state.meds_mobile:
        st.write("---")
        st.write("**Current Rx:**")
        for item in st.session_state.meds_mobile:
            st.text(f"• {item}")

# --- PAGE 4: BILLING ---
elif page == "Billing":
    st.info("🧾 Quick Bill")
    
    total = st.number_input("Total Bill (₹)", step=500)
    received = st.number_input("Received (₹)", step=500)
    
    # Big bold text for due amount
    due = total - received
    if due > 0:
        st.error(f"⚠️ PENDING: ₹ {due}")
    else:
        st.success("✅ FULLY PAID")
        
    if st.button("Send WhatsApp Invoice", use_container_width=True):
        st.info("Opening WhatsApp...")
