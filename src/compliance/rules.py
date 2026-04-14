"""
COMPLIANCE RULES FOR MENA HR
=============================

What this does:
  Defines all UAE/KSA labor law compliance checks.
  These map directly to actual regulations companies MUST follow.
  
Why this matters:
  HR violations = fines + legal action.
  This is not optional. Companies use systems like this to avoid lawsuits.

Educational point:
  Compliance isn't just "follow the rules."
  It's: Know the law → Encode it as logic → Check automatically → Flag violations
  
Legal references:
  - UAE: Federal Decree-Law No. 33 of 2021 (updated labor law)
  - KSA: Royal Decree M/51 (Saudi labor law)
  - MOHRE = UAE Ministry of Human Resources & Emiratization

Real companies: This exact logic is in Workday, SuccessFactors, BambooHR.
You're building what they charge millions for.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum


# =====================================================================
# SEVERITY LEVELS
# =====================================================================

class Severity(Enum):
    """How serious is this violation?"""
    WARNING = "warning"      # Minor issue, should fix
    ERROR = "error"          # Legal violation, must fix
    CRITICAL = "critical"    # Immediate action required


# =====================================================================
# COMPLIANCE RULE BASE CLASS
# =====================================================================

@dataclass
class ComplianceRule:
    """
    A single compliance check.
    
    Every rule has:
    - Name: what's being checked
    - Law: which article/decree
    - Description: human-readable explanation
    - Severity: how serious
    """
    
    name: str
    law_reference: str
    description: str
    severity: Severity
    jurisdiction: str  # "UAE" or "KSA"
    
    def check(self, employee_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Execute the check.
        
        Args:
            employee_data: Dict with employee/contract/payroll info
        
        Returns:
            Violation dict if failed, None if passed
            {
                "rule": rule_name,
                "severity": "error",
                "message": "...",
                "affected_value": "...",
                "required_value": "...",
                "law_reference": "...",
                "recommendation": "..."
            }
        """
        raise NotImplementedError("Subclasses must implement check()")


# =====================================================================
# ANNUAL LEAVE RULES
# =====================================================================

@dataclass
class AnnualLeaveMinimumRule(ComplianceRule):
    """
    UAE Law: Employees must receive minimum annual leave.
    
    Article 78 of Federal Decree-Law No. 33 of 2021:
      - After 1 year: 30 days/year
      - During first year: 2 days/month (accrual)
      - Senior roles may not exceed 30 days (up to employer discretion)
    """
    
    def __init__(self):
        super().__init__(
            name="annual_leave_minimum",
            law_reference="UAE Federal Decree-Law 2021, Article 78",
            description="Minimum annual leave entitlement",
            severity=Severity.ERROR,
            jurisdiction="UAE"
        )
    
    def check(self, employee_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if annual leave meets UAE minimum."""
        
        tenure = employee_data.get("tenure_years", 0)
        annual_entitlement = employee_data.get("annual_leave_entitlement", 0)
        hire_date = employee_data.get("hire_date")
        
        # Calculate expected entitlement
        if tenure < 1 and hire_date:
            # First year: 2 days/month
            months_worked = (date.today() - hire_date).days / 30
            expected = max(2, months_worked * 2)
        elif tenure >= 1:
            # After 1 year: 30 days/year minimum
            expected = 30
        else:
            return None  # Not enough data
        
        # Check
        if annual_entitlement < expected:
            return {
                "rule": self.name,
                "severity": self.severity.value,
                "message": f"Annual leave entitlement ({annual_entitlement} days) below UAE minimum",
                "affected_value": annual_entitlement,
                "required_value": expected,
                "law_reference": self.law_reference,
                "recommendation": f"Increase annual leave to {expected} days/year"
            }
        
        return None


@dataclass
class LeaveCarryForwardRule(ComplianceRule):
    """
    UAE Law: Unused leave carry-forward has limits.
    
    Article 82: Employees can carry forward unused leave, but:
      - Max 5 days per year carried forward
      - After 3 years of service: max 10 days carried forward
      - Excess is paid out
    """
    
    def __init__(self):
        super().__init__(
            name="leave_carryforward_limit",
            law_reference="UAE Federal Decree-Law 2021, Article 82",
            description="Leave carry-forward limits",
            severity=Severity.WARNING,
            jurisdiction="UAE"
        )
    
    def check(self, employee_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if carried-forward leave exceeds limits."""
        
        tenure = employee_data.get("tenure_years", 0)
        carried_forward = employee_data.get("leave_carried_forward", 0)
        
        # Determine max allowed carry-forward
        if tenure < 3:
            max_carryforward = 5
        else:
            max_carryforward = 10
        
        if carried_forward > max_carryforward:
            return {
                "rule": self.name,
                "severity": self.severity.value,
                "message": f"Carried-forward leave ({carried_forward} days) exceeds UAE limit",
                "affected_value": carried_forward,
                "required_value": max_carryforward,
                "law_reference": self.law_reference,
                "recommendation": f"Pay out {carried_forward - max_carryforward} days; carry forward max {max_carryforward} days"
            }
        
        return None


# =====================================================================
# OVERTIME RULES
# =====================================================================

@dataclass
class OvertimeRateRule(ComplianceRule):
    """
    UAE Law: Overtime must be paid at premium rates.
    
    Article 96-97:
      - Weekday overtime: 1.25x hourly rate
      - Friday/holiday overtime: 1.5x hourly rate
      - Cannot exceed 10 hours/day
    """
    
    def __init__(self):
        super().__init__(
            name="overtime_rate_minimum",
            law_reference="UAE Federal Decree-Law 2021, Article 96-97",
            description="Overtime pay rates",
            severity=Severity.ERROR,
            jurisdiction="UAE"
        )
    
    def check(self, employee_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if overtime is paid at minimum rates."""
        
        overtime_hours_weekday = employee_data.get("overtime_hours_weekday", 0)
        overtime_hours_friday = employee_data.get("overtime_hours_friday", 0)
        overtime_rate = employee_data.get("overtime_rate", 0)
        hourly_rate = employee_data.get("hourly_rate", 0)
        
        if not hourly_rate or (overtime_hours_weekday == 0 and overtime_hours_friday == 0):
            return None  # No overtime
        
        # Calculate what should have been paid
        min_weekday_rate = hourly_rate * 1.25
        min_friday_rate = hourly_rate * 1.5
        
        # Actual vs required
        violations = []
        
        if overtime_hours_weekday > 0 and overtime_rate < min_weekday_rate:
            violations.append({
                "type": "weekday_overtime",
                "affected_value": overtime_rate,
                "required_value": min_weekday_rate,
                "hours": overtime_hours_weekday
            })
        
        if overtime_hours_friday > 0 and overtime_rate < min_friday_rate:
            violations.append({
                "type": "friday_overtime",
                "affected_value": overtime_rate,
                "required_value": min_friday_rate,
                "hours": overtime_hours_friday
            })
        
        if violations:
            return {
                "rule": self.name,
                "severity": self.severity.value,
                "message": f"Overtime rate (AED {overtime_rate}/hr) below UAE minimum",
                "affected_value": overtime_rate,
                "required_value": f"{min_weekday_rate}/hr (weekday) or {min_friday_rate}/hr (Friday)",
                "law_reference": self.law_reference,
                "recommendation": "Apply 1.25x for weekday OT, 1.5x for Friday OT",
                "violations": violations
            }
        
        return None


# =====================================================================
# END-OF-SERVICE GRATUITY (SEVERANCE)
# =====================================================================

@dataclass
class EndOfServiceGratuityRule(ComplianceRule):
    """
    UAE Law: Severance pay calculation is mandatory.
    
    Article 83-84 (as amended):
      - Years 1-5: 21 days salary/year
      - Year 5+: 30 days salary/year
      
    Calculation:
      - Based on LAST salary (base + fixed allowances)
      - Not bonus, not variable pay
    """
    
    def __init__(self):
        super().__init__(
            name="eos_gratuity_calculation",
            law_reference="UAE Federal Decree-Law 2021, Article 83-84",
            description="End-of-service gratuity calculation",
            severity=Severity.ERROR,
            jurisdiction="UAE"
        )
    
    def check(self, employee_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if severance calculation is correct."""
        
        tenure = employee_data.get("tenure_years", 0)
        base_salary = employee_data.get("base_salary", 0)
        fixed_allowances = employee_data.get("fixed_allowances", 0)
        recorded_gratuity = employee_data.get("eos_gratuity_calculated", 0)
        
        if not base_salary or tenure == 0:
            return None
        
        # Calculate required gratuity
        monthly_salary = base_salary + fixed_allowances
        
        if tenure <= 5:
            gratuity_per_year = 21
        else:
            gratuity_per_year = 30
        
        required_gratuity = (monthly_salary * gratuity_per_year * tenure) / 30
        
        # Check within tolerance (5% acceptable for rounding)
        difference_percent = abs(recorded_gratuity - required_gratuity) / required_gratuity
        
        if difference_percent > 0.05:
            return {
                "rule": self.name,
                "severity": self.severity.value,
                "message": f"EOS gratuity calculation mismatch",
                "affected_value": recorded_gratuity,
                "required_value": required_gratuity,
                "law_reference": self.law_reference,
                "recommendation": f"Recalculate: {monthly_salary} AED × {gratuity_per_year} days × {tenure} years ÷ 30 = {required_gratuity:.0f} AED",
                "variance_percent": difference_percent * 100
            }
        
        return None


# =====================================================================
# VISA & DOCUMENTATION RULES
# =====================================================================

@dataclass
class VisaExpiryRule(ComplianceRule):
    """
    UAE Law: Work visa must be valid.
    
    MOHRE Requirement:
      - No non-citizen can work without valid visa
      - Work permit must be linked to company
    """
    
    def __init__(self):
        super().__init__(
            name="visa_expiry_check",
            law_reference="UAE MOHRE Work Visa Requirements",
            description="Work visa validity",
            severity=Severity.CRITICAL,
            jurisdiction="UAE"
        )
    
    def check(self, employee_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if visa is valid."""
        
        nationality = employee_data.get("nationality", "")
        visa_expiry = employee_data.get("visa_expiry")
        visa_type = employee_data.get("visa_type")
        
        # UAE citizens don't need work visa
        if nationality.upper() == "AE":
            return None
        
        # Check visa exists and is valid
        if not visa_expiry:
            return {
                "rule": self.name,
                "severity": self.severity.value,
                "message": "Missing visa expiry date (non-citizen employee)",
                "affected_value": "N/A",
                "required_value": "Valid visa expiry date",
                "law_reference": self.law_reference,
                "recommendation": "Add visa expiry information"
            }
        
        # Check if expired or expiring soon
        days_until_expiry = (visa_expiry - date.today()).days
        
        if days_until_expiry < 0:
            return {
                "rule": self.name,
                "severity": Severity.CRITICAL.value,
                "message": f"Visa expired {abs(days_until_expiry)} days ago - employee cannot work",
                "affected_value": visa_expiry,
                "required_value": f"On or after {date.today()}",
                "law_reference": self.law_reference,
                "recommendation": "Renew visa immediately - employee is not legally authorized to work"
            }
        
        elif days_until_expiry < 30:
            # Warning for expiring soon
            return {
                "rule": self.name,
                "severity": Severity.WARNING.value,
                "message": f"Visa expires in {days_until_expiry} days - plan renewal",
                "affected_value": visa_expiry,
                "required_value": f"More than 30 days validity",
                "law_reference": self.law_reference,
                "recommendation": f"Initiate visa renewal process - expires in {days_until_expiry} days"
            }
        
        return None


@dataclass
class NationalIDRule(ComplianceRule):
    """
    UAE Law: National ID is mandatory.
    
    MOHRE Requirement:
      - Every employee must have emirates ID or national ID
      - Required for payroll, benefits, compliance
    """
    
    def __init__(self):
        super().__init__(
            name="national_id_required",
            law_reference="UAE MOHRE Employment Records",
            description="National/Emirates ID required",
            severity=Severity.ERROR,
            jurisdiction="UAE"
        )
    
    def check(self, employee_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if national ID is recorded."""
        
        national_id = employee_data.get("national_id")
        
        if not national_id or national_id.strip() == "":
            return {
                "rule": self.name,
                "severity": self.severity.value,
                "message": "Missing national ID / Emirates ID",
                "affected_value": "None",
                "required_value": "Valid national ID",
                "law_reference": self.law_reference,
                "recommendation": "Add employee national ID to system"
            }
        
        return None


# =====================================================================
# PROBATION PERIOD RULES
# =====================================================================

@dataclass
class ProbationPeriodRule(ComplianceRule):
    """
    UAE Law: Probation period has maximum duration.
    
    Article 47:
      - Maximum probation: 6 months
      - Can be extended for specific roles (pilots, captains) up to 12 months
      - Probation period is at 30-day notice termination
    """
    
    def __init__(self):
        super().__init__(
            name="probation_period_max",
            law_reference="UAE Federal Decree-Law 2021, Article 47",
            description="Probation period maximum",
            severity=Severity.ERROR,
            jurisdiction="UAE"
        )
    
    def check(self, employee_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if probation period is within legal limits."""
        
        probation_months = employee_data.get("probation_period_months", 0)
        job_title = employee_data.get("job_title", "")
        
        # Most roles: max 6 months
        max_probation = 6
        
        # Exception: pilots, captains (max 12 months)
        if any(word in job_title.lower() for word in ["pilot", "captain", "airline"]):
            max_probation = 12
        
        if probation_months > max_probation:
            return {
                "rule": self.name,
                "severity": self.severity.value,
                "message": f"Probation period ({probation_months} months) exceeds UAE maximum",
                "affected_value": probation_months,
                "required_value": max_probation,
                "law_reference": self.law_reference,
                "recommendation": f"Set probation period to maximum {max_probation} months"
            }
        
        return None


# =====================================================================
# RULE REGISTRY
# =====================================================================

def get_all_rules() -> List[ComplianceRule]:
    """Get all compliance rules."""
    return [
        AnnualLeaveMinimumRule(),
        LeaveCarryForwardRule(),
        OvertimeRateRule(),
        EndOfServiceGratuityRule(),
        VisaExpiryRule(),
        NationalIDRule(),
        ProbationPeriodRule(),
    ]


def get_rules_by_jurisdiction(jurisdiction: str) -> List[ComplianceRule]:
    """Get rules for a specific jurisdiction."""
    return [r for r in get_all_rules() if r.jurisdiction == jurisdiction]


def get_critical_rules() -> List[ComplianceRule]:
    """Get only critical rules (immediate action needed)."""
    return [r for r in get_all_rules() if r.severity == Severity.CRITICAL]


if __name__ == "__main__":
    # Test the rules
    print("\n📋 Compliance Rules Registry")
    print("=" * 70)
    
    all_rules = get_all_rules()
    print(f"\nTotal rules: {len(all_rules)}")
    
    for rule in all_rules:
        print(f"\n• {rule.name}")
        print(f"  Jurisdiction: {rule.jurisdiction}")
        print(f"  Severity: {rule.severity.value}")
        print(f"  Law: {rule.law_reference}")
        print(f"  Description: {rule.description}")
    
    # Test a check
    print("\n" + "=" * 70)
    print("Testing: Annual leave check")
    print("=" * 70)
    
    test_employee = {
        "name": "Ahmed Al Mansouri",
        "tenure_years": 1,
        "annual_leave_entitlement": 20,  # Below 30
        "hire_date": date.today() - timedelta(days=365)
    }
    
    rule = AnnualLeaveMinimumRule()
    violation = rule.check(test_employee)
    
    if violation:
        print(f"\n❌ VIOLATION FOUND:")
        for key, value in violation.items():
            print(f"   {key}: {value}")
    else:
        print(f"\n✓ No violation")
