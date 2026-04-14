"""
COMPLIANCE INTEGRATION LAYER
=============================

Connects the compliance checker to the data pipeline.

What this does:
  After we map columns and get clean data,
  we run compliance checks against that clean data.
  
Workflow:
  1. Ingest messy data
  2. Map columns → canonical schema (RAG)
  3. Extract clean employee/contract/payroll records
  4. Run compliance checks
  5. Generate violations report
"""

from typing import List, Dict, Any
from datetime import date
import sys
from pathlib import Path

# Add compliance directory to path
sys.path.insert(0, str(Path(__file__).parent))

from checker import ComplianceChecker, ComplianceViolation, ComplianceRecommender


class ComplianceIntegration:
    """
    Bridge between mapped data and compliance checking.
    
    Takes clean data from mapper and runs compliance checks.
    """
    
    def __init__(self, jurisdiction: str = "UAE"):
        self.checker = ComplianceChecker(jurisdiction)
        self.jurisdiction = jurisdiction
    
    def prepare_employee_for_check(
        self,
        employee_record: Dict[str, Any],
        contract_record: Dict[str, Any],
        leave_record: Dict[str, Any],
        payroll_record: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Combine employee, contract, leave, payroll into single check dict.
        
        The compliance checker needs all info in one place.
        This method combines data from canonical tables.
        """
        
        combined = {
            # From employee table
            "employee_id": employee_record.get("employee_id"),
            "name": employee_record.get("name"),
            "national_id": employee_record.get("national_id"),
            "passport_number": employee_record.get("passport_number"),
            "nationality": employee_record.get("nationality"),
            "hire_date": employee_record.get("hire_date"),
            "visa_type": employee_record.get("visa_type"),
            "visa_expiry": employee_record.get("visa_expiry"),
            
            # From contract table
            "base_salary": contract_record.get("base_salary"),
            "housing_allowance": contract_record.get("housing_allowance", 0),
            "transport_allowance": contract_record.get("transport_allowance", 0),
            "probation_period_months": contract_record.get("probation_period_months", 0),
            "job_title": employee_record.get("job_title"),
            
            # From leave table
            "annual_leave_entitlement": leave_record.get("annual_leave_entitlement", 0),
            "annual_leave_used": leave_record.get("annual_leave_used", 0),
            "sick_leave_entitlement": leave_record.get("sick_leave_entitlement", 0),
            "leave_carried_forward": leave_record.get("annual_leave_carried_forward", 0),
            
            # From payroll table
            "overtime_hours_weekday": payroll_record.get("overtime_hours_weekday", 0),
            "overtime_hours_friday": payroll_record.get("overtime_hours_friday", 0),
            "overtime_rate": payroll_record.get("overtime_rate", 0),
            "eos_gratuity_calculated": payroll_record.get("eos_gratuity", 0),
        }
        
        # Calculate derived fields
        if combined.get("hire_date"):
            combined["tenure_years"] = (date.today() - combined["hire_date"]).days / 365.25
        
        if combined.get("base_salary"):
            combined["hourly_rate"] = combined["base_salary"] / 160  # Assuming 160 work hours/month
        
        combined["fixed_allowances"] = (
            combined.get("housing_allowance", 0) +
            combined.get("transport_allowance", 0)
        )
        
        return combined
    
    def check_company_data(
        self,
        employees: List[Dict[str, Any]],
        contracts: List[Dict[str, Any]],
        leave_records: List[Dict[str, Any]],
        payroll_records: List[Dict[str, Any]]
    ) -> List[ComplianceViolation]:
        """
        Check entire company dataset for compliance.
        
        Args:
            employees: List of employee records (from canonical schema)
            contracts: List of contract records
            leave_records: List of leave balance records
            payroll_records: List of payroll run records
        
        Returns:
            List of violations
        """
        
        all_violations = []
        
        # For each employee, combine their data from all tables
        for employee in employees:
            emp_id = employee.get("employee_id")
            emp_name = employee.get("name", emp_id)
            
            # Find related records
            contract = next(
                (c for c in contracts if c.get("employee_id") == emp_id),
                {}
            )
            leave = next(
                (l for l in leave_records if l.get("employee_id") == emp_id),
                {}
            )
            payroll = next(
                (p for p in payroll_records if p.get("employee_id") == emp_id),
                {}
            )
            
            # Prepare combined data
            check_data = self.prepare_employee_for_check(
                employee, contract, leave, payroll
            )
            
            # Run checks
            violations = self.checker.check_employee(emp_id, emp_name, check_data)
            all_violations.extend(violations)
        
        return all_violations
    
    def generate_compliance_report(
        self,
        violations: List[ComplianceViolation]
    ) -> Dict[str, Any]:
        """
        Generate structured compliance report.
        
        Returns:
            {
                "summary": {...},
                "by_severity": {...},
                "action_plan": "...",
                "violations": [...]
            }
        """
        
        self.checker.violations = violations
        report = self.checker.generate_report()
        
        # Add action plan
        action_plan = ComplianceRecommender.generate_action_plan(violations)
        report["action_plan"] = action_plan
        
        return report


if __name__ == "__main__":
    # Test integration
    
    print("\n🔗 Testing Compliance Integration")
    print("=" * 80)
    
    integration = ComplianceIntegration(jurisdiction="UAE")
    
    # Sample data from canonical tables
    employees = [
        {
            "employee_id": "EMP001",
            "name": "Ahmed Al Mansouri",
            "national_id": "784-2024-1234567-1",
            "nationality": "AE",
            "hire_date": date(2022, 1, 15),
            "visa_type": "Employment",
            "visa_expiry": date(2027, 1, 14),
            "job_title": "Senior Engineer",
        }
    ]
    
    contracts = [
        {
            "employee_id": "EMP001",
            "base_salary": 15000,
            "housing_allowance": 5000,
            "transport_allowance": 1000,
            "probation_period_months": 6,
        }
    ]
    
    leave_records = [
        {
            "employee_id": "EMP001",
            "annual_leave_entitlement": 30,
            "annual_leave_used": 5,
            "sick_leave_entitlement": 10,
            "annual_leave_carried_forward": 2,
        }
    ]
    
    payroll_records = [
        {
            "employee_id": "EMP001",
            "overtime_hours_weekday": 2,
            "overtime_rate": 75,
            "eos_gratuity": 21000,
        }
    ]
    
    # Run checks
    violations = integration.check_company_data(
        employees, contracts, leave_records, payroll_records
    )
    
    if violations:
        print(f"\n❌ Found {len(violations)} violations:")
        for v in violations:
            print(f"  - {v.rule_name}: {v.message}")
    else:
        print(f"\n✅ No violations found! Company is compliant.")
    
    # Generate report
    report = integration.generate_compliance_report(violations)
    print(f"\nReport: {len(report['violations'])} total violations")
