import streamlit as st
import pandas as pd
import numpy as np
import io
import base64
import requests
import re
from validator import (
    clean_sku,
    clean_pid,
    StockResolver,
    validate_lazada,
    validate_shopee,
    validate_tiktok
)

# Page Configuration
st.set_page_config(
    page_title="DKSH Stock Validator for SG & MY",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Premium Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .main {
        background-color: #f7f9fc;
    }
    
    /* Header styling */
    .header-container {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 2.5rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 10px 20px rgba(30, 60, 114, 0.15);
    }
    
    .header-title {
        font-weight: 700;
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
    }
    
    .header-subtitle {
        font-weight: 300;
        font-size: 1.1rem;
        opacity: 0.9;
    }
    
    /* Card design */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        border: 1px solid #eef2f6;
        text-align: center;
        transition: transform 0.2s ease-in-out;
    }
    .metric-card:hover {
        transform: translateY(-4px);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #1e3c72;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #64748b;
        margin-top: 0.25rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Tab styles */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: #f1f5f9;
        border-radius: 8px 8px 0px 0px;
        padding: 10px 20px;
        font-weight: 600;
        color: #475569;
        border: none;
    }

    .stTabs [aria-selected="true"] {
        background-color: #1e3c72 !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# GitHub Helper Functions
# ----------------------------------------------------
def github_get_headers(token):
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers

def github_list_files(repo, path, token):
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = github_get_headers(token)
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        items = response.json()
        if isinstance(items, list):
            # Return list of file names/paths
            return [item for item in items if item['type'] == 'file']
        return []
    else:
        st.sidebar.error(f"GitHub Error: {response.json().get('message', 'Failed to fetch directory content')}")
        return []

def github_fetch_file(repo, file_path, token):
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = github_get_headers(token)
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        content_b64 = data.get('content', '')
        # Remove newlines in base64 encoding if any
        content_bytes = base64.b64decode(content_b64.replace('\n', ''))
        return content_bytes, data.get('sha')
    else:
        st.error(f"Error fetching file {file_path}: {response.json().get('message', 'Unknown error')}")
        return None, None

def github_commit_file(repo, file_path, content_bytes, commit_message, sha, token):
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = github_get_headers(token)
    
    payload = {
        "message": commit_message,
        "content": base64.b64encode(content_bytes).decode('utf-8')
    }
    if sha:
        payload["sha"] = sha
        
    response = requests.put(url, json=payload, headers=headers)
    if response.status_code in [200, 201]:
        return True, response.json().get('commit', {}).get('html_url')
    else:
        return False, response.json().get('message', 'Unknown error')

# ----------------------------------------------------
# Main Streamlit Application
# ----------------------------------------------------

# App Header
st.markdown("""
<div class="header-container">
    <div class="header-title">DKSH Stock Validator</div>
    <div class="header-subtitle">Automated Stock & Status Validation System for Singapore (SG) & Malaysia (MY) Marketplaces</div>
</div>
""", unsafe_allow_html=True)

# Session States
if 'github_files' not in st.session_state:
    st.session_state.github_files = []
if 'all_df' not in st.session_state:
    st.session_state.all_df = None
if 'tc_inv_df' not in st.session_state:
    st.session_state.tc_inv_df = None
if 'lazada_df' not in st.session_state:
    st.session_state.lazada_df = None
if 'shopee_stock_df' not in st.session_state:
    st.session_state.shopee_stock_df = None
if 'shopee_status_df' not in st.session_state:
    st.session_state.shopee_status_df = None
if 'tiktok_stock_df' not in st.session_state:
    st.session_state.tiktok_stock_df = None
if 'tiktok_active_df' not in st.session_state:
    st.session_state.tiktok_active_df = None
if 'tiktok_inactive_df' not in st.session_state:
    st.session_state.tiktok_inactive_df = None

# Sidebar Configuration
st.sidebar.image("https://img.icons8.com/color/96/data-configuration.png", width=60)
st.sidebar.header("Configuration Panel")

data_source = st.sidebar.radio(
    "Select Input Source",
    options=["Local File Upload", "GitHub Pull Integration"]
)

# Initialize GitHub variables
github_pat = ""
github_repo = ""
github_branch = "main"
github_folder = ""

if data_source == "GitHub Pull Integration":
    st.sidebar.markdown("---")
    st.sidebar.subheader("GitHub Settings")
    github_pat = st.sidebar.text_input("Personal Access Token (PAT)", type="password", help="Needed if the repository is private.")
    github_repo = st.sidebar.text_input("Repository (owner/name)", placeholder="e.g. DKSH-Singapore/stock-reports")
    github_branch = st.sidebar.text_input("Branch", value="main")
    github_folder = st.sidebar.text_input("Subfolder Path (optional)", value="", placeholder="e.g. data")
    
    if st.sidebar.button("Fetch Files list from GitHub", use_container_width=True):
        if not github_repo:
            st.sidebar.error("Repository name is required!")
        else:
            with st.spinner("Connecting to GitHub..."):
                files = github_list_files(github_repo, github_folder, github_pat)
                if files:
                    st.session_state.github_files = files
                    st.sidebar.success(f"Loaded {len(files)} files!")

st.sidebar.markdown("---")
st.sidebar.subheader("Global Settings")
country_mode = st.sidebar.selectbox("Country View Mode", ["SG & MY All Marketplaces", "SG Only", "MY Only"])

# Helper load data function
def parse_file(file_obj, file_name, skip_lazada_rows=False):
    if file_name.endswith('.csv'):
        # For csv
        if skip_lazada_rows:
            df = pd.read_csv(file_obj)
            df = df.iloc[3:].reset_index(drop=True)
        else:
            df = pd.read_csv(file_obj)
    else:
        # For excel
        if skip_lazada_rows:
            df = pd.read_excel(file_obj)
            df = df.iloc[3:].reset_index(drop=True)
        else:
            df = pd.read_excel(file_obj)
    return df

# Helper to fetch/upload file widgets
def file_selector(label, key_suffix, mandatory=False):
    label_status = "*(Mandatory)*" if mandatory else "(Optional)"
    if data_source == "Local File Upload":
        uploaded_file = st.file_uploader(f"Upload {label} {label_status}", type=['xlsx', 'xls', 'csv'], key=f"upload_{key_suffix}")
        if uploaded_file is not None:
            return uploaded_file, uploaded_file.name
        return None, None
    else:
        if st.session_state.github_files:
            file_options = ["None"] + [f['path'] for f in st.session_state.github_files]
            selected_path = st.selectbox(f"Select {label} {label_status} from Repo", options=file_options, key=f"github_{key_suffix}")
            if selected_path != "None":
                return selected_path, selected_path.split('/')[-1]
        else:
            st.warning("Please configure GitHub settings and fetch the file list first.")
        return None, None

# Main Data Ingest Section
st.subheader("📁 Step 1: Ingest Inputs & Configuration Files")
col1, col2 = st.columns(2)

with col1:
    st.info("💡 **Core inventory configuration files** (required to run validation)")
    # All File Input
    all_file_raw, all_file_name = file_selector("All File (TC Stock/Reserved Stock)", "all_file", mandatory=True)
    # TC Inventory Input
    tc_inv_raw, tc_inv_name = file_selector("TC Inventory File (Max Qty/TC Status)", "tc_inv", mandatory=True)

with col2:
    st.info("🛒 **Marketplace specific files** (upload/select files you wish to validate)")
    marketplaces_to_validate = st.multiselect(
        "Which marketplaces do you want to validate?",
        options=["Lazada SG", "Shopee SG", "TikTok MY"],
        default=["Lazada SG", "Shopee SG", "TikTok MY"]
    )
    
    lazada_raw = None
    shopee_stock_raw = None
    shopee_status_raw = None
    tiktok_stock_raw = None
    tiktok_active_raw = None
    tiktok_inactive_raw = None
    
    if "Lazada SG" in marketplaces_to_validate:
        st.markdown("**Lazada SG Files**")
        lazada_raw, _ = file_selector("Lazada Report (Quantity/Status)", "lazada")
        
    if "Shopee SG" in marketplaces_to_validate:
        st.markdown("**Shopee SG Files**")
        shopee_stock_raw, _ = file_selector("Shopee Stock Report (SKU/Product ID/Stock)", "shopee_stock")
        shopee_status_raw, _ = file_selector("Shopee Status Report (Active PIDs list)", "shopee_status")
        
    if "TikTok MY" in marketplaces_to_validate:
        st.markdown("**TikTok MY Files**")
        tiktok_stock_raw, _ = file_selector("TikTok Stock Report (Seller SKU/Product ID/Quantity)", "tiktok_stock")
        tiktok_active_raw, _ = file_selector("TikTok Active SKU Report", "tiktok_active")
        tiktok_inactive_raw, _ = file_selector("TikTok Inactive SKU Report", "tiktok_inactive")

# Load and Parse Action Button
if st.button("🚀 Process Stock Validation Reports", type="primary", use_container_width=True):
    # Validation of mandatory files
    if not all_file_raw or not tc_inv_raw:
        st.error("❌ Both 'All File' and 'TC Inventory' file are required to perform validation!")
    else:
        with st.spinner("Processing files and calculating stock/bundle logic..."):
            try:
                # Resolve file buffers depending on data source
                def get_bytes_buffer(raw_obj):
                    if data_source == "Local File Upload":
                        return raw_obj
                    else:
                        # Fetch from GitHub
                        content_bytes, _ = github_fetch_file(github_repo, raw_obj, github_pat)
                        return io.BytesIO(content_bytes) if content_bytes else None

                # Ingest All File
                all_buf = get_bytes_buffer(all_file_raw)
                st.session_state.all_df = parse_file(all_buf, all_file_name)
                
                # Ingest TC Inventory File
                tc_inv_buf = get_bytes_buffer(tc_inv_raw)
                st.session_state.tc_inv_df = parse_file(tc_inv_buf, tc_inv_name)
                
                # Ingest Lazada
                if lazada_raw:
                    laz_buf = get_bytes_buffer(lazada_raw)
                    # For Lazada, skip the first row header and then ignore the next 3 rows.
                    # This means we read the file normally but slice out the first 3 rows of data.
                    st.session_state.lazada_df = parse_file(laz_buf, "lazada.xlsx", skip_lazada_rows=True)
                else:
                    st.session_state.lazada_df = None
                    
                # Ingest Shopee
                if shopee_stock_raw:
                    st.session_state.shopee_stock_df = parse_file(get_bytes_buffer(shopee_stock_raw), "shopee_stock.xlsx")
                else:
                    st.session_state.shopee_stock_df = None
                    
                if shopee_status_raw:
                    st.session_state.shopee_status_df = parse_file(get_bytes_buffer(shopee_status_raw), "shopee_status.xlsx")
                else:
                    st.session_state.shopee_status_df = None
                    
                # Ingest TikTok
                if tiktok_stock_raw:
                    st.session_state.tiktok_stock_df = parse_file(get_bytes_buffer(tiktok_stock_raw), "tiktok_stock.xlsx")
                else:
                    st.session_state.tiktok_stock_df = None
                    
                if tiktok_active_raw:
                    st.session_state.tiktok_active_df = parse_file(get_bytes_buffer(tiktok_active_raw), "tiktok_active.xlsx")
                else:
                    st.session_state.tiktok_active_df = None
                    
                if tiktok_inactive_raw:
                    st.session_state.tiktok_inactive_df = parse_file(get_bytes_buffer(tiktok_inactive_raw), "tiktok_inactive.xlsx")
                else:
                    st.session_state.tiktok_inactive_df = None
                
                st.success("🎉 Files loaded and parsed successfully!")
            except Exception as e:
                st.error(f"❌ Error parsing input files: {e}")

st.markdown("---")

# ----------------------------------------------------
# Step 2: Display Validation Dashboard
# ----------------------------------------------------
st.subheader("📊 Step 2: Stock & Status Validation Dashboard")

# Check if data exists in session state
if st.session_state.all_df is not None:
    
    # Create tabs for each country / marketplace
    available_tabs = []
    if "Lazada SG" in marketplaces_to_validate and country_mode in ["SG & MY All Marketplaces", "SG Only"]:
        available_tabs.append("Lazada SG (SKU Level)")
    if "Shopee SG" in marketplaces_to_validate and country_mode in ["SG & MY All Marketplaces", "SG Only"]:
        available_tabs.append("Shopee SG (PID Level)")
    if "TikTok MY" in marketplaces_to_validate and country_mode in ["SG & MY All Marketplaces", "MY Only"]:
        available_tabs.append("TikTok MY (PID Level)")
        
    if not available_tabs:
        st.warning("No marketplaces selected for validation under current Country View Mode.")
    else:
        tabs = st.tabs(available_tabs)
        
        for tab, tab_name in zip(tabs, available_tabs):
            with tab:
                if "Lazada SG" in tab_name:
                    st.markdown("### 🛒 Lazada SG Stock & Status Mismatch Report")
                    if st.session_state.lazada_df is not None:
                        lazada_result = validate_lazada(
                            st.session_state.lazada_df,
                            st.session_state.tc_inv_df,
                            st.session_state.all_df
                        )
                        
                        # Show summary cards
                        tot_skus = len(lazada_result)
                        all_good_count = len(lazada_result[lazada_result['Action Required'] == 'All Good'])
                        mismatches = tot_skus - all_good_count
                        
                        mcol1, mcol2, mcol3 = st.columns(3)
                        with mcol1:
                            st.markdown(f'<div class="metric-card"><div class="metric-value">{tot_skus}</div><div class="metric-label">Total SKUs</div></div>', unsafe_allow_html=True)
                        with mcol2:
                            st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #22c55e;">{all_good_count}</div><div class="metric-label">All Good (Matched)</div></div>', unsafe_allow_html=True)
                        with mcol3:
                            st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #ef4444;">{mismatches}</div><div class="metric-label">Mismatches (Action Required)</div></div>', unsafe_allow_html=True)
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # Filter by Action
                        action_options = ["All"] + list(lazada_result['Action Required'].unique())
                        selected_action = st.selectbox("Filter by Action Required:", action_options, key="laz_filter")
                        
                        filtered_laz = lazada_result if selected_action == "All" else lazada_result[lazada_result['Action Required'] == selected_action]
                        
                        # Display table
                        st.dataframe(filtered_laz, use_container_width=True)
                        
                        # Export
                        csv_data = filtered_laz.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download Lazada Validation CSV Report",
                            data=csv_data,
                            file_name="Lazada_Status_Validation_Report.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    else:
                        st.info("Lazada SG Report file has not been uploaded/selected yet.")
                        
                elif "Shopee SG" in tab_name:
                    st.markdown("### 🛒 Shopee SG Consolidated Stock Report")
                    if st.session_state.shopee_stock_df is not None:
                        shopee_pid_df, shopee_sku_df = validate_shopee(
                            st.session_state.shopee_stock_df,
                            st.session_state.shopee_status_df,
                            st.session_state.tc_inv_df,
                            st.session_state.all_df
                        )
                        
                        # Metric Cards
                        tot_pids = len(shopee_pid_df)
                        pid_matched = len(shopee_pid_df[shopee_pid_df['Stock Match'] == True])
                        pid_mismatches = tot_pids - pid_matched
                        
                        mcol1, mcol2, mcol3 = st.columns(3)
                        with mcol1:
                            st.markdown(f'<div class="metric-card"><div class="metric-value">{tot_pids}</div><div class="metric-label">Total Product IDs</div></div>', unsafe_allow_html=True)
                        with mcol2:
                            st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #22c55e;">{pid_matched}</div><div class="metric-label">Product Stock Matches</div></div>', unsafe_allow_html=True)
                        with mcol3:
                            st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #ef4444;">{pid_mismatches}</div><div class="metric-label">Product Stock Mismatches</div></div>', unsafe_allow_html=True)
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # Tabs within Shopee for Consolidated vs. SKU level
                        sub_tab1, sub_tab2 = st.tabs(["PID Level Consolidation", "SKU Level Validation Detail"])
                        
                        with sub_tab1:
                            st.dataframe(shopee_pid_df, use_container_width=True)
                            csv_pid = shopee_pid_df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="📥 Download Shopee PID Consolidation CSV",
                                data=csv_pid,
                                file_name="Shopee_Consolidated_PID_Report.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
                            
                        with sub_tab2:
                            # Filter
                            shopee_actions = ["All"] + list(shopee_sku_df['Action Required'].unique())
                            selected_shopee_act = st.selectbox("Filter Shopee SKU Action Required:", shopee_actions, key="shopee_filter")
                            filtered_shopee_sku = shopee_sku_df if selected_shopee_act == "All" else shopee_sku_df[shopee_sku_df['Action Required'] == selected_shopee_act]
                            
                            st.dataframe(filtered_shopee_sku, use_container_width=True)
                            csv_sku = filtered_shopee_sku.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="📥 Download Shopee SKU Detail CSV",
                                data=csv_sku,
                                file_name="Shopee_SKU_Validation_Detail.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
                    else:
                        st.info("Shopee SG Stock report has not been uploaded/selected yet.")
                        
                elif "TikTok MY" in tab_name:
                    st.markdown("### 🛒 TikTok MY Consolidated Stock Report")
                    if st.session_state.tiktok_stock_df is not None:
                        tiktok_pid_df, tiktok_sku_df = validate_tiktok(
                            st.session_state.tiktok_stock_df,
                            st.session_state.tiktok_active_df,
                            st.session_state.tiktok_inactive_df,
                            st.session_state.tc_inv_df,
                            st.session_state.all_df
                        )
                        
                        # Metric Cards
                        tot_pids = len(tiktok_pid_df)
                        pid_matched = len(tiktok_pid_df[tiktok_pid_df['Stock Match'] == True])
                        pid_mismatches = tot_pids - pid_matched
                        
                        mcol1, mcol2, mcol3 = st.columns(3)
                        with mcol1:
                            st.markdown(f'<div class="metric-card"><div class="metric-value">{tot_pids}</div><div class="metric-label">Total Product IDs</div></div>', unsafe_allow_html=True)
                        with mcol2:
                            st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #22c55e;">{pid_matched}</div><div class="metric-label">Product Stock Matches</div></div>', unsafe_allow_html=True)
                        with mcol3:
                            st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #ef4444;">{pid_mismatches}</div><div class="metric-label">Product Stock Mismatches</div></div>', unsafe_allow_html=True)
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # Tabs within TikTok
                        sub_tab1, sub_tab2 = st.tabs(["PID Level Consolidation", "SKU Level Validation Detail"])
                        
                        with sub_tab1:
                            st.dataframe(tiktok_pid_df, use_container_width=True)
                            csv_pid = tiktok_pid_df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="📥 Download TikTok PID Consolidation CSV",
                                data=csv_pid,
                                file_name="TikTok_Consolidated_PID_Report.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
                            
                        with sub_tab2:
                            # Filter
                            tiktok_actions = ["All"] + list(tiktok_sku_df['Action Required'].unique())
                            selected_tiktok_act = st.selectbox("Filter TikTok SKU Action Required:", tiktok_actions, key="tiktok_filter")
                            filtered_tiktok_sku = tiktok_sku_df if selected_tiktok_act == "All" else tiktok_sku_df[tiktok_sku_df['Action Required'] == selected_tiktok_act]
                            
                            st.dataframe(filtered_tiktok_sku, use_container_width=True)
                            csv_sku = filtered_tiktok_sku.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="📥 Download TikTok SKU Detail CSV",
                                data=csv_sku,
                                file_name="TikTok_SKU_Validation_Detail.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
                    else:
                        st.info("TikTok MY Stock report has not been uploaded/selected yet.")

    # ----------------------------------------------------
    # Step 3: Export & Push Validation Report back to GitHub
    # ----------------------------------------------------
    st.markdown("---")
    st.subheader("📤 Step 3: Commit Reports back to GitHub Repository")
    
    if not github_repo:
        st.info("ℹ️ Configure GitHub integration settings in the sidebar to commit validation reports directly back to your repository.")
    else:
        # Commit options
        commit_col1, commit_col2 = st.columns(2)
        with commit_col1:
            report_types = st.multiselect(
                "Select reports to push to GitHub:",
                options=["Lazada SKU Level", "Shopee PID Consolidated", "Shopee SKU Detail", "TikTok PID Consolidated", "TikTok SKU Detail"],
                default=["Lazada SKU Level"]
            )
            commit_message = st.text_input("Commit Message", value="Update stock validation reports")
            
        with commit_col2:
            github_output_folder = st.text_input("Repo Output Folder Path", value="reports")
            
        if st.button("💾 Push Selected Reports to GitHub", type="primary", use_container_width=True):
            success_count = 0
            error_count = 0
            
            with st.spinner("Pushing reports to GitHub..."):
                for report_type in report_types:
                    # Resolve data
                    df_to_push = None
                    file_name = ""
                    
                    if report_type == "Lazada SKU Level" and st.session_state.lazada_df is not None:
                        df_to_push = validate_lazada(st.session_state.lazada_df, st.session_state.tc_inv_df, st.session_state.all_df)
                        file_name = "lazada_validation_report.csv"
                    elif report_type == "Shopee PID Consolidated" and st.session_state.shopee_stock_df is not None:
                        df_to_push, _ = validate_shopee(st.session_state.shopee_stock_df, st.session_state.shopee_status_df, st.session_state.tc_inv_df, st.session_state.all_df)
                        file_name = "shopee_consolidated_pid_report.csv"
                    elif report_type == "Shopee SKU Detail" and st.session_state.shopee_stock_df is not None:
                        _, df_to_push = validate_shopee(st.session_state.shopee_stock_df, st.session_state.shopee_status_df, st.session_state.tc_inv_df, st.session_state.all_df)
                        file_name = "shopee_sku_validation_detail.csv"
                    elif report_type == "TikTok PID Consolidated" and st.session_state.tiktok_stock_df is not None:
                        df_to_push, _ = validate_tiktok(st.session_state.tiktok_stock_df, st.session_state.tiktok_active_df, st.session_state.tiktok_inactive_df, st.session_state.tc_inv_df, st.session_state.all_df)
                        file_name = "tiktok_consolidated_pid_report.csv"
                    elif report_type == "TikTok SKU Detail" and st.session_state.tiktok_stock_df is not None:
                        _, df_to_push = validate_tiktok(st.session_state.tiktok_stock_df, st.session_state.tiktok_active_df, st.session_state.tiktok_inactive_df, st.session_state.tc_inv_df, st.session_state.all_df)
                        file_name = "tiktok_sku_validation_detail.csv"
                        
                    if df_to_push is not None:
                        # Convert to csv bytes
                        csv_str = df_to_push.to_csv(index=False)
                        content_bytes = csv_str.encode('utf-8')
                        
                        target_path = f"{github_output_folder}/{file_name}" if github_output_folder else file_name
                        
                        # Check if file already exists to get SHA
                        existing_url = f"https://api.github.com/repos/{github_repo}/contents/{target_path}?ref={github_branch}"
                        headers = github_get_headers(github_pat)
                        resp = requests.get(existing_url, headers=headers)
                        sha = None
                        if resp.status_code == 200:
                            sha = resp.json().get('sha')
                            
                        # Commit
                        ok, details = github_commit_file(
                            repo=github_repo,
                            file_path=target_path,
                            content_bytes=content_bytes,
                            commit_message=commit_message,
                            sha=sha,
                            token=github_pat
                        )
                        if ok:
                            success_count += 1
                            st.success(f"✅ Successfully committed '{file_name}' to GitHub! [View Commit]({details})")
                        else:
                            error_count += 1
                            st.error(f"❌ Failed to commit '{file_name}': {details}")
                            
                if success_count > 0:
                    st.toast(f"Successfully uploaded {success_count} reports!")
                if error_count > 0:
                    st.toast("Some uploads failed. Check error messages.", icon="⚠️")

else:
    # Instructions panel
    st.info("👈 Please load your 'All File' and 'TC Inventory' file, plus any Marketplace files using the Configuration Panel on the left, then click **Process Stock Validation Reports** to view mismatch dashboards.")
    
    st.markdown("""
    ### System Quick Start Guide
    This tool allows you to match and validate stock quantities and status values between your core **TC Inventory** system and major marketplaces (**Lazada SG**, **Shopee SG**, and **TikTok MY**).
    
    #### 1. Ingest Mode Options
    - **Local File Upload**: Drag and drop reports downloaded directly from Seller Centers.
    - **GitHub Integration**: Fetch source stock inventory files from a GitHub repository, validate them instantly, and commit the status mismatch reports back to a GitHub folder.
    
    #### 2. Key Validation Logic
    - **Bundle SKU Resolution (`+` sign)**: If an SKU is a bundle of components (e.g. `SKU_A+SKU_B`), the system resolves the stock of each individual SKU in the All File and sets the bundle quantity as the minimum stock among all components.
    - **Bundle SKU Division (`X` sign)**: If an SKU represents a multiplier bundle (e.g. `AX2`), the system resolves the base SKU (`A`), divides its stock by the multiplier (`2`), and rounds down to the nearest integer.
    - **Status & Stock Alignment**: Resolves differences between MP Status/Stock and TC Status/Stock, identifying exactly whether an SKU should be changed to **Active**, **Inactive**, or if there is a **Reserved/Buffer** condition.
    - **PID Level Consolidation**: Automatically aggregates individual SKU stocks by Product ID for Shopee and TikTok, comparing the marketplace consolidated quantities against TC stocks.
    """)
