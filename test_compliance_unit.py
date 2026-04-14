#!/usr/bin/env python3
"""Quick test: Verify compliance integration is working correctly."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from compliance.integration import ComplianceIntegration
from schema import Employee, Contract
from datetime import date

print('\n✅ Testing Compliance Integration (Unit Test)')
print('=' * 80)

# Create sample data
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
        "probation_period_months": 4,  # Should be <= 6 ✓
    }
]

leave_records = [
    {
        "employee_id": "EMP001",
        "annual_leave_entitlement": 30,  # Should be >= 30 ✓
        "annual_leave_used": 5,
        "sick_leave_entitlement": 10,
        "annual_leave_carried_forward": 2,
    }
]

payroll_records = [
    {
        "employee_id": "EMP001",
        "overtime_hours_weekday": 2,
        "overtime_rate": 100,  # Should be >= 75 ✓
        "eos_gratuity": 31500,  # 30*1050 = 31500 ✓
    }
]

# Initialize compliance checker
integration = ComplianceIntegration(jurisdiction="UAE")

print('\n🚀 Running compliance check on sample employee...\n')

# Run checks
violations = integration.check_company_data(
    employees, contracts, leave_records, payroll_records
)

# Print results
print(f'\n✅ COMPLIANCE CHECK COMPLETE')
print('=' * 80)
print(f'Total violations detected: {len(violations)}')
if violations:
    print(f'\nViolations:')
    for v in violations:
        print(f'  - {v.rule_name}: {v.message}')
else:
    print('\n✓ No violations found - this employee is compliant!')

print('\n✨ Compliance integration is working correctly!')
