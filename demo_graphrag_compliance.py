"""
DEMO: GraphRAG-lite + Compliance Checking
==========================================

This demonstrates the full workflow:
1. Load employee data from CSV
2. Convert to compliance check format
3. Use GraphRAG to retrieve law article context
4. Run compliance checks
5. Generate violation report with law citations
"""

import pandas as pd
import sys
from pathlib import Path
from datetime import date, timedelta
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rag.graph_retriever import build_uae_labor_law_graph, GraphRAGRetriever
from compliance.checker import ComplianceChecker
from compliance.rules import Severity


def load_employee_data(employee_csv, payroll_csv, leave_csv):
    """Load and merge employee data from CSVs."""
    
    employees = pd.read_csv(employee_csv)
    payroll = pd.read_csv(payroll_csv)
    leaves = pd.read_csv(leave_csv)
    
    # Group by employee
    employee_data = {}
    
    for _, emp_row in employees.iterrows():
        emp_no = emp_row['emp_no']
        
        # Get payroll data
        payroll_data = payroll[payroll['emp_no'] == emp_no]
        latest_payroll = payroll_data.iloc[0] if len(payroll_data) > 0 else {}
        
        # Get leave data
        leave_data = leaves[leaves['emp_no'] == emp_no]
        
        # Construct employee profile
        profile = {
            'employee_id': emp_no,
            'employee_name': emp_row['emp_nm'],
            'nationality': emp_row['nationality_cd'],
            'hire_date': pd.to_datetime(emp_row['joining_dt']).date() if pd.notna(emp_row['joining_dt']) else None,
            'tenure_years': emp_row['yr_of_service'],
            'base_salary': float(emp_row['basic_sal']),
            'fixed_allowances': float(emp_row['housing_all']) + float(emp_row['trans_all']),
            'job_title': emp_row['desig'],
            'probation_period_months': emp_row.get('probation_end', 0),
            'national_id': emp_row['national_id'] if pd.notna(emp_row['national_id']) else None,
            'visa_type': emp_row['visa_typ'] if pd.notna(emp_row['visa_typ']) else None,
            'visa_expiry': pd.to_datetime(emp_row['visa_exp']).date() if pd.notna(emp_row['visa_exp']) else None,
            'annual_leave_entitlement': float(emp_row['annual_leave_bal']),
            'leave_carried_forward': float(emp_row['carry_fwd_bal']) if pd.notna(emp_row['carry_fwd_bal']) else 0,
            
            # From payroll
            'hourly_rate': float(latest_payroll.get('basic_sal', 0)) / 240,  # Assume 240 working hours/month
            'overtime_rate': float(latest_payroll.get('ot_rate', 0)),
            'overtime_hours_weekday': float(latest_payroll.get('ot_hours_weekday', 0)),
            'overtime_hours_friday': float(latest_payroll.get('ot_hours_friday', 0)),
            'eos_gratuity_calculated': float(latest_payroll.get('eos_gratuity_calculated', 0)) if 'eos_gratuity_calculated' in latest_payroll and pd.notna(latest_payroll.get('eos_gratuity_calculated')) else 0,
        }
        
        employee_data[emp_no] = profile
    
    return employee_data


def format_violation(violation, law_context):
    """Format violation with law context."""
    
    lines = []
    lines.append(f"\n{'='*70}")
    lines.append(f"🚨 VIOLATION: {violation['rule_name']} (Severity: {violation['severity'].upper()})")
    lines.append(f"{'='*70}")
    
    lines.append(f"Employee: {violation['employee_name']} ({violation['employee_id']})")
    lines.append(f"Issue: {violation['message']}")
    lines.append(f"Current Value: {violation['affected_value']}")
    lines.append(f"Required Value: {violation['required_value']}")
    lines.append(f"Recommendation: {violation['recommendation']}")
    
    if 'law_reference' in violation:
        lines.append(f"\n📚 Legal Reference:")
        lines.append(f"   {violation['law_reference']}")
    
    return "\n".join(lines)


def run_compliance_demo():
    """Main demo."""
    
    print("\n" + "="*70)
    print("🏛️  CERCLI COMPLIANCE DEMONSTRATION")
    print("GraphRAG-lite + UAE Labor Law Compliance Checking")
    print("="*70)
    
    # 1. Build knowledge graph
    print("\n📚 Building UAE Labor Law Knowledge Graph...")
    kg = build_uae_labor_law_graph()
    retriever = GraphRAGRetriever(kg)
    print(f"✅ Built graph with {kg.graph.number_of_nodes()} entities and {kg.graph.number_of_edges()} relationships")
    
    # 2. Load employee data
    print("\n📂 Loading employee data...")
    dataset_dir = Path(__file__).parent / "datasets"
    
    employee_data = load_employee_data(
        dataset_dir / "employee_master.csv",
        dataset_dir / "payroll_run.csv",
        dataset_dir / "leave_records.csv"
    )
    print(f"✅ Loaded {len(employee_data)} employees")
    
    # 3. Run compliance checks
    print("\n⚖️  Running compliance checks...")
    checker = ComplianceChecker(jurisdiction="UAE")
    
    all_violations = []
    
    for emp_id, emp_profile in employee_data.items():
        violations = checker.check_employee(
            employee_id=emp_profile['employee_id'],
            employee_name=emp_profile['employee_name'],
            employee_data=emp_profile
        )
        
        for violation in violations:
            # Get law context from graph
            entity_name = violation['rule_name'].replace('_', ' ').split()[0]
            
            all_violations.append({
                'employee_id': emp_profile['employee_id'],
                'employee_name': emp_profile['employee_name'],
                **violation.__dict__
            })
    
    # 4. Generate report
    print("\n" + "="*70)
    print(f"📊 COMPLIANCE REPORT - Found {len(all_violations)} Violations")
    print("="*70)
    
    # Group by severity
    by_severity = {}
    for violation in all_violations:
        severity = violation['severity'].value if hasattr(violation['severity'], 'value') else violation['severity']
        if severity not in by_severity:
            by_severity[severity] = []
        by_severity[severity].append(violation)
    
    # Summary
    print(f"\n📈 VIOLATION SUMMARY:")
    print(f"   🚨 CRITICAL: {len(by_severity.get('critical', []))} violations")
    print(f"   ❌ ERROR:    {len(by_severity.get('error', []))} violations")
    print(f"   ⚠️  WARNING: {len(by_severity.get('warning', []))} violations")
    print(f"   TOTAL:      {len(all_violations)} violations")
    
    # Detailed violations by severity
    severity_order = ['critical', 'error', 'warning']
    
    for severity_level in severity_order:
        violations = by_severity.get(severity_level, [])
        if not violations:
            continue
        
        icon = {'critical': '🚨', 'error': '❌', 'warning': '⚠️'}[severity_level]
        print(f"\n\n{icon} {severity_level.upper()} VIOLATIONS ({len(violations)}):")
        print("-" * 70)
        
        for violation in violations[:5]:  # Show first 5 per severity
            print(f"\n  {violation['employee_name']} ({violation['employee_id']})")
            print(f"  Rule: {violation['rule_name']}")
            print(f"  Issue: {violation['message']}")
            if 'law_reference' in violation:
                print(f"  Law: {violation['law_reference']}")
            if 'recommendation' in violation:
                print(f"  Fix: {violation['recommendation']}")
        
        if len(violations) > 5:
            print(f"\n  ... and {len(violations) - 5} more violations")
    
    # 5. Example GraphRAG retrieval
    print(f"\n\n" + "="*70)
    print("🔍 EXAMPLE: GraphRAG-lite Retrieval")
    print("="*70)
    print("\nWhen checking OVERTIME compliance, the system retrieves:\n")
    
    ot_context = retriever.retrieve_for_compliance_check(
        entity="overtime",
        context={
            "employee": "Ahmed Al Mansoori",
            "overtime_hours_weekday": 10,
            "overtime_rate": 10.0,
            "legal_rate": 15.0
        }
    )
    
    print(ot_context["formatted_context"])
    
    # 6. Export results
    print(f"\n\n" + "="*70)
    print("💾 Exporting results...")
    print("="*70)
    
    output_file = Path(__file__).parent / "compliance_violations_report.json"
    
    report = {
        "timestamp": date.today().isoformat(),
        "total_employees_checked": len(employee_data),
        "total_violations": len(all_violations),
        "violations_by_severity": {k: len(v) for k, v in by_severity.items()},
        "violations": [
            {
                "employee_id": v['employee_id'],
                "employee_name": v['employee_name'],
                "rule": v['rule_name'],
                "severity": v['severity'].value if hasattr(v['severity'], 'value') else v['severity'],
                "message": v['message'],
                "affected_value": str(v['affected_value']),
                "required_value": str(v['required_value']),
                "law_reference": v.get('law_reference', 'N/A'),
                "recommendation": v.get('recommendation', '')
            }
            for v in all_violations
        ]
    }
    
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"✅ Report saved to: {output_file}")
    print(f"   Total violations: {len(all_violations)}")
    print(f"   Critical: {len(by_severity.get('critical', []))}")
    print(f"   Errors: {len(by_severity.get('error', []))}")
    print(f"   Warnings: {len(by_severity.get('warning', []))}")


if __name__ == "__main__":
    run_compliance_demo()
