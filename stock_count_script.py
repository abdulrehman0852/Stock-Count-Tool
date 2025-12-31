import streamlit as st
import pandas as pd
import numpy as np
import openpyxl
import datetime
import io
import warnings
warnings.filterwarnings('ignore')

# Page configuration
st.set_page_config(
    page_title="Stock Count & Audit System",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional look
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .stock-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px;
        border-radius: 10px;
        margin: 5px 0;
    }
    .unsold-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 15px;
        border-radius: 10px;
        margin: 5px 0;
    }
    .sold-card {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        color: white;
        padding: 15px;
        border-radius: 10px;
        margin: 5px 0;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        margin: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'original_data' not in st.session_state:
    st.session_state.original_data = None
if 'stock_report' not in st.session_state:
    st.session_state.stock_report = None

class StockAnalyzer:
    """Custom analyzer for your stock data structure"""
    
    # Your specific column names from the dummy data
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
    def standardize_columns(df):
        """Standardize column names based on your data"""
        column_mapping = {}
        for standardized_name, possible_names in StockAnalyzer.COLUMN_MAPPING.items():
            for col in df.columns:
                if any(name.lower() in col.lower() for name in possible_names):
                    column_mapping[col] = standardized_name
                    break
        
        if column_mapping:
            df = df.rename(columns=column_mapping)
        return df
    
    @staticmethod
    def extract_stock_data(df):
        """Extract stock information from your data"""
        # Ensure we have the standardized columns
        df = StockAnalyzer.standardize_columns(df)
        
        # Identify sold vs unsold
        df['Status'] = 'Unsold'
        if 'Sold Date' in df.columns:
            df.loc[df['Sold Date'].notna() & (df['Sold Date'] != ''), 'Status'] = 'Sold'
        
        # Calculate profit if both prices exist
        if 'Price' in df.columns and 'Sold Price' in df.columns:
            df['Profit'] = pd.to_numeric(df['Sold Price'], errors='coerce') - pd.to_numeric(df['Price'], errors='coerce')
        
        # Calculate days in stock
        if 'Date' in df.columns and 'Sold Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['Sold Date'] = pd.to_datetime(df['Sold Date'], errors='coerce')
            df['Days in Stock'] = (df['Sold Date'] - df['Date']).dt.days
            # For unsold items
            df.loc[df['Status'] == 'Unsold', 'Days in Stock'] = (datetime.datetime.now() - df['Date']).dt.days
        
        return df
    
    @staticmethod
    def generate_stock_report(df):
        """Generate comprehensive stock report"""
        if df is None or df.empty:
            return None
        
        report = {}
        
        # Basic counts
        report['total_items'] = len(df)
        report['sold_count'] = len(df[df['Status'] == 'Sold'])
        report['unsold_count'] = len(df[df['Status'] == 'Unsold'])
        
        # By product
        if 'Product Name' in df.columns:
            product_summary = df.groupby('Product Name').agg({
                'Status': lambda x: (x == 'Unsold').sum(),
                'Price': 'first'
            }).reset_index()
            product_summary.columns = ['Product Name', 'Unsold Count', 'Price']
            report['by_product'] = product_summary
            
            # Stock value by product (only unsold)
            unsold_df = df[df['Status'] == 'Unsold']
            if 'Price' in unsold_df.columns:
                stock_value = unsold_df.groupby('Product Name').apply(
                    lambda x: (pd.to_numeric(x['Price'], errors='coerce').sum())
                ).reset_index(name='Stock Value')
                report['stock_value'] = stock_value
        
        # By location (Move)
        if 'Move' in df.columns:
            move_summary = df.groupby('Move').agg({
                'Status': lambda x: (x == 'Unsold').sum()
            }).reset_index()
            move_summary.columns = ['Location', 'Unsold Count']
            report['by_location'] = move_summary
        
        # Aging analysis
        if 'Days in Stock' in df.columns:
            aging_bins = [0, 30, 90, 180, 365, float('inf')]
            aging_labels = ['<30 days', '30-90 days', '90-180 days', '180-365 days', '>1 year']
            df['Aging Category'] = pd.cut(df['Days in Stock'], bins=aging_bins, labels=aging_labels, right=False)
            aging_summary = df[df['Status'] == 'Unsold'].groupby('Aging Category').size().reset_index(name='Count')
            report['aging_analysis'] = aging_summary
        
        # Profit analysis
        if 'Profit' in df.columns:
            profit_summary = df[df['Status'] == 'Sold'].groupby('Product Name').agg({
                'Profit': ['sum', 'mean', 'count']
            }).round(2)
            report['profit_analysis'] = profit_summary
        
        return report

# Main App UI
st.markdown('<h1 class="main-header">📱 Mobile & Electronics Stock Count System</h1>', unsafe_allow_html=True)

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # File upload
    st.subheader("📁 Upload Stock Data")
    uploaded_files = st.file_uploader(
        "Upload your Excel stock files",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        help="Upload files with transaction data (like Dummy Data.xlsx)"
    )
    
    # Processing options
    st.subheader("🔄 Processing Options")
    process_mode = st.radio(
        "Select processing mode:",
        ["Generate Stock Report (Unsold Items)", "Full Transaction Analysis", "Compare with Previous Stock"]
    )
    
    # Filter options
    st.subheader("🔍 Filter Options")
    
    # Auto-detect unsold items (your primary use case)
    show_unsold_only = st.checkbox("Show only unsold items", value=True, 
                                   help="This is your main workflow - show what's in stock")
    
    # Location filter
    location_filter = st.multiselect(
        "Filter by location (Move)",
        ["All", "HCL", "EMP", "DHA H", "DHA 6", "ISB", "VAL", "DLM", "DHA R", "SKT", "FSB"]
    )
    
    # Product category filter
    product_categories = st.multiselect(
        "Filter by product type",
        ["All", "Mi TV Stick", "Redmi", "Note Series", "JBL", "Other Accessories"]
    )
    
    # Date range
    st.subheader("📅 Date Range")
    use_date_range = st.checkbox("Filter by date range")
    if use_date_range:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("From", datetime.date(2022, 1, 1))
        with col2:
            end_date = st.date_input("To", datetime.date.today())

# Main content area
if uploaded_files:
    # Process files
    all_data = []
    file_info = []
    
    for uploaded_file in uploaded_files:
        try:
            # Read all sheets
            xls = pd.ExcelFile(uploaded_file)
            
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
                
                # Add source information
                df['Source_File'] = uploaded_file.name
                df['Source_Sheet'] = sheet_name
                df['Processed_Date'] = datetime.datetime.now()
                
                # Standardize and process
                df = StockAnalyzer.standardize_columns(df)
                df = StockAnalyzer.extract_stock_data(df)
                
                all_data.append(df)
                
                file_info.append({
                    'File': uploaded_file.name,
                    'Sheet': sheet_name,
                    'Rows': len(df),
                    'Sold': len(df[df['Status'] == 'Sold']),
                    'Unsold': len(df[df['Status'] == 'Unsold'])
                })
                
        except Exception as e:
            st.error(f"Error processing {uploaded_file.name}: {str(e)}")
    
    if all_data:
        # Combine all data
        combined_df = pd.concat(all_data, ignore_index=True)
        st.session_state.original_data = combined_df
        
        # Display file summary
        st.subheader("📋 File Processing Summary")
        info_df = pd.DataFrame(file_info)
        st.dataframe(info_df, use_container_width=True)
        
        # Apply filters
        filtered_df = combined_df.copy()
        
        if show_unsold_only and 'Status' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['Status'] == 'Unsold']
        
        if location_filter and 'Move' in filtered_df.columns:
            if 'All' not in location_filter:
                filtered_df = filtered_df[filtered_df['Move'].isin(location_filter)]
        
        if product_categories and 'Product Name' in filtered_df.columns:
            if 'All' not in product_categories:
                # Create a mapping of categories to keywords
                category_map = {
                    'Mi TV Stick': ['Mi TV Stick', 'Mi Tv Stick'],
                    'Redmi': ['Redmi'],
                    'Note Series': ['Note'],
                    'JBL': ['JBL'],
                    'Other Accessories': ['Speaker', 'Headphone']
                }
                
                mask = pd.Series(False, index=filtered_df.index)
                for category in product_categories:
                    if category in category_map:
                        for keyword in category_map[category]:
                            mask = mask | filtered_df['Product Name'].astype(str).str.contains(keyword, case=False, na=False)
                filtered_df = filtered_df[mask]
        
        if use_date_range and 'Date' in filtered_df.columns:
            filtered_df = filtered_df[
                (filtered_df['Date'] >= pd.Timestamp(start_date)) & 
                (filtered_df['Date'] <= pd.Timestamp(end_date))
            ]
        
        # Store filtered data
        st.session_state.processed_data = filtered_df
        
        # Generate report
        report = StockAnalyzer.generate_stock_report(filtered_df)
        st.session_state.stock_report = report
        
        # Display KPI metrics
        st.markdown("---")
        st.subheader("📊 Stock Overview")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f'<div class="stock-card">Total Items<br><h2>{len(filtered_df)}</h2></div>', unsafe_allow_html=True)
        
        with col2:
            unsold_count = len(filtered_df[filtered_df['Status'] == 'Unsold']) if 'Status' in filtered_df.columns else 0
            st.markdown(f'<div class="unsold-card">Unsold Items<br><h2>{unsold_count}</h2></div>', unsafe_allow_html=True)
        
        with col3:
            if 'Price' in filtered_df.columns and 'Status' in filtered_df.columns:
                unsold_value = filtered_df.loc[filtered_df['Status'] == 'Unsold', 'Price'].apply(pd.to_numeric, errors='coerce').sum()
                st.markdown(f'<div class="metric-card">Stock Value<br><h2>{unsold_value:,.0f}</h2></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="metric-card">Stock Value<br><h2>N/A</h2></div>', unsafe_allow_html=True)
        
        with col4:
            unique_products = filtered_df['Product Name'].nunique() if 'Product Name' in filtered_df.columns else 0
            st.markdown(f'<div class="metric-card">Unique Products<br><h2>{unique_products}</h2></div>', unsafe_allow_html=True)
        
        # Tabbed interface for different views
        tab1, tab2, tab3, tab4 = st.tabs(["📱 Stock Details", "📈 Analysis", "📍 Location View", "💾 Export"])
        
        with tab1:
            # Stock details table
            st.subheader("📱 Current Stock Details")
            
            # Select columns to display (your preferred columns from "My Stock Count.xlsx")
            display_columns = ['Product Name', 'Color', 'Sr No./ IMEI No.', 'Move']
            
            # Add additional columns if available
            available_columns = [col for col in display_columns if col in filtered_df.columns]
            
            if 'Date' in filtered_df.columns:
                available_columns.append('Date')
            if 'Price' in filtered_df.columns:
                available_columns.append('Price')
            if 'Days in Stock' in filtered_df.columns:
                available_columns.append('Days in Stock')
            if 'Source_Sheet' in filtered_df.columns:
                available_columns.append('Source_Sheet')
            
            # Display editable table
            display_df = filtered_df[available_columns].copy()
            
            # Format for display
            if 'Price' in display_df.columns:
                display_df['Price'] = display_df['Price'].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "")
            
            if 'Days in Stock' in display_df.columns:
                display_df['Days in Stock'] = display_df['Days in Stock'].astype(int)
            
            st.dataframe(display_df, use_container_width=True, height=400)
        
        with tab2:
            # Analysis views
            st.subheader("📈 Stock Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Product-wise stock
                if report and 'by_product' in report:
                    st.write("**Stock by Product**")
                    st.dataframe(report['by_product'], use_container_width=True)
                    
                    # Bar chart
                    if not report['by_product'].empty:
                        chart_data = report['by_product'].set_index('Product Name')['Unsold Count']
                        st.bar_chart(chart_data)
            
            with col2:
                # Aging analysis
                if report and 'aging_analysis' in report and not report['aging_analysis'].empty:
                    st.write("**Aging Analysis (Unsold Items)**")
                    st.dataframe(report['aging_analysis'], use_container_width=True)
                    
                    # Pie chart for aging
                    aging_chart = report['aging_analysis'].set_index('Aging Category')['Count']
                    st.bar_chart(aging_chart)
            
            # Profit analysis if available
            if report and 'profit_analysis' in report and not report['profit_analysis'].empty:
                st.write("**Profit Analysis (Sold Items)**")
                st.dataframe(report['profit_analysis'], use_container_width=True)
        
        with tab3:
            # Location-based view
            st.subheader("📍 Stock by Location")
            
            if report and 'by_location' in report and not report['by_location'].empty:
                # Location summary
                st.write("**Stock Count by Location**")
                st.dataframe(report['by_location'], use_container_width=True)
                
                # Location details
                if 'Move' in filtered_df.columns:
                    selected_location = st.selectbox(
                        "View details for location:",
                        filtered_df['Move'].unique()
                    )
                    
                    location_df = filtered_df[filtered_df['Move'] == selected_location]
                    if not location_df.empty:
                        st.write(f"**Items at {selected_location}:**")
                        location_display = location_df[['Product Name', 'Color', 'Sr No./ IMEI No.', 'Date']]
                        st.dataframe(location_display, use_container_width=True)
        
        with tab4:
            # Export options
            st.subheader("💾 Export Reports")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Export format selection
                export_format = st.radio(
                    "Select export format:",
                    ["Excel (Stock Count)", "Excel (Full Details)", "CSV", "PDF Summary"]
                )
                
                # File name
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
                default_name = f"Stock_Count_{timestamp}"
                filename = st.text_input("File name:", value=default_name)
            
            with col2:
                # What to export
                export_options = st.multiselect(
                    "Include in export:",
                    ["Current Stock", "Product Summary", "Location Summary", "Aging Report", "Profit Analysis"],
                    default=["Current Stock", "Product Summary"]
                )
                
                # Additional options
                include_prices = st.checkbox("Include price columns", value=True)
                include_dates = st.checkbox("Include date columns", value=True)
            
            # Prepare export data
            if export_format == "Excel (Stock Count)":
                # Your standard format (like "My Stock Count.xlsx")
                export_df = filtered_df[['Product Name', 'Color', 'Sr No./ IMEI No.', 'Move']].copy()
                
                if include_prices and 'Price' in filtered_df.columns:
                    export_df['Price'] = filtered_df['Price']
                
                if include_dates and 'Date' in filtered_df.columns:
                    export_df['Purchase Date'] = filtered_df['Date']
                
                # Create Excel file
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    export_df.to_excel(writer, sheet_name='Stock Count', index=False)
                    
                    if "Product Summary" in export_options and report and 'by_product' in report:
                        report['by_product'].to_excel(writer, sheet_name='Product Summary', index=False)
                    
                    if "Location Summary" in export_options and report and 'by_location' in report:
                        report['by_location'].to_excel(writer, sheet_name='Location Summary', index=False)
                    
                    if "Aging Report" in export_options and report and 'aging_analysis' in report:
                        report['aging_analysis'].to_excel(writer, sheet_name='Aging Report', index=False)
                
                output.seek(0)
                
                st.download_button(
                    label="📥 Download Excel Report",
                    data=output,
                    file_name=f"{filename}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            elif export_format == "Excel (Full Details)":
                # Export everything
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    filtered_df.to_excel(writer, sheet_name='Full Data', index=False)
                    
                    if report:
                        for sheet_name, sheet_data in report.items():
                            if isinstance(sheet_data, pd.DataFrame):
                                sheet_data.to_excel(writer, sheet_name=sheet_name, index=False)
                
                output.seek(0)
                
                st.download_button(
                    label="📥 Download Full Data",
                    data=output,
                    file_name=f"{filename}_Full.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            elif export_format == "CSV":
                # Export as CSV
                csv_data = filtered_df.to_csv(index=False)
                
                st.download_button(
                    label="📥 Download CSV",
                    data=csv_data,
                    file_name=f"{filename}.csv",
                    mime="text/csv"
                )
            
            elif export_format == "PDF Summary":
                st.info("PDF export requires additional setup. Please use Excel or CSV export for now.")
            
            # Quick export templates
            st.markdown("---")
            st.subheader("📋 Quick Templates")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Template for stock count (your main use case)
                template_data = pd.DataFrame(columns=['Product Name', 'Color', 'Sr No./ IMEI No.', 'Move', 'Remarks'])
                template_csv = template_data.to_csv(index=False)
                
                st.download_button(
                    label="📋 Download Empty Stock Count Template",
                    data=template_csv,
                    file_name="Stock_Count_Template.csv",
                    mime="text/csv"
                )
            
            with col2:
                # Template for new entries
                entry_template = pd.DataFrame(columns=['Date', 'Product Name', 'Color', 'Sr No./ IMEI No.', 'Price', 'Move'])
                entry_csv = entry_template.to_csv(index=False)
                
                st.download_button(
                    label="📝 Download New Entry Template",
                    data=entry_csv,
                    file_name="New_Entry_Template.csv",
                    mime="text/csv"
                )
        
        # Audit Trail
        st.markdown("---")
        st.subheader("📝 Audit Trail")
        
        audit_log = {
            'Processing Time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'Files Processed': [f.name for f in uploaded_files],
            'Total Records Processed': len(combined_df),
            'Unsold Items Found': len(filtered_df),
            'Filters Applied': {
                'Show Unsold Only': show_unsold_only,
                'Locations': location_filter,
                'Product Categories': product_categories,
                'Date Range': f"{start_date} to {end_date}" if use_date_range else "Not applied"
            }
        }
        
        st.json(audit_log, expanded=False)
        
        # Export audit log
        audit_df = pd.DataFrame([audit_log])
        audit_csv = audit_df.to_csv(index=False)
        
        st.download_button(
            label="📋 Download Audit Log",
            data=audit_csv,
            file_name=f"audit_log_{timestamp}.csv",
            mime="text/csv"
        )

else:
    # Welcome screen
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div style='text-align: center; padding: 40px;'>
            <h2>📱 Mobile & Electronics Inventory System</h2>
            <p style='font-size: 1.2rem; color: #666; margin-bottom: 30px;'>
                Track stock, generate audit reports, and manage inventory
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Quick start guide
        with st.expander("🚀 How to Use", expanded=True):
            st.markdown("""
            **For Stock Count Reports (Your Main Use Case):**
            1. **Upload** your transaction Excel files (like Dummy Data.xlsx)
            2. **Check** "Show only unsold items" (this filters sold items)
            3. **Select** location filters if needed
            4. **View** the stock in "Stock Details" tab
            5. **Export** using "Excel (Stock Count)" format
            
            **Supported Data Format:**
            - Columns: `Date`, `Product Name`, `Color`, `Sr No./ IMEI No.`, `Move`, `Sold Date`
            - Multiple sheets per file (each product category)
            - Mix of sold and unsold items
            
            **Output Format (like My Stock Count.xlsx):**
            - Product Name, Color, Sr No./ IMEI No., Move
            - Optional: Price, Purchase Date
            """)
        
        # Example workflow
        with st.expander("📊 Sample Workflow"):
            st.markdown("""
            1. **Upload** `Dummy Data.xlsx`
            2. **Filter** → Show only unsold items
            3. **Result** → Get current stock list
            4. **Export** → Download as `My Stock Count.xlsx`
            5. **Analyze** → Check aging, location distribution
            
            **Common Tasks:**
            - Daily stock count
            - Monthly audit reports
            - Location-wise stock check
            - Aging analysis (slow-moving items)
            - Profit analysis on sold items
            """)

# Footer
st.markdown("---")
st.caption("📱 Mobile & Electronics Stock System v3.0 • Designed for inventory tracking and audit reports")