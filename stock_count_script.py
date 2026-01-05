# stock_count_script_v3_2.py
import streamlit as st
import pandas as pd
import numpy as np
import openpyxl
import datetime
import io
import warnings
import re

warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="Stock Count & Audit System",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS (same as before) ---
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; color: #1f77b4; text-align: center; margin-bottom: 1rem; }
    .stock-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; margin: 5px 0; }
    .unsold-card { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 15px; border-radius: 10px; margin: 5px 0; }
    .sold-card { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 15px; border-radius: 10px; margin: 5px 0; }
    .metric-card { background-color: #f8f9fa; border-radius: 10px; padding: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin: 5px; }
</style>
""", unsafe_allow_html=True)

# --- Utilities & Analyzer (robust sold engine & helpers) ---
class StockAnalyzer:
    COLUMN_MAPPING = {
        'Date': ['Date', 'Purchase Date', 'Entry Date'],
        'Vendor Name': ['Vendor Name', 'Supplier', 'Vendor'],
        'Price': ['Price', 'Cost Price', 'Purchase Price', 'Cost'],
        'Product Name': ['Product Name', 'Product', 'Item', 'Description'],
        'Color': ['Color', 'Colour', 'Variant'],
        'Sr No./ IMEI No.': ['Sr No./ IMEI No.', 'IMEI', 'Serial Number', 'Serial No', 'SN', 'IMEI No.'],
        'Move': ['Move', 'Location', 'Warehouse', 'Store', 'Branch'],
        'Sold Date': ['Sold Date', 'Sale Date', 'Transaction Date'],
        'Sold Price': ['Sold Price', 'Sale Price', 'Revenue', 'Selling Price'],
        'Invoice No.': ['Invoice No.', 'Invoice Number', 'Invoice'],
        'Customer Name': ['Customer Name', 'Customer', 'Client'],
        'Payment Method': ['Payment Method', 'Payment', 'Mode of Payment'],
        'Stock Method': ['Stock Method', 'Stock Type', 'Inventory Type'],
        'Comments': ['Comments', 'Remarks', 'Notes'],
        'RB Process': ['RB Process', 'Return Process', 'RB']
    }

    @staticmethod
    def _exact_then_word_boundary_match(df_cols):
        mapping = {}
        # exact
        for std_name, possible in StockAnalyzer.COLUMN_MAPPING.items():
            for p in possible:
                for col in df_cols:
                    if col.strip().lower() == p.strip().lower():
                        mapping[col] = std_name
                        break
                if std_name in mapping.values():
                    break
        # word-boundary fuzzy
        for std_name, possible in StockAnalyzer.COLUMN_MAPPING.items():
            if any(v == std_name for v in mapping.values()):
                continue
            for p in possible:
                pat = r'\b' + re.escape(p.strip().lower()) + r'\b'
                for col in df_cols:
                    if col in mapping:
                        continue
                    if re.search(pat, col.lower()):
                        mapping[col] = std_name
                        break
                if std_name in mapping.values():
                    break
        return mapping

    @staticmethod
    def standardize_columns(df):
        col_map = StockAnalyzer._exact_then_word_boundary_match(list(df.columns))
        if col_map:
            df = df.rename(columns=col_map)
        return df

    @staticmethod
    def determine_status(row):
        # robust sold detection: sell if sold date present OR sold price present OR invoice present
        if pd.notna(row.get('Sold Date')) and str(row.get('Sold Date')).strip() != '':
            return 'Sold'
        if pd.notna(row.get('Sold Price')) and str(row.get('Sold Price')).strip() != '':
            return 'Sold'
        if pd.notna(row.get('Invoice No.')) and str(row.get('Invoice No.')).strip() != '':
            return 'Sold'
        return 'Unsold'

    @staticmethod
    def extract_stock_data(df):
        df = StockAnalyzer.standardize_columns(df)
        df.columns = [c.strip() for c in df.columns]

        # numeric conversions
        if 'Price' in df.columns:
            df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
        if 'Sold Price' in df.columns:
            df['Sold Price'] = pd.to_numeric(df['Sold Price'], errors='coerce')

        # determine status
        if 'Status' not in df.columns:
            df['Status'] = df.apply(StockAnalyzer.determine_status, axis=1)

        # profit
        if 'Price' in df.columns and 'Sold Price' in df.columns:
            df['Profit'] = df['Sold Price'] - df['Price']

        # date parsing
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        if 'Sold Date' in df.columns:
            df['Sold Date'] = pd.to_datetime(df['Sold Date'], errors='coerce')

        now = pd.to_datetime(datetime.datetime.now())
        if 'Date' in df.columns:
            if 'Sold Date' in df.columns:
                df['Days in Stock'] = (df['Sold Date'] - df['Date']).dt.days
            else:
                df['Days in Stock'] = np.nan
            mask_unsold = df['Status'] == 'Unsold'
            df.loc[mask_unsold, 'Days in Stock'] = (now - df.loc[mask_unsold, 'Date']).dt.days
            df.loc[df['Days in Stock'] < 0, 'Days in Stock'] = np.nan

        return df

    @staticmethod
    def generate_stock_report(df):
        if df is None or df.empty:
            return {}
        report = {}
        report['total_items'] = len(df)
        report['sold_count'] = int((df['Status'] == 'Sold').sum()) if 'Status' in df.columns else 0
        report['unsold_count'] = int((df['Status'] == 'Unsold').sum()) if 'Status' in df.columns else 0

        if 'Product Name' in df.columns:
            product_summary = df.groupby('Product Name').agg({
                'Status': lambda x: (x == 'Unsold').sum(),
                'Price': 'first'
            }).reset_index()
            product_summary.columns = ['Product Name', 'Unsold Count', 'Price']
            report['by_product'] = product_summary

            unsold_df = df[df['Status'] == 'Unsold']
            if 'Price' in unsold_df.columns:
                stock_value = (unsold_df.assign(Price=pd.to_numeric(unsold_df['Price'], errors='coerce'))
                               .groupby('Product Name')['Price'].sum()
                               .reset_index(name='Stock Value'))
                report['stock_value'] = stock_value

        if 'Move' in df.columns:
            move_summary = df.groupby('Move').agg({'Status': lambda x: (x == 'Unsold').sum()}).reset_index()
            move_summary.columns = ['Location', 'Unsold Count']
            report['by_location'] = move_summary

        if 'Days in Stock' in df.columns:
            aging_bins = [0, 30, 90, 180, 365, float('inf')]
            aging_labels = ['<30 days', '30-90 days', '90-180 days', '180-365 days', '>1 year']
            df['_days_temp'] = pd.to_numeric(df['Days in Stock'], errors='coerce')
            df['Aging Category'] = pd.cut(df['_days_temp'], bins=aging_bins, labels=aging_labels, right=False)
            aging_summary = df[df['Status'] == 'Unsold'].groupby('Aging Category').size().reset_index(name='Count')
            report['aging_analysis'] = aging_summary
            df.drop(columns=['_days_temp'], inplace=True, errors='ignore')

        if 'Profit' in df.columns:
            profit_summary = (df[df['Status'] == 'Sold']
                              .groupby('Product Name')['Profit']
                              .agg(['sum', 'mean', 'count']).round(2))
            report['profit_analysis'] = profit_summary

        return report

def sanitize_sheet_name(name: str) -> str:
    invalid = r'[:\\/?*\[\]]'
    s = re.sub(invalid, '_', str(name))
    return s[:31]

@st.cache_data
def process_uploaded_files(uploaded_files):
    all_data = []
    file_info = []
    duplicates_removed = 0

    for uploaded_file in uploaded_files:
        try:
            xls = pd.ExcelFile(uploaded_file)
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
                df['Source_File'] = uploaded_file.name
                df['Source_Sheet'] = sheet_name
                df['Processed_Date'] = datetime.datetime.now()
                df = StockAnalyzer.extract_stock_data(df)
                all_data.append(df)
                file_info.append({
                    'File': uploaded_file.name,
                    'Sheet': sheet_name,
                    'Rows': len(df),
                    'Sold': int((df['Status'] == 'Sold').sum()) if 'Status' in df.columns else 0,
                    'Unsold': int((df['Status'] == 'Unsold').sum()) if 'Status' in df.columns else 0
                })
        except Exception as e:
            st.error(f"Error processing {uploaded_file.name}: {e}")

    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        if 'Sr No./ IMEI No.' in combined_df.columns:
            before = len(combined_df)
            combined_df = combined_df.drop_duplicates(subset=['Sr No./ IMEI No.'], keep='last')
            duplicates_removed = before - len(combined_df)
    else:
        combined_df = pd.DataFrame()

    return combined_df, file_info, duplicates_removed

# --- Session State init ---
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'original_data' not in st.session_state:
    st.session_state.original_data = None
if 'stock_report' not in st.session_state:
    st.session_state.stock_report = None

# --- UI ---
st.markdown('<h1 class="main-header">📱 Mobile & Electronics Stock Count System</h1>', unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Configuration")
    st.subheader("📁 Upload Stock Data")
    uploaded_files = st.file_uploader("Upload your Excel stock files", type=["xlsx", "xls"], accept_multiple_files=True, help="Upload files with transaction data (like Dummy Data.xlsx)")

    st.markdown("----")
    st.info("After upload, use the '🧾 Sold Report' tab to build the sold-items report (Last 3 months or custom range).")

# --- Main logic ---
if uploaded_files:
    combined_df, file_info, duplicates_removed = process_uploaded_files(uploaded_files)

    if combined_df.empty:
        st.warning("No data found in uploaded files.")
    else:
        st.session_state.original_data = combined_df.copy()
        st.subheader("📋 File Processing Summary")
        st.dataframe(pd.DataFrame(file_info), use_container_width=True)
        if duplicates_removed > 0:
            st.warning(f"Deduplicated {duplicates_removed} duplicate IMEI rows (kept last occurrence).")

        # default filters from earlier
        show_unsold_only = st.checkbox("Show only unsold items (main view)", value=True)
        filtered_df = combined_df.copy()
        if show_unsold_only and 'Status' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['Status'] == 'Unsold']

        # Keep processed_data in session for other tabs
        st.session_state.processed_data = filtered_df.copy()
        st.session_state.stock_report = StockAnalyzer.generate_stock_report(filtered_df)

        # KPI cards (same as before)
        st.markdown("---")
        st.subheader("📊 Stock Overview")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="stock-card">Total Items<br><h2>{len(filtered_df):,}</h2></div>', unsafe_allow_html=True)
        with c2:
            unsold_count = int((filtered_df['Status'] == 'Unsold').sum()) if 'Status' in filtered_df.columns else 0
            st.markdown(f'<div class="unsold-card">Unsold Items<br><h2>{unsold_count:,}</h2></div>', unsafe_allow_html=True)
        with c3:
            if 'Price' in filtered_df.columns and 'Status' in filtered_df.columns:
                unsold_value = filtered_df.loc[filtered_df['Status'] == 'Unsold', 'Price'].apply(pd.to_numeric, errors='coerce').sum()
                st.markdown(f'<div class="metric-card">Stock Value<br><h2>{unsold_value:,.0f}</h2></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="metric-card">Stock Value<br><h2>N/A</h2></div>', unsafe_allow_html=True)
        with c4:
            unique_products = int(filtered_df['Product Name'].nunique()) if 'Product Name' in filtered_df.columns else 0
            st.markdown(f'<div class="metric-card">Unique Products<br><h2>{unique_products}</h2></div>', unsafe_allow_html=True)

        # Tabs: keep previous ones and add Sold Report
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📱 Stock Details", "📈 Analysis", "📍 Location View", "💾 Export", "🧾 Sold Report"])

        # --- Existing tabs omitted for brevity (they remain same as v3.1) ---
        with tab1:
            st.subheader("📱 Current Stock Details")
            # display same as earlier - simplified for brevity
            display_columns = ['Product Name', 'Color', 'Sr No./ IMEI No.', 'Move']
            available_columns = [c for c in display_columns if c in filtered_df.columns]
            if 'Date' in filtered_df.columns:
                available_columns.append('Date')
            if 'Price' in filtered_df.columns:
                available_columns.append('Price')
            if 'Days in Stock' in filtered_df.columns:
                available_columns.append('Days in Stock')
            if 'Source_Sheet' in filtered_df.columns:
                available_columns.append('Source_Sheet')

            display_df = filtered_df[available_columns].copy()
            if 'Days in Stock' in display_df.columns:
                display_df['Days in Stock'] = pd.to_numeric(display_df['Days in Stock'], errors='coerce').astype('Int64')
            st.dataframe(display_df, use_container_width=True, height=350)

        with tab2:
            st.subheader("📈 Stock Analysis (summary)")
            if st.session_state.stock_report and 'by_product' in st.session_state.stock_report:
                st.dataframe(st.session_state.stock_report['by_product'], use_container_width=True)

        with tab3:
            st.subheader("📍 Stock by Location")
            if 'by_location' in st.session_state.stock_report:
                st.dataframe(st.session_state.stock_report['by_location'], use_container_width=True)

        with tab4:
            st.subheader("💾 Export Reports")
            # simplified export options here (same as earlier)...
            st.write("Use the Sold Report tab for sold-specific exports.")

        # --- NEW: Sold Report tab implementation ---
        with tab5:
            st.header("🧾 Sold Items Report")
            sold_df_raw = combined_df[combined_df['Status'] == 'Sold'] if 'Status' in combined_df.columns else pd.DataFrame()
            st.markdown("**Filter sold items by date and select columns to include in exported report.**")

            if sold_df_raw.empty:
                st.info("No rows detected as Sold in the uploaded files (based on Sold Date / Sold Price / Invoice No.)")
            else:
                # show counts & missing sold date stats
                total_sold = len(sold_df_raw)
                sold_with_date = sold_df_raw['Sold Date'].notna().sum() if 'Sold Date' in sold_df_raw.columns else 0
                st.subheader(f"Sold records detected: {total_sold:,}")
                st.caption(f"Records with Sold Date: {sold_with_date:,} — records without Sold Date will be excluded by date filters unless you opt to include them.")

                # Date filter modes
                df_has_sold_date = 'Sold Date' in sold_df_raw.columns and sold_df_raw['Sold Date'].notna().any()
                filter_mode = st.radio("Sold date filter mode:", ["All sold items", "Last N months (default 3)", "Custom date range", "Select specific Year-Months"], index=1)

                sold_filtered = sold_df_raw.copy()

                if filter_mode == "Last N months (default 3)":
                    n_months = st.number_input("Last how many months?", min_value=1, max_value=24, value=3)
                    cutoff = pd.Timestamp.now() - pd.DateOffset(months=int(n_months))
                    if df_has_sold_date:
                        sold_filtered = sold_filtered[sold_filtered['Sold Date'] >= cutoff]
                    else:
                        st.warning("No Sold Date data present — 'Last N months' filter cannot be applied; showing all sold items instead.")

                elif filter_mode == "Custom date range":
                    col1, col2 = st.columns(2)
                    with col1:
                        start = st.date_input("Start date", value=(pd.Timestamp.now() - pd.DateOffset(months=3)).date())
                    with col2:
                        end = st.date_input("End date", value=pd.Timestamp.now().date())
                    if df_has_sold_date:
                        sold_filtered = sold_filtered[(sold_filtered['Sold Date'] >= pd.Timestamp(start)) & (sold_filtered['Sold Date'] <= pd.Timestamp(end))]
                    else:
                        st.warning("No Sold Date data present — custom range filtering not possible.")

                else:  # Select specific Year-Months
                    if df_has_sold_date:
                        sold_filtered['YM'] = sold_filtered['Sold Date'].dt.to_period('M').astype(str)
                        available_months = sorted(sold_filtered['YM'].unique(), reverse=True)
                        chosen_months = st.multiselect("Choose Year-Months", options=available_months, default=available_months[:3])
                        if chosen_months:
                            sold_filtered = sold_filtered[sold_filtered['Sold Date'].dt.to_period('M').astype(str).isin(chosen_months)]
                        sold_filtered.drop(columns=['YM'], inplace=True, errors='ignore')
                    else:
                        st.warning("No Sold Date data present — cannot select months.")

                # Option: include sold rows that lack Sold Date
                include_missing_dates = st.checkbox("Also include sold rows missing Sold Date", value=False)
                if include_missing_dates:
                    missing_date_rows = sold_df_raw[sold_df_raw['Sold Date'].isna()] if 'Sold Date' in sold_df_raw.columns else pd.DataFrame()
                    if not missing_date_rows.empty:
                        # Append missing-date sold rows to filtered set (if not already present)
                        sold_filtered = pd.concat([sold_filtered, missing_date_rows]).drop_duplicates().reset_index(drop=True)

                # Column selector UI
                # Provide the user's requested default column order:
                default_cols = ['Date','Vendor Name','Price','Product Name','Color','Sr No./ IMEI No.','Move','Sold Date','Sold Price','Invoice No.','Customer Name','Payment Method','RB Process','Comments']
                available_cols = list(sold_filtered.columns)
                # Keep the order: defaults first if present
                ordered_available = [c for c in default_cols if c in available_cols] + [c for c in available_cols if c not in default_cols]
                chosen_cols = st.multiselect("Choose columns to include in the sold report (export & preview):", options=ordered_available, default=[c for c in default_cols if c in available_cols])

                if not chosen_cols:
                    st.warning("Select at least one column to preview/export.")
                else:
                    preview_df = sold_filtered[chosen_cols].copy()
                    # Format Days in Stock if present
                    if 'Days in Stock' in preview_df.columns:
                        preview_df['Days in Stock'] = pd.to_numeric(preview_df['Days in Stock'], errors='coerce').astype('Int64')
                    st.subheader("Preview")
                    st.dataframe(preview_df, use_container_width=True, height=350)

                    # Export controls
                    exp_col1, exp_col2 = st.columns([2,1])
                    with exp_col1:
                        filename = st.text_input("Export file name", value=f"Sold_Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}")
                    with exp_col2:
                        exp_format = st.selectbox("Format", ["Excel (.xlsx)", "CSV (.csv)"])

                    # Export action
                    if st.button("📥 Download Sold Report"):
                        if exp_format == "Excel (.xlsx)":
                            out = io.BytesIO()
                            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                                preview_df.to_excel(writer, sheet_name=sanitize_sheet_name('Sold Report'), index=False)
                            out.seek(0)
                            st.download_button(label="Download Excel", data=out, file_name=f"{filename}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                        else:
                            csv_data = preview_df.to_csv(index=False)
                            st.download_button(label="Download CSV", data=csv_data, file_name=f"{filename}.csv", mime="text/csv")

                # Quick summary metrics for the sold filter
                st.markdown("---")
                st.write(f"**Filtered sold count:** {len(sold_filtered):,}")
                st.write(f"**With Sold Date:** {sold_filtered['Sold Date'].notna().sum() if 'Sold Date' in sold_filtered.columns else 0}")
                st.write(f"**Without Sold Date:** {sold_filtered['Sold Date'].isna().sum() if 'Sold Date' in sold_filtered.columns else 0}")

        # --- End Sold Report tab ---

        # Audit trail (same idea as before)
        st.markdown("---")
        st.subheader("📝 Audit Trail")
        audit_log = {
            'Processing Time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'Files Processed': [f.name for f in uploaded_files],
            'Total Records Processed': int(len(combined_df)),
            'Duplicates Removed': int(duplicates_removed),
            'Detected Sold Rows': int((combined_df['Status'] == 'Sold').sum()) if 'Status' in combined_df.columns else 0
        }
        st.json(audit_log, expanded=False)
        st.download_button(label="📋 Download Audit Log", data=pd.DataFrame([audit_log]).to_csv(index=False), file_name=f"audit_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")

else:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("""
        <div style='text-align:center;padding:40px;'>
            <h2>📱 Mobile & Electronics Inventory System</h2>
            <p style='font-size:1.2rem;color:#666;margin-bottom:30px;'>Upload Excel files and use the Sold Report tab to export sold items for specific months.</p>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")
st.caption("📱 Mobile & Electronics Stock System v3.2 • Sold Report & column selection added")
