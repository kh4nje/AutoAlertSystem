import pandas as pd
import streamlit as st
import numpy as np
from io import BytesIO
import os

# Streamlit app title
st.title("IDSRS Disease Outbreak Detection App")
st.write("By Asad khan")
st.write("Upload the new week data. Excludes 'Other-1' and 'Other-2' diseases. Filter for top alerts (ranked by deviation, with priority diseases always included).")


# Priority disease list (customize as needed)
priority_diseases = [
    "Crimean Congo Hemorrhagic Fever (New Cases)",
    "Anthrax (New Cases)",
    "Botulism (New Cases)",
    "Diphtheria (Probable) (New Cases)",
    "Neonatal Tetanus (New Cases)",
    "Acute Flaccid Paralysis (New Cases)",
    "Visceral Leishmaniasis (New Cases)",
    "HIV/AIDS (New Cases)",
    "Dengue Fever (New Cases)"
]

# Upload new week file
new_file = st.file_uploader("Upload new week data (Excel or CSV, e.g., week 40, 2025)", type=['xlsx', 'csv'])

# Priority disease selector
selected_priority_diseases = st.multiselect(
    "Select priority diseases to always include in alerts (even low numbers):",
    options=priority_diseases,
    default=priority_diseases  # Default to all priority diseases
)

# Load or initialize threshold file
threshold_file_path = 'threshold.csv'
threshold_df = None
if os.path.exists(threshold_file_path):
    encodings = ['utf-8', 'latin1', 'iso-8859-1', 'cp1252']
    for encoding in encodings:
        try:
            threshold_df = pd.read_csv(threshold_file_path, encoding=encoding)
            st.write("Threshold file loaded from local 'threshold.csv'.")
            break
        except UnicodeDecodeError:
            st.write(f"Failed to read threshold file with {encoding} encoding. Trying next...")
    if threshold_df is None:
        st.error("Unable to read local threshold file. Please delete 'threshold.csv' and re-upload initial data.")
        st.stop()
else:
    initial_threshold_file = st.file_uploader("Upload initial threshold file (CSV from historical computation) to create 'threshold.csv'", type=['csv'])
    if initial_threshold_file is not None:
        encodings = ['utf-8', 'latin1', 'iso-8859-1', 'cp1252']
        for encoding in encodings:
            try:
                threshold_df = pd.read_csv(initial_threshold_file, encoding=encoding)
                st.write("Initial threshold file loaded and saved as 'threshold.csv'.")
                # Save to local file
                with open(threshold_file_path, 'w', encoding='utf-8') as f:
                    threshold_df.to_csv(f, index=False)
                break
            except UnicodeDecodeError:
                st.write(f"Failed to read initial threshold file with {encoding} encoding. Trying next...")
        if threshold_df is None:
            st.error("Unable to read initial threshold file.")
            st.stop()
    else:
        st.info("No threshold file found. Please upload the initial historical threshold CSV to get started.")
        st.stop()

if threshold_df is not None and new_file is not None:
    # Extract current threshold for alerts
    current_thresholds = threshold_df[['orgunitlevel1', 'orgunitlevel2', 'orgunitlevel3', 'orgunitlevel4', 'orgunitlevel5', 'orgunitlevel6', 'Facility_Name', 'Disease_Name', 'Historical_Threshold']].copy()
    last_updated_week = threshold_df['Last_Updated_Week'].iloc[0] if 'Last_Updated_Week' in threshold_df.columns else 0
    historical_weeks_count = threshold_df['Historical_Weeks_Count'].iloc[0] if 'Historical_Weeks_Count' in threshold_df.columns else 0
    st.write(f"Using thresholds from {historical_weeks_count} historical weeks, last updated week {last_updated_week}.")

    # Step 2: Load new week data
    if new_file.name.endswith('.xlsx'):
        new_df = pd.read_excel(new_file)
        new_df.columns = new_df.columns.str.strip()
        new_df['Epi Week Number'] = new_df['periodname'].str.extract(r'Week (\d+)', expand=False).astype(int)
        id_cols = ['periodname', 'orgunitlevel1', 'orgunitlevel2', 'orgunitlevel3', 'orgunitlevel4', 'orgunitlevel5', 'orgunitlevel6', 'organisationunitname', 'Epi Week Number']
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
            percentage_deviation = round((deviation / row['Historical_Threshold']) * 100, 2) if row['Historical_Threshold'] > 0 else 0
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
                'Percentage_Deviation': percentage_deviation,
                'Priority_Disease': 'Yes' if is_priority else 'No'
            })

    # Step 4: Filter and rank alerts for top results
    if alerts_list:
        alerts_df = pd.DataFrame(alerts_list)
        alerts_df = alerts_df.sort_values(by='Deviation', ascending=False)  # Rank by deviation descending

        # Separate priority alerts (always include)
        priority_alerts = alerts_df[alerts_df['Priority_Disease'] == 'Yes']
        non_priority_alerts = alerts_df[alerts_df['Priority_Disease'] == 'No']

        # Debug info for priority alerts
        st.write("**Debug Info:**")
        st.write(f"Total raw alerts: {len(alerts_df)}")
        st.write(f"Priority alerts found: {len(priority_alerts)}")
        if len(priority_alerts) == 0:
            st.warning("No priority disease alerts detected. Check if selected priority diseases have deviations > 0 in the data, or if names match exactly.")
            st.write("Selected priority diseases:", selected_priority_diseases)
        else:
            st.success(f"Priority alerts: {len(priority_alerts)} (all included)")

        # User controls for filtering non-priority alerts (removed default limit of 50, now optional with higher default)
        col1, col2 = st.columns(2)
        with col1:
            top_n = st.slider("Top N Non-Priority Alerts (0 for all)", min_value=0, max_value=len(non_priority_alerts), value=0)  # Default to 0 (show all)
        with col2:
            min_deviation = st.slider("Min Deviation for Non-Priority", min_value=0.0, max_value=non_priority_alerts['Deviation'].max() if len(non_priority_alerts) > 0 else 1.0, value=0.0, step=0.5)  # Default min 0.0 to show all above threshold

        # Apply filters to non-priority
        filtered_non_priority = non_priority_alerts[(non_priority_alerts['Deviation'] >= min_deviation)]
        if top_n > 0:
            filtered_non_priority = filtered_non_priority.head(top_n)

        # Combine: All priority + filtered non-priority
        filtered_alerts = pd.concat([priority_alerts, filtered_non_priority], ignore_index=True)
        if len(filtered_alerts) > 0:
            filtered_alerts = filtered_alerts.sort_values(by='Deviation', ascending=False)
        st.write(f"Showing: {len(priority_alerts)} priority + {len(filtered_non_priority)} filtered non-priority = {len(filtered_alerts)} total alerts.")

        # Display preview
        st.dataframe(filtered_alerts)  # Show all filtered alerts

        # Generate filtered alerts Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            filtered_alerts.to_excel(writer, index=False, sheet_name='Filtered Alerts')
        output.seek(0)
        st.download_button(
            label=f"Download All Filtered Alerts for Week {new_week} as Excel",
            data=output,
            file_name=f'alerts_week_{new_week}_filtered.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        st.success(f"Filtered alerts ready for download ({len(filtered_alerts)} rows).")

        # Top 4 alerts per disease
        top_per_disease = []
        for disease in alerts_df['Disease'].unique():
            disease_alerts = alerts_df[alerts_df['Disease'] == disease].head(4)
            top_per_disease.append(disease_alerts)
        if top_per_disease:
            top_alerts_df = pd.concat(top_per_disease, ignore_index=True)
            top_alerts_df = top_alerts_df.sort_values(by=['Disease', 'Deviation'], ascending=[True, False])
            output_top = BytesIO()
            with pd.ExcelWriter(output_top, engine='openpyxl') as writer:
                top_alerts_df.to_excel(writer, index=False, sheet_name='Top Alerts')
            output_top.seek(0)
            st.download_button(
                label=f"Download Top 4 Alerts Per Disease for Week {new_week} as Excel",
                data=output_top,
                file_name=f'top_alerts_week_{new_week}.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            st.success(f"Top alerts per disease ready for download ({len(top_alerts_df)} rows).")
    else:
        st.warning(f"No alerts found for Week {new_week} (after excluding Other-1/Other-2). Check data for deviations > 0.")

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
            new_mean = (old_mean * old_n + new_case) / (old_n + 1)
            # Running variance (approx, using updated mean)
            old_variance = old_std ** 2
            new_variance = ((old_n - 1) * old_variance + (old_n * (old_mean - new_mean)**2 + new_case * (new_case - new_mean)**2)) / old_n
            new_std = np.sqrt(new_variance)
            new_threshold = new_mean + 3 * new_std if new_std > 0 else new_mean
            updated_threshold_df.at[idx, 'Historical_Mean'] = round(new_mean, 2)
            updated_threshold_df.at[idx, 'Historical_Std'] = round(new_std, 2)
            updated_threshold_df.at[idx, 'Historical_Threshold'] = round(new_threshold, 2)
            updated_threshold_df.at[idx, 'Historical_Weeks_Count'] += 1
            updated_threshold_df.at[idx, 'Last_Updated_Week'] = new_week

        # Save updated threshold to local file
        updated_threshold_df.to_csv(threshold_file_path, index=False, encoding='utf-8')
        st.success("Threshold file updated in place as 'threshold.csv' (no re-upload needed next time).")

        # Optional: Download as backup
        updated_threshold = BytesIO()
        updated_threshold_df.to_csv(updated_threshold, index=False, encoding='utf-8')
        updated_threshold.seek(0)
        st.download_button(
            label="Download Updated Threshold File (CSV) as Backup",
            data=updated_threshold,
            file_name='threshold_backup.csv',
            mime='text/csv'
        )
    else:
        st.info("No update needed for threshold file (duplicate week).")

# Instructions
st.sidebar.title("Instructions")
st.sidebar.write("1. On first run: Upload initial threshold CSV—it saves as 'threshold.csv' locally.")
st.sidebar.write("2. Select priority diseases (defaults to all; they will always be included if deviation > 0).")
st.sidebar.write("3. Upload new week data (Excel or CSV) each time.")
st.sidebar.write("4. Adjust sliders for non-priority alerts (set Top N to 0 and Min Deviation to 0 to show all).")
st.sidebar.write("5. Download alerts_week_{N}_filtered.xlsx for filtered results (now includes Percentage_Deviation column for sorting by relative increase).")
st.sidebar.write("6. Download top_alerts_week_{N}.xlsx for top 4 deviations per disease (also includes Percentage_Deviation).")
st.sidebar.write("7. If new week, threshold auto-updates in 'threshold.csv'—no re-upload needed!")
st.sidebar.write("Note: 'Other-1' and 'Other-2' are automatically excluded from alerts. Debug info shows priority alert counts.")

