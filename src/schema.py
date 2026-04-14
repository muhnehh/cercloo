"""
CANONICAL CERCLI DATA MODEL
============================

This defines "what clean looks like" for a MENA HR platform.
Everything else (mapper, compliance checks) maps data INTO this schema.

Key idea: You're defining a contract between messy input data and clean output.
Later, the LLM mapper will learn to map any column name to one of these categories.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import date

# =====================================================================
# EMPLOYEE TABLE — the core entity
# =====================================================================

@dataclass
class Employee:
    """A single employee in the system."""
    
    # Identity
    employee_id: str  # unique identifier ("EMP001")
    name: str  # full name
    national_id: str  # UAE Emirate ID / KSA National ID
    passport_number: str
    nationality: str  # ISO 3166-1 code ("AE", "SA", "IN", etc.)
    
    # Contact
    email: str
    phone: str
    iban: str  # bank account (for payroll)
    address: str  # current address
    
    # Employment terms
    hire_date: date  # when employment started
    employment_type: str  # "Full-time", "Part-time", "Contractor"
    job_title: str
    department: str
    manager_id: Optional[str] = None  # employee_id of manager
    
    # Compliance-critical fields
    visa_type: Optional[str] = None  # "Employment", "Residence", etc.
    visa_expiry: Optional[date] = None
    work_permit_number: Optional[str] = None
    sponsorship_type: str = "Employer"  # typical for UAE/KSA
    
    # Flags (populated by compliance layer)
    compliance_flags: List[str] = field(default_factory=list)


# =====================================================================
# CONTRACT TABLE — employment terms
# =====================================================================

@dataclass
class Contract:
    """Employment contract for an employee."""
    
    # Required fields (no defaults)
    contract_id: str
    employee_id: str
    start_date: date
    base_salary: float  # required - job cannot exist without salary
    
    # Optional or default fields
    end_date: Optional[date] = None  # None = ongoing
    probation_period_months: int = 6  # UAE law: max 6 months
    currency: str = "AED"  # typical for UAE
    housing_allowance: float = 0  # Changed from Optional[float]
    transport_allowance: float = 0  # Changed from Optional[float]
    other_allowances: float = 0  # Changed from Optional[float]
    
    @property
    def gross_monthly(self) -> float:
        """Total monthly compensation."""
        return (
            self.base_salary +
            self.housing_allowance +
            self.transport_allowance +
            self.other_allowances
        )


# =====================================================================
# LEAVE BALANCE TABLE — track entitlements
# =====================================================================

@dataclass
class LeaveBalance:
    """Leave entitlements and usage for an employee in a given year."""
    
    leave_balance_id: str
    employee_id: str
    year: int
    annual_leave_entitlement: float  # in days
    
    # Entitlements by type (with defaults)
    annual_leave_used: float = 0
    annual_leave_balance: float = 0
    
    sick_leave_entitlement: float = 10  # UAE law: 10 days/year
    sick_leave_used: float = 0
    sick_leave_balance: float = 0
    
    maternity_leave_entitlement: Optional[float] = None  # 60 days in UAE
    maternity_leave_used: float = 0
    
    @property
    def annual_leave_available(self) -> float:
        """Days available to take now."""
        return max(0, self.annual_leave_entitlement - self.annual_leave_used)


# =====================================================================
# PAYROLL RUN TABLE — monthly payroll execution
# =====================================================================

@dataclass
class PayrollRun:
    """A single payroll execution (monthly, bi-weekly, etc)."""
    
    payroll_run_id: str
    employee_id: str
    
    # Period
    period_start: date
    period_end: date
    pay_date: date
    
    # Components
    base_salary: float
    housing_allowance: float = 0
    transport_allowance: float = 0
    other_allowances: float = 0
    
    # Overtime (hours worked at premium rates)
    overtime_hours_weekday: float = 0  # paid at 1.25x
    overtime_hours_friday: float = 0  # paid at 1.5x (UAE law)
    overtime_rate: float = 0  # hourly rate for premium calculation
    
    # Deductions
    income_tax: float = 0
    social_security: float = 0
    employee_contribution: float = 0
    other_deductions: float = 0
    
    @property
    def gross_pay(self) -> float:
        """Total before tax/deductions."""
        return (
            self.base_salary +
            self.housing_allowance +
            self.transport_allowance +
            self.other_allowances +
            (self.overtime_hours_weekday * self.overtime_rate * 1.25) +
            (self.overtime_hours_friday * self.overtime_rate * 1.5)
        )
    
    @property
    def net_pay(self) -> float:
        """Take-home pay."""
        return (
            self.gross_pay -
            self.income_tax -
            self.social_security -
            self.employee_contribution -
            self.other_deductions
        )


# =====================================================================
# COMPLIANCE ALERT TABLE — violations detected
# =====================================================================

@dataclass
class ComplianceAlert:
    """A single compliance violation or warning."""
    
    alert_id: str
    employee_id: str
    
    # What's wrong
    rule_name: str  # e.g., "annual_leave_minimum"
    severity: str  # "warning" or "error"
    description: str  # human-readable
    
    # How to fix it
    law_article: str  # e.g., "UAE Labor Law Article 78"
    law_text: str  # the actual regulation text
    recommended_action: str  # what the company should do
    
    detected_date: date = field(default_factory=lambda: date.today())


# =====================================================================
# HELPER: CENTRALIZED SCHEMA MAPPING
# This is what your LLM mapper will learn to create
# =====================================================================

CANONICAL_SCHEMA = {
    "employees": {
        "fields": [f.name for f in Employee.__dataclass_fields__.values()],
        "required": ["employee_id", "name", "national_id", "nationality", "hire_date"],
        "compliance_critical": ["national_id", "passport_number", "visa_type", "visa_expiry", "work_permit_number"],
    },
    "contracts": {
        "fields": [f.name for f in Contract.__dataclass_fields__.values()],
        "required": ["contract_id", "employee_id", "start_date", "base_salary"],
        "compliance_critical": ["probation_period_months"],
    },
    "leave_balances": {
        "fields": [f.name for f in LeaveBalance.__dataclass_fields__.values()],
        "required": ["leave_balance_id", "employee_id", "year", "annual_leave_entitlement"],
        "compliance_critical": ["annual_leave_entitlement", "sick_leave_entitlement"],
    },
    "payroll_runs": {
        "fields": [f.name for f in PayrollRun.__dataclass_fields__.values()],
        "required": ["payroll_run_id", "employee_id", "period_start", "period_end", "base_salary"],
        "compliance_critical": ["overtime_hours_weekday", "overtime_hours_friday", "overtime_rate"],
    },
    "compliance_alerts": {
        "fields": [f.name for f in ComplianceAlert.__dataclass_fields__.values()],
        "required": ["alert_id", "employee_id", "rule_name", "severity"],
        "compliance_critical": ["law_article", "severity"],
    }
}


if __name__ == "__main__":
    # Quick test: print what a "clean" employee looks like
    sample_emp = Employee(
        employee_id="EMP001",
        name="Ahmed Al Mansouri",
        national_id="784-1234-5678901-1",
        passport_number="K123456789",
        nationality="AE",
        email="ahmed@company.ae",
        phone="+971501234567",
        iban="AE070331234567890123456",
        address="Dubai, UAE",
        hire_date=date(2021, 1, 15),
        employment_type="Full-time",
        job_title="Software Engineer",
        department="Engineering",
        visa_type="Employment",
        visa_expiry=date(2027, 1, 14),
    )
    
    print("✓ Schema loaded successfully")
    print(f"✓ Sample employee: {sample_emp.name} ({sample_emp.employee_id})")
    print(f"✓ Required fields: {CANONICAL_SCHEMA['employees']['required']}")
    print(f"✓ Compliance-critical fields: {CANONICAL_SCHEMA['employees']['compliance_critical']}")
