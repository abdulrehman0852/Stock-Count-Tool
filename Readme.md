# 📊 Stock Count Web Application

A Streamlit-based web tool for uploading, filtering, editing, and exporting stock data from Excel files.  
This application is designed to streamline inventory management by allowing users to process multiple Excel files, apply filters, preview and edit data, and export the results.

## ✨ Features

- Upload one or more Excel (`.xlsx`) files.
- Automatically detect sheets with a **"Sold Date"** column.
- Select sheets and columns for processing.
- Filter options:
  - Rows where "Sold Date" is blank.
  - Filter by a specific column and value.
  - Optional date range filtering.
- Preview and **edit data before exporting**.
- Export results in **Excel**, **CSV**, or **(PDF - coming soon)** formats.
- Search within extracted data.
- Basic data visualization (bar charts).
- Summary statistics and unique value counts.
- Audit trail logging.

## 📦 Requirements

Install dependencies:

```bash
pip install streamlit pandas openpyxl
```
