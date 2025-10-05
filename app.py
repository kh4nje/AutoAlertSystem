import pandas as pd
import streamlit as st
import numpy as np
from io import BytesIO
import os

# Streamlit app title
st.title("Disease Outbreak Detection App with Threshold File")
st.write("Threshold file is pre-loaded if available. Upload only the new week data. All priority diseases are pre-selected. Excludes 'Other-1' and 'Other-2'.")

# Priority disease list (all pre-selected by default)
priority_diseases = [
    "Crimean Congo Hemorrhagic Fever (New Cases)",
    "Anthrax (New Cases)",
    "Botulism (New Cases)",
    "Diphtheria (Probable) (New Cases)",
    "Neonatal Tetanus (New Cases)",
    "Acute Flaccid Paralysis (New Cases)"
]

# Pre-select all priority diseases (user can deselect if needed)
selected_priority_diseases = st.multiselect(
    "Priority diseases (all pre-selected; deselect if needed):",
    options=priority_diseases,
    default=priority_diseases  # All pre-selected
)

# Upload only new week file
new_file = st.file_uploader("Upload new week data (Excel or CSV, e.g., week 40, 2025)", type=['xlsx', 'csv'])

# Pre-load threshold file (assume 'threshold_file.csv' in app directory; fallback upload if not found)
threshold_path = 'threshold_file.csv'
if os.path.exists(threshold_path):
    threshold_df = pd.read_csv(threshold_path)
    st.success("Threshold file pre-loaded successfully from 'threshold_file.csv'.")
else:
    threshold_file_upload = st.file_uploader("Threshold file not found. Upload as fallback:", type=['csv'])
    if threshold_file_upload is not None:
        encodings = ['utf-8', 'latin1', 'iso-8859-1', 'cp1252']
        for encoding in encodings:
            try:
                threshold_df = pd.read_csv(threshold_file_upload, encoding=encoding)
                st.write("Threshold file loaded from upload.")
                break
            except UnicodeDecodeError:
                continue
        if 'threshold_df' not in locals():
            st.error("Unable to read threshold file.")
            st.stop()
    else:
        st.error("Threshold file 'threshold_file.csv' not found. Place it in the app directory or upload as fallback.")
        st.stop()

# Handle missing columns in threshold_df (fill with 'Unknown' if absent)
required_cols = ['Facility_Name', 'Disease_Name', 'Historical_Threshold']
missing_cols = [col for col in required_cols if col not in threshold_df.columns]
if missing_cols:
    st.error(f"Missing required columns in threshold file: {missing_cols}. Please re-generate the threshold file.")
    st.stop()

# Add org levels if missing (fill with 'Unknown')
org_levels = ['orgunitlevel1', 'orgunitlevel2', 'orgunitlevel3', 'orgunitlevel4', 'orgunitlevel5', 'orgunitlevel6']
for level in org_levels:
    if level not in threshold_df.columns:
        threshold_df[level] = 'Unknown'
        st.warning(f"Column '{level}' missing in threshold file; filled with 'Unknown'.")

# Extract current threshold for alerts
current_thresholds = threshold_df[org_levels + ['Facility_Name', 'Disease_Name', 'Historical_Threshold']].copy()
last_updated_week = threshold_df['Last_Updated_Week'].iloc[0] if 'Last_Updated_Week' in threshold_df.columns else 0
historical_weeks_count = threshold_df['Historical_Weeks_Count'].iloc[0] if 'Historical_Weeks_Count' in threshold_df.columns else 0
st.write(f"Using thresholds from {historical_weeks_count} historical weeks, last updated week {last_updated_week}.")

if new_file is not None:
    # Step 2: Load new week data
    if new_file.name.endswith('.xlsx'):
        new_df = pd.read_excel(new_file)
        new_df.columns = new_df.columns.str.strip()
        # Check if 'periodname' exists; if not, prompt for week number
        if 'periodname' in new_df.columns:
            new_df['Epi Week Number'] = new_df['periodname'].str.extract(r'Week (\d+)', expand=False).astype(int)
        else:
            new_week_input = st.number_input("Enter the Epi Week Number for this data (since 'periodname' column is missing):", min_value=1, max_value=52, value=40)
            new_df['Epi Week Number'] = new_week_input
            st.info("No 'periodname' column found; using user-input week number.")
        # Dynamically build id_cols based on available columns
        possible_id_cols = ['orgunitlevel1', 'orgunitlevel2', 'orgunitlevel3', 'orgunitlevel4', 'orgunitlevel5', 'orgunitlevel6', 'organisationunitname', 'Epi Week Number']
        id_cols = [col for col in possible_id_cols if col in new_df.columns]
        if 'organisationunitname' in new_df.columns:
            new_df = new_df
