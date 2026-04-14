"""
COMPLIANCE CHECKER — Apply rules and detect violations
=======================================================

What this does:
  Takes employee/payroll/leave data
  Runs all compliance rules against it
  Returns list of violations with:
    - What broke
    - Why it matters
    - How to fix it
    - Legal reference

Why this matters:
  This is what HR systems use to flag risk.
  Compliance failures = lawsuits = company liability.
  Automated detection is how you prevent problems.

Educational point:
  This is an example of "business logic encoding":
  Taking legal requirements and turning them into executable code.
  This pattern scales from 2 rules (small company) to 200+ (global enterprise).
"""

from typing import List, Dict, Any, Optional
from datetime import date, timedelta
from dataclasses import dataclass, asdict
import sys
from pathlib import Path

# Add compliance directory to path for relative imports
sys.path.insert(0, str(Path(__file__).parent))

from rules import (
    get_all_rules,
    get_rules_by_jurisdiction,
    get_critical_rules,
    Severity
)


@dataclass
class ComplianceViolation:
    """A single compliance violation."""
    
    employee_id: str
    employee_name: str
    rule_name: str
    severity: str
    message: str
    law_reference: str
    affected_value: Any
    required_value: Any
    recommendation: str
    detected_at: date
    jurisdiction: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for storage/display."""
        return asdict(self)
    
    def __str__(self) -> str:
        """Pretty string representation."""
        severity_icon = {
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚨"
        }
        icon = severity_icon.get(self.severity, "❓")
        return f"{icon} {self.employee_name}: {self.message}"


class ComplianceChecker:
    """
    Main compliance checking orchestrator.
    
    Runs all rules against employee data and generates violations.
    """
    
    def __init__(self, jurisdiction: str = "UAE"):
        """
        Initialize checker.
        
        Args:
            jurisdiction: "UAE" or "KSA"
        """
        self.jurisdiction = jurisdiction
        self.rules = get_rules_by_jurisdiction(jurisdiction)
        self.violations: List[ComplianceViolation] = []
    
    def check_employee(
        self,
        employee_id: str,
        employee_name: str,
        employee_data: Dict[str, Any]
    ) -> List[ComplianceViolation]:
        """
        Check a single employee against all rules.
        
        Args:
            employee_id: unique ID
            employee_name: full name
            employee_data: dict with all employee info
                {
                    "tenure_years": 2,
                    "annual_leave_entitlement": 30,
                    "base_salary": 15000,
                    "visa_expiry": date(2027, 1, 15),
                    ...
                }
        
        Returns:
            List of violations for this employee
        """
        
        violations = []
        
        # Run each rule
        for rule in self.rules:
            violation_dict = rule.check(employee_data)
            
            if violation_dict:
                # Convert rule output to ComplianceViolation object
                violation = ComplianceViolation(
                    employee_id=employee_id,
                    employee_name=employee_name,
                    rule_name=rule.name,
                    severity=violation_dict.get("severity", "warning"),
                    message=violation_dict.get("message", ""),
                    law_reference=violation_dict.get("law_reference", ""),
                    affected_value=violation_dict.get("affected_value"),
                    required_value=violation_dict.get("required_value"),
                    recommendation=violation_dict.get("recommendation", ""),
                    detected_at=date.today(),
                    jurisdiction=self.jurisdiction
                )
                
                violations.append(violation)
        
        return violations
    
    def check_batch(self, employees: List[Dict[str, Any]]) -> List[ComplianceViolation]:
        """
        Check multiple employees.
        
        Args:
            employees: List of dicts:
                [
                    {
                        "employee_id": "EMP001",
                        "employee_name": "Ahmed Al Mansouri",
                        "data": {...}
                    }
                ]
        
        Returns:
            All violations across all employees
        """
        
        all_violations = []
        
        for emp in employees:
            employee_id = emp.get("employee_id", "UNKNOWN")
            employee_name = emp.get("employee_name", "UNKNOWN")
            employee_data = emp.get("data", {})
            
            violations = self.check_employee(employee_id, employee_name, employee_data)
            all_violations.extend(violations)
        
        self.violations = all_violations
        return all_violations
    
    def get_violations_by_severity(self, severity: str) -> List[ComplianceViolation]:
        """Filter violations by severity."""
        return [v for v in self.violations if v.severity == severity]
    
    def get_critical_violations(self) -> List[ComplianceViolation]:
        """Get only critical violations (immediate action needed)."""
        return self.get_violations_by_severity("critical")
    
    def get_errors(self) -> List[ComplianceViolation]:
        """Get high-severity violations (must fix)."""
        return self.get_violations_by_severity("error")
    
    def get_warnings(self) -> List[ComplianceViolation]:
        """Get warnings (should fix)."""
        return self.get_violations_by_severity("warning")
    
    def generate_report(self) -> Dict[str, Any]:
        """
        Generate a compliance report.
        
        Returns:
            {
                "summary": {...},
                "by_severity": {...},
                "by_rule": {...},
                "violations": [...]
            }
        """
        
        critical = self.get_critical_violations()
        errors = self.get_errors()
        warnings = self.get_warnings()
        
        report = {
            "generated_at": date.today().isoformat(),
            "jurisdiction": self.jurisdiction,
            "total_violations": len(self.violations),
            "summary": {
                "critical": len(critical),
                "errors": len(errors),
                "warnings": len(warnings),
            },
            "by_severity": {
                "critical": [v.to_dict() for v in critical],
                "errors": [v.to_dict() for v in errors],
                "warnings": [v.to_dict() for v in warnings],
            },
            "violations": [v.to_dict() for v in self.violations]
        }
        
        # Group by rule
        by_rule = {}
        for violation in self.violations:
            rule = violation.rule_name
            if rule not in by_rule:
                by_rule[rule] = []
            by_rule[rule].append(violation.to_dict())
        
        report["by_rule"] = by_rule
        
        return report
    
    def print_report(self, detailed: bool = True) -> None:
        """Print a human-readable report."""
        
        critical = self.get_critical_violations()
        errors = self.get_errors()
        warnings = self.get_warnings()
        
        print("\n" + "=" * 80)
        print("COMPLIANCE REPORT")
        print("=" * 80)
        print(f"Jurisdiction: {self.jurisdiction}")
        print(f"Generated: {date.today()}")
        print(f"Total violations: {len(self.violations)}")
        
        # Summary
        print(f"\n📊 Summary:")
        print(f"   🚨 CRITICAL: {len(critical)}")
        print(f"   ❌ ERRORS:   {len(errors)}")
        print(f"   ⚠️  WARNINGS: {len(warnings)}")
        
        # Detailed violations
        if detailed and self.violations:
            print(f"\n📋 Violations by Severity:")
            
            # Critical
            if critical:
                print(f"\n🚨 CRITICAL (Immediate Action Required):")
                for v in critical:
                    print(f"\n   {v.rule_name}")
                    print(f"   Employee: {v.employee_name} ({v.employee_id})")
                    print(f"   Message: {v.message}")
                    print(f"   Recommendation: {v.recommendation}")
                    print(f"   Law: {v.law_reference}")
            
            # Errors
            if errors:
                print(f"\n❌ ERRORS (Must Fix):")
                for v in errors:
                    print(f"\n   {v.rule_name}")
                    print(f"   Employee: {v.employee_name} ({v.employee_id})")
                    print(f"   Message: {v.message}")
                    print(f"   Current: {v.affected_value}")
                    print(f"   Required: {v.required_value}")
                    print(f"   Recommendation: {v.recommendation}")
            
            # Warnings
            if warnings:
                print(f"\n⚠️  WARNINGS (Should Fix):")
                for v in warnings[:5]:  # Show first 5
                    print(f"\n   {v.rule_name}")
                    print(f"   Employee: {v.employee_name}")
                    print(f"   Message: {v.message}")
                    print(f"   Recommendation: {v.recommendation}")
                
                if len(warnings) > 5:
                    print(f"\n   ... and {len(warnings) - 5} more warnings")
        
        print("\n" + "=" * 80)


class ComplianceRecommender:
    """
    Generate actionable recommendations from violations.
    
    This helps companies prioritize:
    - What to fix first
    - How long it takes
    - What's at risk
    """
    
    @staticmethod
    def prioritize_violations(violations: List[ComplianceViolation]) -> Dict[str, List[ComplianceViolation]]:
        """
        Categorize violations by urgency and effort.
        
        Returns:
            {
                "immediate": [...],  # Fix today (legal risk)
                "urgent": [...],     # Fix this week (compliance)
                "planned": [...],    # Fix this month (process)
            }
        """
        
        immediate = []
        urgent = []
        planned = []
        
        for v in violations:
            if v.severity == "critical" or "visa" in v.rule_name:
                # Can't work without visa
                immediate.append(v)
            elif v.severity == "error":
                # Legal violation
                urgent.append(v)
            else:
                # Improvement
                planned.append(v)
        
        return {
            "immediate": immediate,
            "urgent": urgent,
            "planned": planned
        }
    
    @staticmethod
    def generate_action_plan(violations: List[ComplianceViolation]) -> str:
        """Generate an action plan text."""
        
        prioritized = ComplianceRecommender.prioritize_violations(violations)
        
        plan = "COMPLIANCE ACTION PLAN\n"
        plan += "=" * 50 + "\n\n"
        
        if prioritized["immediate"]:
            plan += "🚨 IMMEDIATE (Today)\n"
            for v in prioritized["immediate"]:
                plan += f"  • {v.employee_name}: {v.message}\n"
                plan += f"    → {v.recommendation}\n\n"
        
        if prioritized["urgent"]:
            plan += "❌ URGENT (This Week)\n"
            for v in prioritized["urgent"]:
                plan += f"  • {v.employee_name}: {v.message}\n"
                plan += f"    → {v.recommendation}\n\n"
        
        if prioritized["planned"]:
            plan += "📋 PLANNED (This Month)\n"
            for v in prioritized["planned"][:5]:
                plan += f"  • {v.employee_name}: {v.message}\n"
            
            if len(prioritized["planned"]) > 5:
                plan += f"  ... and {len(prioritized['planned']) - 5} more\n"
        
        return plan


if __name__ == "__main__":
    # Test the checker
    
    print("\n✅ Testing Compliance Checker")
    print("=" * 80)
    
    # Create test employees with violations
    test_employees = [
        {
            "employee_id": "EMP001",
            "employee_name": "Ahmed Al Mansouri",
            "data": {
                "tenure_years": 2,
                "annual_leave_entitlement": 20,  # Below 30 ❌
                "hire_date": date.today().replace(year=date.today().year - 2),
                "base_salary": 15000,
                "probation_period_months": 3,
                "visa_expiry": date.today().replace(year=date.today().year + 1),
                "national_id": "784-2024-1234567-1",
            }
        },
        {
            "employee_id": "EMP002",
            "employee_name": "Sarah Johnson",
            "data": {
                "tenure_years": 1,
                "annual_leave_entitlement": 30,  # OK ✓
                "hire_date": date.today().replace(year=date.today().year - 1),
                "base_salary": 12000,
                "probation_period_months": 10,  # Over 6 months ❌
                "visa_expiry": date.today() + timedelta(days=15),  # Expiring soon ⚠️
                "national_id": "",  # Missing ❌
                "overtime_hours_weekday": 5,
                "overtime_rate": 40,  # Below 1.25x minimum ❌
                "hourly_rate": 60,
            }
        }
    ]
    
    # Run checker
    checker = ComplianceChecker(jurisdiction="UAE")
    violations = checker.check_batch(test_employees)
    
    # Print report
    checker.print_report(detailed=True)
    
    # Generate action plan
    print("\n" + ComplianceRecommender.generate_action_plan(violations))
