"""
DATASET VIOLATIONS SUMMARY
==========================

This document shows all the intentional compliance violations
embedded in the sample datasets to demonstrate the system's
violation detection capabilities.

Total Employees: 21
Expected Violations: 30+
"""

VIOLATIONS = {
    "EMP001": {
        "name": "Ahmed Al Mansoori",
        "violations": [
            {
                "rule": "annual_leave_minimum",
                "severity": "ERROR",
                "issue": "Annual leave entitlement is 20 days (carries forward 8 days) but should be 30 days minimum after 4 years tenure",
                "law": "Article 78 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "leave_carryforward_limit",
                "severity": "WARNING", 
                "issue": "Carry forward is 8 days, but max allowed for tenure >= 3 years is 10 days, and for tenure < 3 years is 5 days",
                "law": "Article 82 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "overtime_rate_minimum",
                "severity": "ERROR",
                "issue": "Overtime rate is AED 10.0/hr but should be at least 15000*1.25/240 = AED 15.625/hr for weekday",
                "law": "Article 96-97 - UAE Federal Decree-Law 2021"
            }
        ]
    },
    "EMP002": {
        "name": "Sarah Johnson",
        "violations": [
            {
                "rule": "leave_carryforward_limit",
                "severity": "WARNING",
                "issue": "Carry forward is 12 days, exceeds maximum of 10 days for any tenure",
                "law": "Article 82 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "visa_expiry_check",
                "severity": "WARNING",
                "issue": "Visa expired on 2024-06-15, it is now 2026-04-14 (employee not legally authorized to work)",
                "law": "MOHRE Work Visa Requirements"
            }
        ]
    },
    "EMP003": {
        "name": "Mohammed Al Rashidi",
        "violations": [
            {
                "rule": "annual_leave_minimum",
                "severity": "ERROR",
                "issue": "Annual leave entitlement is 20 days but should be 30 days minimum after 4.5 years tenure",
                "law": "Article 78 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "overtime_rate_minimum",
                "severity": "ERROR",
                "issue": "Overtime rate is AED 9.5/hr, below minimum of AED 11.875/hr (1.25x weekday rate)",
                "law": "Article 96-97 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "eos_gratuity_calculation",
                "severity": "ERROR",
                "issue": "EOS gratuity calculated as 4275 AED but should be (9500+3000)*21*4.5/30 = 18900 AED (77% variance)",
                "law": "Article 83-84 - UAE Federal Decree-Law 2021"
            }
        ]
    },
    "EMP004": {
        "name": "Priya Sharma",
        "violations": [
            {
                "rule": "annual_leave_minimum",
                "severity": "ERROR",
                "issue": "Only 1.8 years tenure but entitlement is only 12 days (should be 2 days/month = 3.6 days for 1.8 months)",
                "law": "Article 78 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "leave_carryforward_limit",
                "severity": "WARNING",
                "issue": "Carry forward is 8 days, exceeds 5-day limit for tenure < 3 years",
                "law": "Article 82 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "visa_expiry_check",
                "severity": "WARNING",
                "issue": "Visa expires 2024-06-30, will expire soon (less than 30 days)",
                "law": "MOHRE Work Visa Requirements"
            },
            {
                "rule": "eos_gratuity_calculation",
                "severity": "ERROR",
                "issue": "EOS gratuity missing - should be calculated but is 18000, should be (15000+5000)*21*1.8/30 = 25200 AED",
                "law": "Article 83-84 - UAE Final Decree-Law 2021"
            }
        ]
    },
    "EMP005": {
        "name": "Khalid Al Zaabi",
        "violations": [
            {
                "rule": "leave_carryforward_limit",
                "severity": "WARNING",
                "issue": "Carry forward is 15 days, exceeds maximum of 10 days",
                "law": "Article 82 - UAE Federal Decree-Law 2021"
            }
        ]
    },
    "EMP006": {
        "name": "Fatima Al Nuaimi",
        "violations": [
            {
                "rule": "eos_gratuity_calculation",
                "severity": "ERROR",
                "issue": "EOS gratuity is missing/zero but should be (8000+2500)*21*0.5/30 = 1750 AED",
                "law": "Article 83-84 - UAE Federal Decree-Law 2021"
            }
        ]
    },
    "EMP007": {
        "name": "Raj Patel",
        "violations": [
            {
                "rule": "leave_carryforward_limit",
                "severity": "WARNING",
                "issue": "Carry forward is 20 days, far exceeds limit of 5 days for tenure < 3 years",
                "law": "Article 82 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "eos_gratuity_calculation",
                "severity": "ERROR",
                "issue": "EOS gratuity is 39200 AED but should be (20000+6500)*21*4.2/30 = 45780 AED (14% variance)",
                "law": "Article 83-84 - UAE Federal Decree-Law 2021"
            }
        ]
    },
    "EMP008": {
        "name": "Aisha Bint Sultan",
        "violations": [
            {
                "rule": "leave_carryforward_limit",
                "severity": "WARNING",
                "issue": "Carry forward is 18 days, exceeds maximum of 10 days for any tenure",
                "law": "Article 82 - UAE Federal Decree-Law 2021"
            }
        ]
    },
    "EMP009": {
        "name": "John Williams",
        "violations": [
            {
                "rule": "annual_leave_minimum",
                "severity": "ERROR",
                "issue": "Annual leave entitlement is 20 days but should be 30 days minimum after 2.8 years tenure",
                "law": "Article 78 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "visa_expiry_check",
                "severity": "WARNING",
                "issue": "Visa expires 2024-09-01, expired date has passed (employee cannot legally work)",
                "law": "MOHRE Work Visa Requirements"
            }
        ]
    },
    "EMP010": {
        "name": "Nour Al Hamdan",
        "violations": [
            {
                "rule": "leave_carryforward_limit",
                "severity": "WARNING",
                "issue": "Carry forward is 12 days, exceeds maximum of 10 days for any tenure",
                "law": "Article 82 - UAE Federal Decree-Law 2021"
            }
        ]
    },
    "EMP011": {
        "name": "Tariq Hassan",
        "violations": [
            {
                "rule": "annual_leave_minimum",
                "severity": "ERROR",
                "issue": "In first year of employment but annual entitlement is 15 days (should be 2 days/month = 2 days for 1.0 year)",
                "law": "Article 78 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "visa_expiry_check",
                "severity": "CRITICAL",
                "issue": "Visa expired on 2024-03-03, employee has not been legally authorized to work for over a year",
                "law": "MOHRE Work Visa Requirements"
            },
            {
                "rule": "probation_period_max",
                "severity": "ERROR",
                "issue": "Probation period is 15 months, exceeds UAE maximum of 6 months",
                "law": "Article 47 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "overtime_rate_minimum",
                "severity": "ERROR",
                "issue": "Overtime rate is AED 7.5/hr, far below minimum of AED 9.375/hr per hour (1.25x)",
                "law": "Article 96-97 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "eos_gratuity_calculation",
                "severity": "ERROR",
                "issue": "EOS gratuity is missing/zero but should be (7500+2200)*21*1.0/30 = 6767 AED",
                "law": "Article 83-84 - UAE Federal Decree-Law 2021"
            }
        ]
    },
    "EMP012": {
        "name": "Lina Khoury",
        "violations": [
            {
                "rule": "leave_carryforward_limit",
                "severity": "WARNING",
                "issue": "Carry forward is 14 days, exceeds maximum of 10 days for any tenure",
                "law": "Article 82 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "eos_gratuity_calculation",
                "severity": "ERROR",
                "issue": "EOS gratuity is 31200 AED but should be (16000+5200)*21*3.9/30 = 53287 AED (41% variance)",
                "law": "Article 83-84 - UAE Federal Decree-Law 2021"
            }
        ]
    },
    "EMP013": {
        "name": "Sanjay Mehta",
        "violations": [
            {
                "rule": "leave_carryforward_limit",
                "severity": "ERROR",
                "issue": "Carry forward is 28 days, far exceeds maximum of 10 days - massive violation",
                "law": "Article 82 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "visa_expiry_check",
                "severity": "CRITICAL",
                "issue": "Visa expired on 2024-08-08, employee has not been legally authorized for ~8 months",
                "law": "MOHRE Work Visa Requirements"
            }
        ]
    },
    "EMP014": {
        "name": "Omar Al Farsi",
        "violations": [
            {
                "rule": "annual_leave_minimum",
                "severity": "ERROR",
                "issue": "Annual leave entitlement is 25 days but should be 30 days minimum after 2.6 years tenure",
                "law": "Article 78 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "leave_carryforward_limit",
                "severity": "WARNING",
                "issue": "Carry forward is 10 days, at the maximum allowable - monitor closely",
                "law": "Article 82 - UAE Federal Decree-Law 2021"
            }
        ]
    },
    "EMP017": {
        "name": "Deepa Nair",
        "violations": [
            {
                "rule": "annual_leave_minimum",
                "severity": "ERROR",
                "issue": "Annual leave entitlement is 18 days but should be 30 days minimum (tenure 1.6 years < 2 years)",
                "law": "Article 78 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "visa_expiry_check",
                "severity": "WARNING",
                "issue": "Visa expires 2024-09-22, will expire soon (less than 30 days remaining)",
                "law": "MOHRE Work Visa Requirements"
            },
            {
                "rule": "eos_gratuity_calculation",
                "severity": "ERROR",
                "issue": "EOS gratuity is 2850 AED but should be (9500+3000)*21*1.6/30 = 10080 AED (72% variance)",
                "law": "Article 83-84 - UAE Federal Decree-Law 2021"
            }
        ]
    },
    "EMP018": {
        "name": "Youssef Mansour",
        "violations": [
            {
                "rule": "leave_carryforward_limit",
                "severity": "WARNING",
                "issue": "Carry forward is 15 days, exceeds maximum of 10 days",
                "law": "Article 82 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "overtime_rate_minimum",
                "severity": "ERROR",
                "issue": "Overtime rate is AED 8.5/hr, below minimum of AED 10.63/hr (1.25x weekday rate)",
                "law": "Article 96-97 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "eos_gratuity_calculation",
                "severity": "ERROR",
                "issue": "EOS gratuity is missing/zero but should be (8500+2700)*21*4.6/30 = 16907 AED",
                "law": "Article 83-84 - UAE Federal Decree-Law 2021"
            }
        ]
    },
    "EMP019": {
        "name": "Emma Clarke",
        "violations": [
            {
                "rule": "annual_leave_minimum",
                "severity": "ERROR",
                "issue": "Annual leave entitlement is 22 days but should be 30 days minimum after 1.2 years tenure",
                "law": "Article 78 - UAE Federal Decree-Law 2021"
            },
            {
                "rule": "leave_carryforward_limit",
                "severity": "WARNING",
                "issue": "Carry forward is 8 days, exceeds maximum of 5 days for tenure < 3 years",
                "law": "Article 82 - UAE Federal Decree-Law 2021"
            }
        ]
    },
    "EMP020": {
        "name": "Ali Al Balushi",
        "violations": [
            {
                "rule": "leave_carryforward_limit",
                "severity": "WARNING",
                "issue": "Carry forward is 20 days, exceeds maximum of 10 days - should be paid out",
                "law": "Article 82 - UAE Federal Decree-Law 2021"
            }
        ]
    },
    "EMP021": {
        "name": "Hassan Al Kaabi",
        "violations": [
            {
                "rule": "probation_period_max",
                "severity": "ERROR",
                "issue": "Probation period is 10 months, exceeds maximum of 12 months even for pilots",
                "law": "Article 47 - UAE Federal Decree-Law 2021"
            }
        ]
    }
}


def print_summary():
    """Print violation summary."""
    print("\n" + "="*70)
    print("COMPLIANCE VIOLATION SUMMARY")
    print("="*70)
    
    violation_count = {}
    severity_count = {"ERROR": 0, "CRITICAL": 0, "WARNING": 0}
    
    for emp_id, emp_data in VIOLATIONS.items():
        for v in emp_data["violations"]:
            rule = v["rule"]
            severity = v["severity"]
            
            violation_count[rule] = violation_count.get(rule, 0) + 1
            severity_count[severity] = severity_count.get(severity, 0) + 1
    
    print("\nVIOLATIONS BY SEVERITY:")
    print("-" * 70)
    print("  CRITICAL: {} violations".format(severity_count["CRITICAL"]))
    print("  ERROR:    {} violations".format(severity_count["ERROR"]))
    print("  WARNING:  {} violations".format(severity_count["WARNING"]))
    print("  TOTAL:    {} violations".format(sum(severity_count.values())))
    
    print("\nVIOLATIONS BY RULE:")
    print("-" * 70)
    for rule in sorted(violation_count.keys()):
        count = violation_count[rule]
        print("  {}: {} cases".format(rule, count))
    
    print("\nEMPLOYEES WITH VIOLATIONS:")
    print("-" * 70)
    for emp_id in sorted(VIOLATIONS.keys()):
        emp_name = VIOLATIONS[emp_id]["name"]
        count = len(VIOLATIONS[emp_id]["violations"])
        print("  {} ({}): {} violations".format(emp_id, emp_name, count))


if __name__ == "__main__":
    print_summary()
