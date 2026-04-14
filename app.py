"""
CERCLI HR DATA MIGRATION SYSTEM — Streamlit Web UI
====================================================

Complete end-to-end application:
1. Upload messy CSVs
2. Preview & profile data
3. Review LLM column mappings
4. Run compliance checks
5. Export clean canonical data

This is the user-facing interface for the entire RAG + compliance system.
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import os
import tempfile
from datetime import date
from typing import Dict, List, Optional, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion import DataIngestionPipeline
from src.mapper import ColumnMapper
from src.compliance.integration import ComplianceIntegration
from src.schema import CANONICAL_SCHEMA
from src.compliance.rules import get_all_rules

# =====================================================================
# PAGE CONFIG
# =====================================================================

st.set_page_config(
    page_title="Cercli HR Data Migration",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
    <style>
    .main {
        padding: 20px;
    }
    .stTabs [data-baseweb="tab-list"] button {
        font-size: 16px;
        padding: 10px 20px;
    }
    .violation-critical {
        padding: 12px;
        border-left: 5px solid #DC143C;
        background-color: #FFE4E1;
        border-radius: 5px;
        margin: 8px 0;
        color: #333;
    }
    .violation-error {
        padding: 12px;
        border-left: 5px solid #FF6347;
        background-color: #FFF0F5;
        border-radius: 5px;
        margin: 8px 0;
        color: #333;
    }
    .violation-warning {
        padding: 12px;
        border-left: 5px solid #FF8C00;
        background-color: #FFF8DC;
        border-radius: 5px;
        margin: 8px 0;
        color: #333;
    }
    .violation-text {
        color: #000;
        font-size: 14px;
        line-height: 1.6;
    }
    </style>
    """, unsafe_allow_html=True)

# =====================================================================
# SESSION STATE MANAGEMENT
# =====================================================================

# Initialize temp_uploads folder - use system temp directory as fallback
try:
    # Try project directory first
    UPLOAD_DIR = Path(__file__).parent / "temp_uploads"
    os.makedirs(str(UPLOAD_DIR), exist_ok=True)
except Exception:
    # Fallback to system temp directory
    UPLOAD_DIR = Path(tempfile.gettempdir()) / "cerclo_uploads"
    os.makedirs(str(UPLOAD_DIR), exist_ok=True)

if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = None

if "profiles" not in st.session_state:
    st.session_state.profiles = None

if "mappings" not in st.session_state:
    st.session_state.mappings = None

if "violations" not in st.session_state:
    st.session_state.violations = None

if "data_frames" not in st.session_state:
    st.session_state.data_frames = {}

# =====================================================================
# HELPER FUNCTIONS
# =====================================================================

def upload_and_profile_csvs(upload_folder: str = None) -> Tuple[Dict, Dict]:
    """Upload CSVs and profile them."""
    
    if upload_folder is None:
        upload_folder = str(UPLOAD_DIR)
    
    # Ensure folder exists using os.makedirs
    try:
        os.makedirs(upload_folder, exist_ok=True)
    except Exception as e:
        st.error(f"Cannot create upload folder: {e}\n\nUsing fallback directory...")
        upload_folder = str(Path(tempfile.gettempdir()) / "cerclo_uploads")
        os.makedirs(upload_folder, exist_ok=True)
    
    # Get uploaded files
    uploaded_files = st.file_uploader(
        "📤 Upload CSV Files",
        type="csv",
        accept_multiple_files=True,
        help="Upload messy HR CSV files (employee_master, payroll_run, leave_records, etc.)"
    )
    
    if not uploaded_files:
        return None, {}
    
    # Save files temporarily
    saved_paths = {}
    for uploaded_file in uploaded_files:
        save_path = Path(upload_folder) / uploaded_file.name
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        saved_paths[uploaded_file.name] = str(save_path)
    
    # Profile CSVs
    try:
        ingestion = DataIngestionPipeline(upload_folder)
        profiles = ingestion.ingest_all()
        
        # Also load the raw dataframes
        data_frames = {}
        for file_name, profile in profiles.items():
            df = pd.read_csv(saved_paths.get(f"{file_name}.csv", f"{upload_folder}/{file_name}.csv"))
            data_frames[file_name] = df
        
        return profiles, data_frames
    
    except Exception as e:
        st.error(f"❌ Error profiling CSVs: {e}")
        return None, {}


def display_column_profile(profile: Dict, file_name: str):
    """Display a profile for one CSV file."""
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 Rows", profile["row_count"])
    with col2:
        st.metric("📋 Columns", profile["column_count"])
    with col3:
        st.metric("💾 Size (KB)", profile.get("size_kb", 0))
    with col4:
        st.metric("✓ Completeness", f"{profile.get('completeness', 0):.0f}%")
    
    # Show sample columns
    if "columns" in profile:
        st.write("**Sample Columns:**")
        cols_display = profile["columns"][:10]  # First 10
        
        col_data = []
        for col in cols_display:
            col_data.append({
                "Column Name": col["name"],
                "Type": col.get("inferred_type", "unknown"),
                "Non-Null": f"{col.get('non_null_count', 0)}/{profile['row_count']}",
                "Sample": str(col.get("sample_value", ""))[:30]
            })
        
        st.dataframe(pd.DataFrame(col_data), use_container_width=True)


def display_mapping_editor(mappings: List, data_frames: Dict) -> Dict:
    """Interactive table to review and edit column mappings."""
    
    if not mappings:
        st.info("No mappings generated yet. Run the mapper first.")
        return {}
    
    st.subheader("🗺️ Column Mapping Review")
    st.write("Review and confirm the LLM's suggested column mappings. Edit if needed.")
    
    # Build editable dataframe
    mapping_data = []
    for m in mappings:
        mapping_data.append({
            "Source Column": m.source_column,
            "Target Field": m.suggested_target,
            "Table": m.target_table,
            "Confidence %": int(m.confidence * 100),
            "Reasoning": m.reasoning[:100] + "..." if len(m.reasoning) > 100 else m.reasoning,
            "Approved": True  # Checkbox
        })
    
    df_mappings = pd.DataFrame(mapping_data)
    
    # Editable data editor
    edited_df = st.data_editor(
        df_mappings,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "Confidence %": st.column_config.ProgressColumn(
                "Confidence",
                min_value=0,
                max_value=100,
            ),
            "Approved": st.column_config.CheckboxColumn(help="Check to approve mapping"),
        }
    )
    
    # Convert back to mappings (with user edits)
    reviewed_mappings = {}
    for idx, row in edited_df.iterrows():
        if row["Approved"]:
            reviewed_mappings[row["Source Column"]] = row["Target Field"]
    
    return reviewed_mappings


def run_compliance_checks(data_frames: Dict, reviewed_mappings: Dict) -> Optional[Dict]:
    """Run compliance checks on the data."""
    
    # For now, use the integration with sample preparation
    try:
        integration = ComplianceIntegration(jurisdiction="UAE")
        
        # Prepare data for compliance checking
        employee_data = []
        contract_data = []
        leave_data = []
        payroll_data = []
        
        # Helper function to safely get values from pandas Series
        def get_str(row, key, default="Unknown"):
            val = row.get(key, default)
            if pd.isna(val):
                return default
            return str(val).strip() if val else default
        
        def get_float(row, key, default=0.0):
            val = row.get(key, default)
            if pd.isna(val):
                return float(default)
            try:
                return float(val)
            except:
                return float(default)
        
        def get_int(row, key, default=0):
            val = row.get(key, default)
            if pd.isna(val):
                return int(default)
            try:
                return int(val)
            except:
                return int(default)
        
        # Build reverse mapping: canonical_field -> source_column
        # reviewed_mappings is: source_column -> canonical_field
        canonical_to_source = {v: k for k, v in reviewed_mappings.items()} if reviewed_mappings else {}
        
        # Try to extract from available dataframes
        if "employee_master" in data_frames:
            df_emp = data_frames["employee_master"]
            for idx, row in df_emp.iterrows():
                # Extract with proper field handling for compliance rules
                # CSV uses: emp_no, emp_nm, joining_dt, annual_leave_bal, carry_fwd_bal, yr_of_service, visa_exp, national_id, visa_typ, desig, basic_sal, housing_all, trans_all
                
                emp_id = get_str(row, canonical_to_source.get("employee_id", "emp_no"), f"EMP{idx}")
                emp_name = get_str(row, canonical_to_source.get("name", "emp_nm"), "Unknown")
                national_id = row.get(canonical_to_source.get("national_id", "national_id"))
                if pd.isna(national_id):
                    national_id = None
                else:
                    national_id = str(national_id).strip() if national_id else None
                
                # Parse hire_date from joining_dt
                try:
                    hire_date = pd.to_datetime(row.get(canonical_to_source.get("hire_date", "joining_dt"), date.today())).date()
                except:
                    hire_date = date.today()
                
                # Parse visa_expiry
                try:
                    visa_exp_val = row.get(canonical_to_source.get("visa_expiry", "visa_exp"))
                    if pd.notna(visa_exp_val):
                        visa_expiry = pd.to_datetime(visa_exp_val).date()
                    else:
                        visa_expiry = None
                except:
                    visa_expiry = None
                
                # Calculate tenure in years
                tenure_years = get_float(row, canonical_to_source.get("tenure_years", "yr_of_service"), 0.0)
                
                employee_data.append({
                    "employee_id": emp_id,
                    "name": emp_name,
                    "employee_name": emp_name,
                    "national_id": national_id,
                    "nationality": get_str(row, canonical_to_source.get("nationality", "nationality_cd"), "AE"),
                    "hire_date": hire_date,
                    "tenure_years": tenure_years,
                    "visa_type": get_str(row, canonical_to_source.get("visa_type", "visa_typ"), "Employment"),
                    "visa_expiry": visa_expiry,
                    "job_title": get_str(row, canonical_to_source.get("job_title", "desig"), ""),
                    "annual_leave_entitlement": get_float(row, canonical_to_source.get("annual_leave_entitlement", "annual_leave_bal"), 30),
                    "leave_carried_forward": get_float(row, canonical_to_source.get("leave_carried_forward", "carry_fwd_bal"), 0),
                    "base_salary": get_float(row, canonical_to_source.get("base_salary", "basic_sal"), 0),
                    "fixed_allowances": get_float(row, canonical_to_source.get("housing_allowance", "housing_all"), 0) + get_float(row, canonical_to_source.get("transport_allowance", "trans_all"), 0),
                })
        
        if "payroll_run" in data_frames:
            df_payroll = data_frames["payroll_run"]
            for idx, row in df_payroll.iterrows():
                emp_id = get_str(row, canonical_to_source.get("employee_id", "emp_no"), f"EMP{idx}")
                contract_data.append({
                    "employee_id": emp_id,
                    "base_salary": get_float(row, canonical_to_source.get("base_salary", "basic_sal"), 0),
                    "housing_allowance": get_float(row, canonical_to_source.get("housing_allowance", "housing_all"), 0),
                    "transport_allowance": get_float(row, canonical_to_source.get("transport_allowance", "trans_all"), 0),
                    "overtime_hours_weekday": get_float(row, canonical_to_source.get("overtime_hours_weekday", "ot_hours_weekday"), 0),
                    "overtime_hours_friday": get_float(row, canonical_to_source.get("overtime_hours_friday", "ot_hours_friday"), 0),
                    "overtime_rate": get_float(row, canonical_to_source.get("overtime_rate", "ot_rate"), 0),
                    "eos_gratuity_calculated": get_float(row, canonical_to_source.get("eos_gratuity_calculated", "eos_gratuity_calculated"), 0),
                    "hourly_rate": get_float(row, canonical_to_source.get("base_salary", "basic_sal"), 0) / 240,  # Standard 240 working hours
                })
        
        if "leave_records" in data_frames:
            df_leave = data_frames["leave_records"]
            for idx, row in df_leave.iterrows():
                emp_id = get_str(row, canonical_to_source.get("employee_id", "emp_no"), f"EMP{idx}")
                leave_data.append({
                    "employee_id": emp_id,
                    "annual_leave_entitlement": get_float(row, canonical_to_source.get("annual_leave_entitlement", "annual_entitlement"), 30),
                    "annual_leave_used": get_float(row, canonical_to_source.get("annual_leave_used", "days_taken"), 0),
                    "sick_leave_entitlement": get_float(row, canonical_to_source.get("sick_leave_entitlement", "sick_leave_entitlement"), 10),
                    "annual_leave_carried_forward": get_float(row, canonical_to_source.get("annual_leave_carried_forward", "carry_forward"), 0),
                    "leave_balance": get_float(row, canonical_to_source.get("leave_balance", "leave_balance"), 0),
                })
        
        # Run checks
        violations = integration.check_company_data(
            employee_data or [{"employee_id": "N/A", "name": "Sample"}],
            contract_data or [{"employee_id": "N/A", "base_salary": 0}],
            leave_data or [{"employee_id": "N/A", "annual_leave_entitlement": 30}],
            payroll_data or [{"employee_id": "N/A", "overtime_rate": 75}]
        )
        
        report = integration.generate_compliance_report(violations)
        
        return {
            "violations": violations,
            "report": report,
            "employee_count": len(employee_data),
            "violation_count": len(violations),
            "employee_data": employee_data,  # Include for debugging
            "employee_names": list(set([e.get("name", "Unknown") for e in employee_data]))
        }
    
    except Exception as e:
        st.error(f"❌ Error running compliance checks: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None


def export_results(data_frames: Dict, mappings: Dict, compliance_result: Optional[Dict]):
    """Export clean data and reports."""
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Export mapped CSV
        if data_frames:
            # Safely rename columns - only map those that exist in each dataframe
            renamed_dfs = []
            for df in data_frames.values():
                # Filter mappings to only include columns that exist in this dataframe
                valid_mappings = {k: v for k, v in mappings.items() if k in df.columns}
                # Rename columns and handle any duplicate resulting column names
                renamed_df = df.rename(columns=valid_mappings)
                # Drop any completely duplicate columns (keep first occurrence)
                renamed_df = renamed_df.loc[:, ~renamed_df.columns.duplicated(keep='first')]
                renamed_dfs.append(renamed_df)
            
            export_df = pd.concat(renamed_dfs, ignore_index=True)
            csv_buffer = export_df.to_csv(index=False)
            
            st.download_button(
                label="📥 Download Mapped CSV",
                data=csv_buffer,
                file_name="cercli_clean_data.csv",
                mime="text/csv",
                help="Download clean data with canonical column names"
            )
    
    with col2:
        # Export compliance report
        if compliance_result:
            violations_text = "COMPLIANCE VIOLATIONS REPORT\n"
            violations_text += "=" * 80 + "\n\n"
            
            for v in compliance_result["violations"]:
                violations_text += f"{v.severity.upper()}: {v.rule_name}\n"
                violations_text += f"  Employee: {v.employee_name}\n"
                violations_text += f"  Message: {v.message}\n"
                violations_text += f"  Recommendation: {v.recommendation}\n"
                violations_text += f"  Law Reference: {v.law_reference}\n\n"
            
            st.download_button(
                label="📋 Download Compliance Report",
                data=violations_text,
                file_name="compliance_violations.txt",
                mime="text/plain",
                help="Download detailed compliance report with law references"
            )
    
    with col3:
        # Export mapping summary
        if mappings:
            mappings_json = pd.Series(mappings).to_json()
            st.download_button(
                label="🗺️ Download Mappings (JSON)",
                data=mappings_json,
                file_name="column_mappings.json",
                mime="application/json",
                help="Download column mapping configuration for reuse"
            )


# =====================================================================
# MAIN APP
# =====================================================================

def main():
    # Header
    st.title("🏢 Cercli HR Data Migration System")
    st.markdown("**Transform messy HR data into clean, compliant canonical format**")
    
    st.divider()
    
    # Tabs for different sections
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📤 Upload & Profile",
        "🗺️ Column Mapping",
        "✅ Compliance Check",
        "💾 Export Results",
        "📊 System Info"
    ])
    
    # ===== TAB 1: UPLOAD & PROFILE =====
    with tab1:
        st.header("Step 1: Upload CSV Files")
        st.write("Upload your messy HR CSV files. The system will automatically profile them and identify column types.")
        
        # File uploader at top level (this is key!)
        uploaded_files = st.file_uploader(
            "📤 Upload CSV Files",
            type="csv",
            accept_multiple_files=True,
            key="file_uploader_main",
            help="Upload messy HR CSV files (employee_master, payroll_run, leave_records, etc.)"
        )
        
        # Process files automatically when they're uploaded
        if uploaded_files:
            with st.spinner("📂 Loading and profiling CSV files..."):
                try:
                    # Save files to temp directory
                    upload_folder = str(UPLOAD_DIR)
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    saved_paths = {}
                    for uploaded_file in uploaded_files:
                        save_path = Path(upload_folder) / uploaded_file.name
                        with open(save_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        saved_paths[uploaded_file.name] = str(save_path)
                    
                    # Profile CSVs
                    ingestion = DataIngestionPipeline(upload_folder)
                    profiles = ingestion.ingest_all()
                    
                    # Load raw dataframes
                    data_frames = {}
                    for file_name, profile in profiles.items():
                        df = pd.read_csv(saved_paths.get(f"{file_name}.csv", f"{upload_folder}/{file_name}.csv"))
                        data_frames[file_name] = df
                    
                    # Store in session state
                    st.session_state.profiles = profiles
                    st.session_state.data_frames = data_frames
                    st.success(f"✅ Loaded {len(profiles)} CSV files successfully!")
                    
                except Exception as e:
                    st.error(f"❌ Error loading files: {e}")
        
        # Display profiles if available
        if st.session_state.profiles:
            st.subheader("📊 Data Profiles")
            
            for file_name, profile in st.session_state.profiles.items():
                with st.expander(f"📋 {file_name}.csv", expanded=True):
                    display_column_profile(profile, file_name)
                    
                    # Show preview
                    if file_name in st.session_state.data_frames:
                        st.write("**Data Preview:**")
                        st.dataframe(
                            st.session_state.data_frames[file_name].head(5),
                            use_container_width=True
                        )
    
    # ===== TAB 2: COLUMN MAPPING =====
    with tab2:
        st.header("Step 2: Review Column Mappings")
        st.write("The LLM mapper has suggested mappings for your columns. Review and approve them below.")
        
        if not st.session_state.profiles:
            st.info("⚠️ Please upload files first (Tab 1)")
        else:
            # Show available columns in uploaded files
            with st.expander("📋 Available Columns in Your Files", expanded=False):
                for file_name, profile in st.session_state.profiles.items():
                    st.write(f"**{file_name}.csv:**")
                    columns = [c["name"] for c in profile.get("columns", [])]
                    st.write(", ".join(columns))
                    st.divider()
            
            # Show available LLM options
            with st.expander("🎯 LLM Configuration", expanded=False):
                st.markdown("""
                **Available Modes:**
                1. **Ollama (Local)** - Deepseek or Qwen models if running on localhost:11434
                2. **Claude (Cloud)** - Requires ANTHROPIC_API_KEY environment variable
                3. **Demo Mode** - Fast heuristic matching for testing
                
                **To use Ollama:**
                ```bash
                ollama serve
                ```
                
                **To use Claude:**
                ```bash
                $env:ANTHROPIC_API_KEY='sk-ant-your-key-here'
                ```
                """)
            
            if st.button("🤖 Run LLM Column Mapper", key="mapper_btn"):
                with st.spinner("🧠 Running LLM mapper... checking available models"):
                    try:
                        mapper = ColumnMapper()
                        mappings = mapper.map_columns_with_llm(
                            st.session_state.profiles,
                            retriever=None  # No RAG in UI version (FAISS not installed)
                        )
                        st.session_state.mappings = mappings
                        if mappings:
                            st.success(f"✅ Mapping complete! Generated {len(mappings)} mappings")
                        else:
                            st.warning("⚠️ No mappings generated. Check the configuration above.")
                    except Exception as e:
                        st.error(f"❌ Mapping failed: {e}")
            
            # Display mapping editor
            if st.session_state.mappings:
                reviewed_mappings = display_mapping_editor(
                    st.session_state.mappings,
                    st.session_state.data_frames
                )
                
                if reviewed_mappings:
                    st.success(f"✅ Approved {len(reviewed_mappings)} mappings")
                    st.session_state.reviewed_mappings = reviewed_mappings
    
    # ===== TAB 3: COMPLIANCE CHECK =====
    with tab3:
        st.header("Step 3: Run Compliance Checks")
        st.write("Automatically check your HR data against UAE labor law requirements.")
        
        if not st.session_state.data_frames:
            st.info("⚠️ Please upload files first (Tab 1)")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                jurisdiction = st.selectbox(
                    "📍 Select Jurisdiction",
                    ["UAE", "KSA", "Other"]
                )
            
            with col2:
                if st.button("✅ Run Compliance Checks", key="compliance_btn"):
                    with st.spinner("🔍 Running compliance checks..."):
                        compliance_result = run_compliance_checks(
                            st.session_state.data_frames,
                            getattr(st.session_state, 'reviewed_mappings', {})
                        )
                        
                        if compliance_result:
                            st.session_state.violations = compliance_result
                            st.success(f"✅ Check complete! Found {compliance_result['violation_count']} violations")
            
            # Display violations
            if st.session_state.violations:
                result = st.session_state.violations
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    critical = len([v for v in result["violations"] if v.severity.upper() == "CRITICAL"])
                    st.metric("🚨 Critical", critical)
                with col2:
                    errors = len([v for v in result["violations"] if v.severity.upper() == "ERROR"])
                    st.metric("❌ Errors", errors)
                with col3:
                    warnings = len([v for v in result["violations"] if v.severity.upper() == "WARNING"])
                    st.metric("⚠️ Warnings", warnings)
                
                st.subheader("Violations by Employee")
                
                # Group by employee
                violations_by_emp = {}
                for v in result["violations"]:
                    emp_name = v.employee_name
                    if emp_name not in violations_by_emp:
                        violations_by_emp[emp_name] = []
                    violations_by_emp[emp_name].append(v)
                
                for emp_name, viols in violations_by_emp.items():
                    with st.expander(f"👤 {emp_name} ({len(viols)} violations)", expanded=False):
                        for v in viols:
                            severity_class = f"violation-{v.severity.lower()}"
                            severity_icon = {
                                "critical": "🚨",
                                "error": "❌",
                                "warning": "⚠️"
                            }.get(v.severity.lower(), "•")
                            
                            st.markdown(f"""
                                <div class="{severity_class}">
                                <div class="violation-text">
                                <b>{severity_icon} {v.rule_name}</b><br/>
                                <b>Message:</b> {v.message}<br/>
                                <b>Recommendation:</b> {v.recommendation}<br/>
                                <b>Law Reference:</b> <code>{v.law_reference}</code>
                                </div>
                                </div>
                                """, unsafe_allow_html=True)
                
                # Debug: Show what columns were actually found
                with st.expander("🔍 Debug Info (Column Mappings Used)", expanded=False):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Approved Mappings:**")
                        if hasattr(st.session_state, 'reviewed_mappings') and st.session_state.reviewed_mappings:
                            mapping_display = {src: target for src, target in st.session_state.reviewed_mappings.items()}
                            st.json(mapping_display)
                        else:
                            st.write("❌ No mappings applied - run column mapper first")
                    
                    with col2:
                        st.write("**Extracted Employee Names:**")
                        employee_names = result.get("employee_names", ["Unknown"])
                        if employee_names and employee_names != ["Unknown"]:
                            for name in employee_names[:5]:  # Show first 5
                                st.write(f"✅ {name}")
                        else:
                            st.warning("⚠️ Employee names not found! Check that 'name' column was mapped.")
    
    # ===== TAB 4: EXPORT RESULTS =====
    with tab4:
        st.header("Step 4: Export Results")
        st.write("Download your clean data, compliance report, and mapping configuration.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📥 Available Exports")
            
            export_ready = {
                "Canonical CSV": bool(st.session_state.data_frames),
                "Compliance Report": bool(st.session_state.violations),
                "Mapping Config": bool(st.session_state.mappings)
            }
            
            for export_name, is_ready in export_ready.items():
                status = "✅ Ready" if is_ready else "⏳ Pending"
                st.write(f"- {export_name}: {status}")
        
        with col2:
            st.subheader("📊 Export Summary")
            if st.session_state.data_frames:
                total_rows = sum(len(df) for df in st.session_state.data_frames.values())
                st.metric("Total Rows", total_rows)
            if st.session_state.violations:
                st.metric("Violations Found", len(st.session_state.violations["violations"]))
            if st.session_state.mappings:
                st.metric("Column Mappings", len(st.session_state.mappings))
        
        st.divider()
        
        export_results(
            st.session_state.data_frames,
            getattr(st.session_state, 'reviewed_mappings', {}),
            st.session_state.violations
        )
    
    # ===== TAB 5: SYSTEM INFO =====
    with tab5:
        st.header("📊 System Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🏗️ Architecture")
            st.write("""
            **6-Step Pipeline:**
            1. Data Ingestion (CSV profiling)
            2. RAG System (embeddings + retrieval)
            3. Column Mapping (LLM with Ollama/Claude)
            4. Store Learnings (self-improvement)
            5. Compliance Checks (7 UAE law rules)
            6. Report Generation
            """)
        
        with col2:
            st.subheader("⚖️ Compliance Rules")
            rules = get_all_rules()
            for rule in rules:
                st.write(f"- {rule.name} (Article {rule.law_reference})")
        
        st.divider()
        
        st.subheader("📚 Technology Stack")
        st.write("""
        - **Data Processing**: pandas, numpy
        - **ML**: sentence-transformers (embeddings)
        - **Vector DB**: FAISS (semantic search)
        - **LLM**: Claude 3.5 Sonnet + Ollama (fallback)
        - **UI**: Streamlit
        - **Compliance**: 7 UAE labor law rules
        """)
        
        st.divider()
        
        st.subheader("👨‍💻 About This Project")
        st.write("""
        Built to solve real compliance problems for MENA HR platforms like Cercli.
        
        **What it does:**
        - Transforms messy HR data into clean canonical format
        - Maps arbitrary column names to standard schema using LLM + RAG
        - Automates compliance checking against UAE/KSA labor laws
        - Generates actionable recommendations
        
        **Key Innovation:** True RAG architecture instead of prompt stuffing
        """)


if __name__ == "__main__":
    main()
