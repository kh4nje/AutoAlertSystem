import pandas as pd
import streamlit as st
import numpy as np
from io import BytesIO

# Streamlit app title
st.title("Disease Outbreak Detection App with Threshold File")
st.write("Upload the threshold file and new week data. Excludes 'Other-1' and 'Other-2' diseases. Filter for top alerts (ranked by deviation, with priority diseases always included).")

# Priority disease list (customize as needed)
priority_diseases = [
    "Crimean Congo Hemorrhagic Fever (New Cases)",
    "Anthrax (New Cases)",
    "Botulism (New Cases)",
    "Diphtheria (Probable) (New Cases)",
    "Neonatal Tetanus (New Cases)",
    "Acute Flaccid Paralysis (New Cases)"
]

# Upload threshold file and new week file
threshold_file = st.file_uploader("Upload the threshold file (CSV from historical computation)", type=['csv'])
new_file = st.file_uploader("Upload new week data (Excel or CSV, e.g., week 40, 2025)", type=['xlsx', 'csv'])

# Priority disease selector
selected_priority_diseases = st.multiselect(
    "Select priority diseases to always include in alerts (even low numbers):",
    options=priority_diseases,
    default=priority_diseases[:2]  # Default to CCHF and Anthrax
)

if threshold_file is not None and new_file is not None:
    # Step 1: Load threshold file
    encodings = ['utf-8', 'latin1', 'iso-8859-1', 'cp1252']
    threshold_df = None
    for encoding in encodings:
        try:
            threshold_df = pd.read_csv(threshold_file, encoding=encoding)
            st.write("Threshold file loaded successfully.")
            break
        except UnicodeDecodeError:
            st.write(f"Failed to read threshold file with {encoding} encoding. Trying next...")
    if threshold_df is None:
        st.error("Unable to read threshold file.")
        st.stop()

    # Extract current threshold for alerts
    current_thresholds = threshold_df[['orgunitlevel1', 'orgunitlevel2', 'orgunitlevel3', 'orgunitlevel4', 'orgunitlevel5', 'orgunitlevel6', 'Facility_Name', 'Disease_Name', 'Historical_Threshold']].copy()
    last_updated_week = threshold_df['Last_Updated_Week'].iloc[0] if 'Last_Updated_Week' in threshold_df.columns else 0
    historical_weeks_count = threshold_df['Historical_Weeks_Count'].iloc[0] if 'Historical_Weeks_Count' in threshold_df.columns else 0
    st.write(f"Using thresholds from {historical_weeks_count} historical weeks, last updated week {last_updated_week}.")

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
        id_cols = ['periodname', 'orgunitlevel1', 'orgunitlevel2', 'orgunitlevel3', 'orgunitlevel4', 'orgunitlevel5', 'orgunitlevel6', 'organisationunitname', 'Epi Week Number'] if 'periodname' in new_df.columns else ['orgunitlevel1', 'orgunitlevel2', 'orgunitlevel3', 'orgunitlevel4', 'orgunitlevel5', 'orgunitlevel6', 'organisationunitname', 'Epi Week Number']
        disease_cols = [col for col in new_df.columns if col not in id_cols]
        long_new = pd.melt(new_df, id_vars=id_cols, value_vars=disease_cols, var_name='Disease_Name', value_name='Number_Cases')
        long_new = long_new.rename(columns={'organisationunitname': 'Facility_Name'})
        long_new = long_new[['orgunitlevel1', 'orgunitlevel2', 'orgunitlevel3', 'orgunitlevel4', 'orgunitlevel5', 'orgunitlevel6', 'Facility_Name', 'Disease_Name', 'Epi Week Number', 'Number_Cases']]
        long_new['Number_Cases'] = long_new['Number_Cases'].fillna(0).astype(int)
        long_new = long_new.sort_values(by=['Facility_Name', 'Disease_Name', 'Epi Week Number'])
        st.write("New week Excel file processed successfully.")
    else:
        encodings = ['utf-8', 'latin1', 'iso-8859-1', 'cp1252']
        long_new = None
        for encoding in encodings:
            try:
                long_new = pd.read_csv(new_file, encoding=encoding)
                st.write(f"New week CSV read with {encoding} encoding.")
                break
            except UnicodeDecodeError:
                st.write(f"Failed to read new week CSV with {encoding} encoding. Trying next...")
        if long_new is None:
            st.error("Unable to read new week CSV.")
            st.stop()
        # For CSV, assume 'Epi Week Number' column exists or prompt
        if 'Epi Week Number' not in long_new.columns:
            new_week_input = st.number_input("Enter the Epi Week Number for this data (since column is missing):", min_value=1, max_value=52, value=40)
            long_new['Epi Week Number'] = new_week_input

    # Step 3: Check new week against historical threshold
    new_week = long_new['Epi Week Number'].unique()[0]  # Assume single week
    if new_week == last_updated_week:
        st.warning(f"New week {new_week} matches last updated week. Using existing threshold (no update).")
    else:
        st.success(f"New week {new_week} is new. Checking against historical threshold from {historical_weeks_count} weeks.")

    # Merge new data with thresholds for alert check (include org levels)
    new_with_threshold = long_new.merge(current_thresholds, on=['orgunitlevel1', 'orgunitlevel2', 'orgunitlevel3', 'orgunitlevel4', 'orgunitlevel5', 'orgunitlevel6', 'Facility_Name', 'Disease_Name'], how='left')
    alerts_list = []
    for _, row in new_with_threshold.iterrows():
        disease_name = row['Disease_Name']
        # Skip non-specific diseases
        if 'Other-1' in disease_name or 'Other-2' in disease_name:
            continue
        if pd.isna(row['Historical_Threshold']):
            continue  # Skip if no historical threshold (new facility-disease)
        deviation = row['Number_Cases'] - row['Historical_Threshold']
        if deviation > 0:
            is_priority = disease_name in selected_priority_diseases
            alerts_list.append({
                'orgunitlevel1': row['orgunitlevel1'],
                'orgunitlevel2': row['orgunitlevel2'],
                'orgunitlevel3': row['orgunitlevel3'],
                'orgunitlevel4': row['orgunitlevel4'],
                'orgunitlevel5': row['orgunitlevel5'],
                'orgunitlevel6': row['orgunitlevel6'],
                'Facility': row['Facility_Name'],
                'Disease': disease_name,
                'New_Week_Cases': row['Number_Cases'],
                'Historical_Threshold': row['Historical_Threshold'],
                'Deviation': round(deviation, 2),
                'Priority_Disease': 'Yes' if is_priority else 'No'
            })

    # Step 4: Filter and rank alerts for top results
    if alerts_list:
        alerts_df = pd.DataFrame(alerts_list)
        alerts_df = alerts_df.sort_values(by='Deviation', ascending=False)  # Rank by deviation descending

        # Separate priority alerts (always include)
        priority_alerts = alerts_df[alerts_df['Priority_Disease'] == 'Yes']
        non_priority_alerts = alerts_df[alerts_df['Priority_Disease'] == 'No']

        # User controls for filtering non-priority alerts
        col1, col2 = st.columns(2)
        with col1:
            top_n = st.slider("Top N Non-Priority Alerts", min_value=0, max_value=len(non_priority_alerts), value=min(50, len(non_priority_alerts)))  # Default to 50
        with col2:
            min_deviation = st.slider("Min Deviation for Non-Priority", min_value=0.0, max_value=non_priority_alerts['Deviation'].max() if len(non_priority_alerts) > 0 else 1.0, value=2.0, step=0.5)  # Default min 2.0

        # Apply filters to non-priority
        filtered_non_priority = non_priority_alerts[(non_priority_alerts['Deviation'] >= min_deviation)].head(top_n)

        # Combine: All priority + filtered non-priority
        filtered_alerts = pd.concat([priority_alerts, filtered_non_priority], ignore_index=True)
        if len(filtered_alerts) > 0:
            filtered_alerts = filtered_alerts.sort_values(by='Deviation', ascending=False)
        st.write(f"Total raw alerts (after excluding Other-1/Other-2): {len(alerts_df)}. Showing: {len(priority_alerts)} priority + {len(filtered_non_priority)} filtered non-priority = {len(filtered_alerts)}.")

        # Display preview
        st.dataframe(filtered_alerts.head(10))  # Show first 10 for preview

        # Generate filtered alerts Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            filtered_alerts.to_excel(writer, index=False, sheet_name='Top Alerts')
        output.seek(0)
        st.download_button(
            label=f"Download Top Alerts for Week {new_week} as Excel",
            data=output,
            file_name=f'alerts_week_{new_week}_top.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        st.success(f"Top {len(filtered_alerts)} alerts ready for download.")
    else:
        st.warning("No alerts found for Week {new_week} (after excluding Other-1/Other-2).")

    # Step 5: Update threshold file if new week
    if new_week != last_updated_week:
        # Recalculate threshold using historical stats + new week (running formulas)
        updated_threshold_df = threshold_df.copy()
        for idx, row in updated_threshold_df.iterrows():
            facility = row['Facility_Name']
            disease = row['Disease_Name']
            new_case = long_new[(long_new['Facility_Name'] == facility) & (long_new['Disease_Name'] == disease)]['Number_Cases'].values
            if len(new_case) == 0:
                continue
            new_case = new_case[0]
            old_n = row['Historical_Weeks_Count']
            old_mean = row['Historical_Mean']
            old_std = row['Historical_Std']
            # Running mean
            new_mean = (old_mean * old_n + new_case)
