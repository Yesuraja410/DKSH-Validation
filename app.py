import streamlit as st
import pandas as pd
import numpy as np
import io
import base64
import requests
import re
import os
from datetime import datetime
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
    page_title="DKSH Stock Validator",
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

# Persistent reports folder
REPORT_DIR = "C:/Users/Yesuraja/Documents/DKSH Stock Validator for SG & MY/saved_reports"
os.makedirs(REPORT_DIR, exist_ok=True)

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

# Session States
if 'github_files' not in st.session_state:
    st.session_state.github_files = []
if 'validation_run' not in st.session_state:
    st.session_state.validation_run = False
if 'lazada_results' not in st.session_state:
    st.session_state.lazada_results = None
if 'shopee_pid_results' not in st.session_state:
    st.session_state.shopee_pid_results = None
if 'shopee_sku_results' not in st.session_state:
    st.session_state.shopee_sku_results = None
if 'tiktok_pid_results' not in st.session_state:
    st.session_state.tiktok_pid_results = None
if 'tiktok_sku_results' not in st.session_state:
    st.session_state.tiktok_sku_results = None
if 'report_path' not in st.session_state:
    st.session_state.report_path = None
if 'report_fname' not in st.session_state:
    st.session_state.report_fname = None

# Sidebar Configuration
st.sidebar.image("https://img.icons8.com/color/96/data-configuration.png", width=60)
st.sidebar.header("CONFIGURATION")

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
st.sidebar.subheader("SELECT COUNTRY")
country = st.sidebar.selectbox("Country", ["SG", "MY", "TH"], label_visibility="collapsed")

# Helper load data function
def parse_file(file_obj, file_name, skip_lazada_rows=False):
    if file_name.endswith('.csv'):
        if skip_lazada_rows:
            df = pd.read_csv(file_obj)
            df = df.iloc[3:].reset_index(drop=True)
        else:
            df = pd.read_csv(file_obj)
    else:
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
            st.warning("Fetch file list first.")
        return None, None

def get_bytes_buffer(raw_obj):
    if data_source == "Local File Upload":
        return raw_obj
    else:
        content_bytes, _ = github_fetch_file(github_repo, raw_obj, github_pat)
        return io.BytesIO(content_bytes) if content_bytes else None

def generate_excel_report(lazada_res, shopee_pid, shopee_sku, tiktok_pid, tiktok_sku):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        if lazada_res is not None and not lazada_res.empty:
            lazada_res.to_excel(writer, sheet_name="Lazada SKU Level", index=False)
        if shopee_pid is not None and not shopee_pid.empty:
            shopee_pid.to_excel(writer, sheet_name="Shopee PID Level", index=False)
        if shopee_sku is not None and not shopee_sku.empty:
            shopee_sku.to_excel(writer, sheet_name="Shopee SKU Level", index=False)
        if tiktok_pid is not None and not tiktok_pid.empty:
            tiktok_pid.to_excel(writer, sheet_name="TikTok PID Level", index=False)
        if tiktok_sku is not None and not tiktok_sku.empty:
            tiktok_sku.to_excel(writer, sheet_name="TikTok SKU Level", index=False)
    return buffer.getvalue()

st.sidebar.markdown("---")

# Expanders for Marketplaces
with st.sidebar.expander(f"Lazada {country}"):
    lazada_raw, lazada_name = file_selector("Lazada File", "lazada")

with st.sidebar.expander(f"Shopee {country}"):
    shopee_stock_raw, shopee_stock_name = file_selector("Shopee Stock File", "shopee_stock")
    shopee_status_raw, shopee_status_name = file_selector("Shopee Status File", "shopee_status")

with st.sidebar.expander(f"TikTok {country}"):
    tiktok_active_raw, tiktok_active_name = file_selector("TikTok Active File", "tiktok_active")
    tiktok_inactive_raw, tiktok_inactive_name = file_selector("TikTok Inactive File", "tiktok_inactive")

with st.sidebar.expander("Reference Files"):
    tc_inv_raw, tc_inv_name = file_selector("TC Inventory", "tc_inv", mandatory=True)
    all_file_raw, all_file_name = file_selector("TC All File", "all_file", mandatory=True)

st.sidebar.markdown("---")
run_validation = st.sidebar.button("Run Validation", type="primary", use_container_width=True)

# App Header
st.markdown(f"""
<div class="header-container">
    <div class="header-title">DKSH Stock Validator</div>
    <div class="header-subtitle">Automated Stock & Status Validation System for SG, MY & TH Marketplaces</div>
</div>
""", unsafe_allow_html=True)

# Run validation process
if run_validation:
    if not all_file_raw or not tc_inv_raw:
        st.error("❌ Both 'TC All File' and 'TC Inventory' file are required to perform validation!")
    else:
        with st.spinner("Processing files and calculating stock/bundle logic..."):
            try:
                # Ingest All File
                all_buf = get_bytes_buffer(all_file_raw)
                all_df = parse_file(all_buf, all_file_name)
                
                # Ingest TC Inventory File
                tc_inv_buf = get_bytes_buffer(tc_inv_raw)
                tc_inv_df = parse_file(tc_inv_buf, tc_inv_name)
                
                # Clear previous results
                st.session_state.lazada_results = None
                st.session_state.shopee_pid_results = None
                st.session_state.shopee_sku_results = None
                st.session_state.tiktok_pid_results = None
                st.session_state.tiktok_sku_results = None
                st.session_state.validation_run = False
                st.session_state.report_path = None
                st.session_state.report_fname = None
                
                # Lazada
                if lazada_raw:
                    laz_buf = get_bytes_buffer(lazada_raw)
                    lazada_df = parse_file(laz_buf, lazada_name, skip_lazada_rows=True)
                    st.session_state.lazada_results = validate_lazada(lazada_df, tc_inv_df, all_df)
                    
                # Shopee
                if shopee_stock_raw:
                    shopee_stock_df = parse_file(get_bytes_buffer(shopee_stock_raw), shopee_stock_name)
                    shopee_status_df = parse_file(get_bytes_buffer(shopee_status_raw), shopee_status_name) if shopee_status_raw else None
                    shopee_pid, shopee_sku = validate_shopee(shopee_stock_df, shopee_status_df, tc_inv_df, all_df)
                    st.session_state.shopee_pid_results = shopee_pid
                    st.session_state.shopee_sku_results = shopee_sku
                    
                # TikTok
                if tiktok_active_raw or tiktok_inactive_raw:
                    tiktok_active_df = parse_file(get_bytes_buffer(tiktok_active_raw), tiktok_active_name) if tiktok_active_raw else None
                    tiktok_inactive_df = parse_file(get_bytes_buffer(tiktok_inactive_raw), tiktok_inactive_name) if tiktok_inactive_raw else None
                    tiktok_pid, tiktok_sku = validate_tiktok(tiktok_active_df, tiktok_inactive_df, tc_inv_df, all_df)
                    st.session_state.tiktok_pid_results = tiktok_pid
                    st.session_state.tiktok_sku_results = tiktok_sku
                
                if (st.session_state.lazada_results is not None or 
                    st.session_state.shopee_pid_results is not None or 
                    st.session_state.tiktok_pid_results is not None):
                    
                    st.session_state.validation_run = True
                    
                    # Generate report and save to persistent folder
                    excel_data = generate_excel_report(
                        st.session_state.lazada_results,
                        st.session_state.shopee_pid_results,
                        st.session_state.shopee_sku_results,
                        st.session_state.tiktok_pid_results,
                        st.session_state.tiktok_sku_results
                    )
                    
                    today = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    report_fname = f"DKSH_Validation_Report_{country}_{today}.xlsx"
                    report_path = os.path.join(REPORT_DIR, report_fname)
                    
                    with open(report_path, "wb") as f:
                        f.write(excel_data)
                        
                    st.session_state.report_path = report_path
                    st.session_state.report_fname = report_fname
                    
                    st.success("🎉 Validation completed successfully! Report saved.")
                else:
                    st.warning("⚠️ No marketplace files were uploaded/selected for validation.")
                    
            except Exception as e:
                st.error(f"❌ Error during validation: {e}")
                st.exception(e)

st.write(f"Country: {country} | Upload files in the sidebar then click Run Validation.")

# Tabs Layout
tab1, tab2, tab3 = st.tabs([
    "Status Validation",
    "Downloads",
    "Saved Reports",
])

# Tab 1: Status Validation
with tab1:
    if st.session_state.validation_run:
        results_tabs_names = []
        if st.session_state.lazada_results is not None:
            results_tabs_names.append(f"Lazada {country}")
        if st.session_state.shopee_pid_results is not None:
            results_tabs_names.append(f"Shopee {country}")
        if st.session_state.tiktok_pid_results is not None:
            results_tabs_names.append(f"TikTok {country}")
            
        if not results_tabs_names:
            st.info("No marketplaces validated. Please upload files in the sidebar and run validation.")
        else:
            sub_tabs = st.tabs(results_tabs_names)
            for sub_tab, name in zip(sub_tabs, results_tabs_names):
                with sub_tab:
                    if "Lazada" in name:
                        st.markdown(f"### 🛒 Lazada {country} Stock & Status Mismatch Report")
                        lazada_result = st.session_state.lazada_results
                        
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
                        action_options = ["All"] + list(lazada_result['Action Required'].unique())
                        selected_action = st.selectbox("Filter by Action Required:", action_options, key="laz_filter")
                        filtered_laz = lazada_result if selected_action == "All" else lazada_result[lazada_result['Action Required'] == selected_action]
                        st.dataframe(filtered_laz, use_container_width=True)
                        
                    elif "Shopee" in name:
                        st.markdown(f"### 🛒 Shopee {country} Consolidated Stock Report")
                        shopee_pid_df = st.session_state.shopee_pid_results
                        shopee_sku_df = st.session_state.shopee_sku_results
                        
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
                        shopee_sub_tab1, shopee_sub_tab2 = st.tabs(["PID Level Consolidation", "SKU Level Validation Detail"])
                        with shopee_sub_tab1:
                            st.dataframe(shopee_pid_df, use_container_width=True)
                        with shopee_sub_tab2:
                            shopee_actions = ["All"] + list(shopee_sku_df['Action Required'].unique())
                            selected_shopee_act = st.selectbox("Filter Shopee SKU Action Required:", shopee_actions, key="shopee_filter")
                            filtered_shopee_sku = shopee_sku_df if selected_shopee_act == "All" else shopee_sku_df[shopee_sku_df['Action Required'] == selected_shopee_act]
                            st.dataframe(filtered_shopee_sku, use_container_width=True)
                            
                    elif "TikTok" in name:
                        st.markdown(f"### 🛒 TikTok {country} Consolidated Stock Report")
                        tiktok_pid_df = st.session_state.tiktok_pid_results
                        tiktok_sku_df = st.session_state.tiktok_sku_results
                        
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
                        tiktok_sub_tab1, tiktok_sub_tab2 = st.tabs(["PID Level Consolidation", "SKU Level Validation Detail"])
                        with tiktok_sub_tab1:
                            st.dataframe(tiktok_pid_df, use_container_width=True)
                        with tiktok_sub_tab2:
                            tiktok_actions = ["All"] + list(tiktok_sku_df['Action Required'].unique())
                            selected_tiktok_act = st.selectbox("Filter TikTok SKU Action Required:", tiktok_actions, key="tiktok_filter")
                            filtered_tiktok_sku = tiktok_sku_df if selected_tiktok_act == "All" else tiktok_sku_df[tiktok_sku_df['Action Required'] == selected_tiktok_act]
                            st.dataframe(filtered_tiktok_sku, use_container_width=True)
    else:
        st.info("Run validation to see results.")

# Tab 2: Downloads
with tab2:
    st.markdown("### Download Current Report")
    report_path = st.session_state.get("report_path")
    report_fname = st.session_state.get("report_fname")
    
    if report_path and os.path.exists(report_path):
        size_mb = round(os.path.getsize(report_path) / (1024 * 1024), 2)
        st.info(f"File: **{report_fname}** ({size_mb} MB)")
        with open(report_path, "rb") as f:
            st.download_button(
                "Download Excel Report",
                data=f.read(),
                file_name=report_fname,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="dl_current"
            )
    else:
        st.info("Run validation first to generate a report.")

# Tab 3: Saved Reports
def _list_saved_reports():
    files = []
    if os.path.exists(REPORT_DIR):
        for f in os.listdir(REPORT_DIR):
            if f.endswith(".xlsx"):
                fpath = os.path.join(REPORT_DIR, f)
                mtime = os.path.getmtime(fpath)
                size_mb = round(os.path.getsize(fpath) / (1024 * 1024), 2)
                files.append((f, fpath, mtime, size_mb))
        files.sort(key=lambda x: x[2], reverse=True)
    return files

with tab3:
    st.markdown("### All Saved Reports")
    st.caption("Reports are saved to the server and remain available. You can download any previous report here.")
    
    saved = _list_saved_reports()
    if not saved:
        st.info("No saved reports yet. Run validation to generate one.")
    else:
        for fname, fpath, mtime, size_mb in saved:
            col1, col2, col3 = st.columns([5, 2, 2])
            col1.write(f"**{fname}**")
            col2.write(f"{size_mb} MB")
            ts = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            col3.write(ts)
            with open(fpath, "rb") as f:
                st.download_button(
                    "Download " + fname,
                    data=f.read(),
                    file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_" + fname,
                )
            st.markdown("---")
            
        if st.button("Clear all saved reports", type="secondary"):
            for _, fpath, _, _ in saved:
                try:
                    os.remove(fpath)
                except Exception:
                    pass
            st.success("All saved reports cleared.")
            st.rerun()

# Step 3: Export & Push Validation Report back to GitHub
st.markdown("---")
st.subheader("📤 Step 3: Commit Reports back to GitHub Repository")

if not github_repo:
    st.info("ℹ️ Configure GitHub integration settings in the sidebar to commit validation reports directly back to your repository.")
else:
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
                df_to_push = None
                file_name = ""
                
                if report_type == "Lazada SKU Level" and st.session_state.lazada_results is not None:
                    df_to_push = st.session_state.lazada_results
                    file_name = "lazada_validation_report.csv"
                elif report_type == "Shopee PID Consolidated" and st.session_state.shopee_pid_results is not None:
                    df_to_push = st.session_state.shopee_pid_results
                    file_name = "shopee_consolidated_pid_report.csv"
                elif report_type == "Shopee SKU Detail" and st.session_state.shopee_sku_results is not None:
                    df_to_push = st.session_state.shopee_sku_results
                    file_name = "shopee_sku_validation_detail.csv"
                elif report_type == "TikTok PID Consolidated" and st.session_state.tiktok_pid_results is not None:
                    df_to_push = st.session_state.tiktok_pid_results
                    file_name = "tiktok_consolidated_pid_report.csv"
                elif report_type == "TikTok SKU Detail" and st.session_state.tiktok_sku_results is not None:
                    df_to_push = st.session_state.tiktok_sku_results
                    file_name = "tiktok_sku_validation_detail.csv"
                    
                if df_to_push is not None:
                    csv_str = df_to_push.to_csv(index=False)
                    content_bytes = csv_str.encode('utf-8')
                    target_path = f"{github_output_folder}/{file_name}" if github_output_folder else file_name
                    
                    existing_url = f"https://api.github.com/repos/{github_repo}/contents/{target_path}?ref={github_branch}"
                    headers = github_get_headers(github_pat)
                    resp = requests.get(existing_url, headers=headers)
                    sha = None
                    if resp.status_code == 200:
                        sha = resp.json().get('sha')
                        
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
                        st.success(f"Successfully committed '{file_name}' to GitHub! [View Commit]({details})")
                    else:
                        error_count += 1
                        st.error(f"Failed to commit '{file_name}': {details}")
                        
            if success_count > 0:
                st.toast(f"Successfully uploaded {success_count} reports!")
            if error_count > 0:
                st.toast("Some uploads failed. Check error messages.", icon="⚠️")
