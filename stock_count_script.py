import streamlit as st
import pandas as pd
import openpyxl
import datetime
import os

st.set_page_config(page_title="Stock Count Tool", layout="wide")
st.title("Stock Count Web Application")

# --- File uploader ---
uploaded_files = st.file_uploader("Select one or more Excel files", type=["xlsx"], accept_multiple_files=True, help="Upload your stock Excel file(s).")

if uploaded_files:
    all_sheet_names = set()
    all_dfs = {}
    for uploaded_file in uploaded_files:
        try:
            wb = openpyxl.load_workbook(uploaded_file, data_only=True)
            sheet_names = wb.sheetnames
            all_sheet_names.update(sheet_names)
            for sheet in sheet_names:
                df = pd.read_excel(uploaded_file, sheet_name=sheet)
                all_dfs[(uploaded_file.name, sheet)] = df
        except Exception as e:
            st.error(f"Error loading {uploaded_file.name}: {e}")
    # Auto-select sheets containing 'Sold Date' column
    auto_selected_sheets = [key for key, df in all_dfs.items() if 'Sold Date' in df.columns]
    st.success(f"Auto-detected sheets with 'Sold Date': {[sheet for (_, sheet) in auto_selected_sheets]}")
    all_sheet_keys = [key for key in all_dfs.keys()]
    # Sheet selection logic with select all checkbox
    select_all_sheets = st.checkbox("Select All Sheets")
    if select_all_sheets:
        selected_sheets = all_sheet_keys
    else:
        selected_sheets = st.multiselect(
            "Select sheets to process",
            all_sheet_keys,
            default=auto_selected_sheets,
            format_func=lambda x: f"{x[0]} - {x[1]}"
        )
    # Auto-select columns D-G if present, else all columns
    sample_df = all_dfs[selected_sheets[0]] if selected_sheets else None
    if sample_df is not None:
        all_columns = list(sample_df.columns)
        # Set default columns to: Product Name, Color, Sr No./ IMEI No., Move
        default_columns = [col for col in all_columns if col in ['Product Name', 'Color', 'Sr No./ IMEI No.', 'Move']]
        if not default_columns:
            default_columns = all_columns[3:7] if len(all_columns) >= 7 else all_columns
    else:
        all_columns = []
        default_columns = []
    selected_columns = st.multiselect("Select columns to extract", all_columns, default=default_columns)

    # --- Filter options ---
    filter_blanks = st.checkbox('Filter rows where "Sold Date" is blank', value=True)
    st.markdown("**Advanced Filter (optional):**")
    filter_col = st.selectbox("Column to filter", all_columns, index=all_columns.index('Sold Date') if 'Sold Date' in all_columns else 0)
    filter_val = st.text_input("Value to filter for (leave blank for no filter)")
    # Date range filter
    if "Date" in all_columns:
        st.markdown("**Date Range Filter (optional):**")
        min_date = pd.to_datetime(pd.concat([df["Date"] for df in all_dfs.values() if "Date" in df], ignore_index=True), errors='coerce').min()
        max_date = pd.to_datetime(pd.concat([df["Date"] for df in all_dfs.values() if "Date" in df], ignore_index=True), errors='coerce').max()
        date_range = st.date_input("Select date range", value=(min_date, max_date))
    else:
        date_range = None
    # --- Output location and filename ---
    output_filename = st.text_input("Output file name", f"Stock Count ({datetime.datetime.now().strftime('%Y-%m-%d')}).xlsx")
    export_format = st.selectbox("Export format", ["xlsx", "csv", "pdf"])
    # --- Data preview and processing ---
    preview_data = []
    for key in selected_sheets:
        df = all_dfs[key].copy()
        if filter_blanks and "Sold Date" in df.columns:
            df = df[df["Sold Date"].isna() | (df["Sold Date"] == "")]
        if filter_val and filter_col in df.columns:
            df = df[df[filter_col].astype(str) == filter_val]
        if date_range and "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors='coerce')
            df = df[(df["Date"] >= pd.to_datetime(date_range[0])) & (df["Date"] <= pd.to_datetime(date_range[1]))]
        df = df[selected_columns]
        df["Sheet"] = key[1]
        df["File"] = key[0]
        preview_data.append(df)
    if preview_data:
        result_df = pd.concat(preview_data, ignore_index=True)
        st.write(f"Total rows: {len(result_df)}")
        # --- Row editing before export ---
        st.markdown("---")
        st.subheader("Edit Data Before Export")
        edited_df = st.data_editor(result_df, num_rows="dynamic", use_container_width=True)
        # --- Download button ---
        if export_format == "xlsx":
            with pd.ExcelWriter(output_filename, engine='openpyxl') as output:
                edited_df.to_excel(output, index=False)
            with open(output_filename, "rb") as f:
                st.download_button("Download Excel file", f, file_name=output_filename)
            os.remove(output_filename)
        elif export_format == "csv":
            csv = edited_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV file", csv, file_name=output_filename.replace('.xlsx', '.csv'))
        elif export_format == "pdf":
            st.info("PDF export coming soon! (Can be implemented with additional libraries)")
        # --- Search bar for unique data ---
        st.markdown("---")
        st.subheader("Search Extracted Data")
        search_query = st.text_input("Search for unique data (case-insensitive)")
        if search_query:
            search_results = edited_df.apply(lambda row: row.astype(str).str.contains(search_query, case=False).any(), axis=1)
            filtered_search_df = edited_df[search_results]
            st.write(f"Found {len(filtered_search_df)} matching rows:")
            st.dataframe(filtered_search_df)
        # --- Data visualization ---
        st.markdown("---")
        st.subheader("Data Visualization")
        if len(selected_columns) > 0:
            st.bar_chart(edited_df[selected_columns[0]].value_counts())
        # --- Summary statistics ---
        st.markdown("---")
        st.subheader("Summary Statistics")
        st.write(edited_df.describe(include='all'))
        st.write("Unique values per column:")
        st.write(edited_df.nunique())
        # --- Audit trail (simple log) ---
        st.markdown("---")
        st.subheader("Audit Trail")
        st.write(f"Processed on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        st.write(f"Files processed: {[key[0] for key in selected_sheets]}")
        st.write(f"Sheets processed: {[key[1] for key in selected_sheets]}")
        st.write(f"Columns extracted: {selected_columns}")
        st.write(f"Filters applied: Sold Date blank={filter_blanks}, {filter_col}={filter_val}, Date Range={date_range}")
else:
    st.info("Please upload one or more Excel files to begin.")