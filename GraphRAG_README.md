# GraphRAG-lite + Compliance Checking Demo

## Overview

This project demonstrates how to combine **Knowledge Graphs** (graph-based entity relationships) with **Vector Search** (semantic similarity) to create a smarter compliance checking system.

### What is GraphRAG?

**GraphRAG** = Graph-based Retrieval-Augmented Generation

Instead of just searching by similarity:
```
Traditional RAG:
  Query → Embed query → Search vector store → Get articles
  Problem: loses structural context about relationships

GraphRAG:
  Query → Extract entity → Look up in knowledge graph → Get relationships + thresholds → 
  Vector search for articles → Return context with law citations
  Benefit: Structured knowledge + semantic similarity = better retrieval
```

### Our Implementation

This is **GraphRAG-lite** — a lightweight version using:
- **NetworkX** for the knowledge graph (entities + relationships)
- **FAISS** for vector search (already in the project)
- **Manual curation** of law data (vs. full NER extraction)

## Files Created

### 1. `src/rag/graph_retriever.py` (NEW)

**Core classes:**

- `KnowledgeGraph`: Stores entities and relationships
  ```python
  kg.add_entity("annual_leave", "benefit")
  kg.add_relationship("annual_leave", "minimum_days", "30", {"applies_after": "1_year_tenure"})
  kg.add_article_reference("annual_leave", "Article 78 - Federal Decree-Law 2021")
  ```

- `GraphRAGRetriever`: Dual-mode retrieval
  ```python
  retriever = GraphRAGRetriever(kg)
  
  context = retriever.retrieve_for_compliance_check(
      entity="annual_leave",
      context={"employee_tenure": 2, "entitlement": 20}
  )
  # Returns: relationships + articles + formatted context
  ```

**How it works:**
1. Extract entity ("annual_leave") from compliance check
2. Graph lookup: Find relationships ("minimum_days: 30", "applies_after: 1_year_tenure")
3. Vector search: Find relevant articles (Article 78)
4. Format: Create LLM-friendly context with law citations

### 2. Enhanced Sample Datasets

**41 Compliance Violations** across 19 employees demonstrating all rules:

#### Violation Summary (by type):

| Rule | Count | Severity | Example |
|------|-------|----------|---------|
| **Leave Carry-Forward** | 13 | WARNING | Exceeds 5-day (tenure <3yr) or 10-day (tenure ≥3yr) limits |
| **Annual Leave Minimum** | 8 | ERROR | Only 20 days instead of 30-day minimum |
| **EOS Gratuity** | 8 | ERROR | Calculation errors (21 or 30 days/year formula) |
| **Overtime Rate** | 4 | ERROR | Below 1.25x (weekday) or 1.5x (Friday) |
| **Visa Expiry** | 6 | CRITICAL/WARNING | Expired or expiring soon |
| **Probation Period** | 2 | ERROR | > 6 months (or > 12 for pilots) |

**Total: 41 violations across 19 employees**

#### Realistic Violation Examples

**EMP001 - Ahmed Al Mansoori** (3 violations):
- Annual leave: 20 days → should be 30 (4-year employee)
- Carry forward: 8 days → exceeds 5-day max
- Overtime rate: AED 10/hr → should be AED 15.625/hr (1.25x)

**EMP011 - Tariq Hassan** (5 violations - WORST CASE):
- ✅ CRITICAL: Visa expired 1+ years ago
- Annual leave: 15 days → should be 2 days/month for first year
- Probation: 15 months → exceeds 6-month max
- Overtime: AED 7.5/hr → should be AED 9.375/hr
- EOS Gratuity: Missing

**EMP013 - Sanjay Mehta** (2 violations):
- ✅ CRITICAL: Visa expired 8 months ago
- Carry forward: 28 days → massively exceeds 10-day max

## How to Use

### 1. View Violation Summary
```bash
python datasets/VIOLATIONS_SUMMARY.py
```

Output:
```
VIOLATIONS BY SEVERITY:
  CRITICAL: 2 violations
  ERROR:    23 violations
  WARNING:  16 violations
  TOTAL:    41 violations

VIOLATIONS BY RULE:
  leave_carryforward_limit:     13 cases
  annual_leave_minimum:          8 cases
  eos_gratuity_calculation:      8 cases
  overtime_rate_minimum:         4 cases
  visa_expiry_check:             6 cases
  probation_period_max:          2 cases
```

### 2. Run GraphRAG + Compliance Demo

First install dependencies:
```bash
pip install -r requirements.txt
```

Then run:
```bash
python demo_graphrag_compliance.py
```

### 3. Integration with Web App

The Streamlit app can use the GraphRAG retriever:
```python
from src.rag.graph_retriever import build_uae_labor_law_graph, GraphRAGRetriever
from src.compliance.checker import ComplianceChecker

kg = build_uae_labor_law_graph()
retriever = GraphRAGRetriever(kg)
checker = ComplianceChecker(jurisdiction="UAE")

# Check employee
violations = checker.check_employee(emp_id, emp_name, emp_data)

# For each violation, get law context
for violation in violations:
    context = retriever.retrieve_for_compliance_check(
        entity=violation.rule_name,
        context={"employee": emp_name, "value": violation.affected_value}
    )
    # Display: violation.message + context["formatted_context"]
```

## The Knowledge Graph Structure

```
ANNUAL LEAVE
  ├── minimum_days: 30 → [applies_after: 1_year_tenure]
  ├── first_year_accrual: 2_days_per_month
  └── reference: Article 78

LEAVE CARRY-FORWARD
  ├── max_tenure_under_3yr: 5_days
  ├── max_tenure_3yr_plus: 10_days
  └── reference: Article 82

OVERTIME
  ├── weekday_rate: 1.25x_hourly_rate
  ├── friday_rate: 1.5x_hourly_rate
  └── reference: Article 96-97

EOS GRATUITY
  ├── years_1_to_5: 21_days_per_year
  ├── years_5_plus: 30_days_per_year
  └── calculation_base: final_monthly_salary

VISA REQUIREMENTS
  ├── applies_to: non_uae_nationals
  ├── status: must_be_valid
  └── reference: MOHRE Work Visa

PROBATION PERIOD
  ├── max_standard: 6_months [applies_to: general_roles]
  ├── max_extended: 12_months [applies_to: pilots_captains]
  └── reference: Article 47
```

## Why This Architecture Matters

1. **Structured Knowledge**: Graph captures relationships that vector search alone misses
   - Graph: "annual_leave" → "minimum_days" → "30"
   - Vector search alone: might find unrelated "30 day" references

2. **Compliance Accuracy**: Entity lookup + threshold constraints
   - Graph: "min_tenure_under_3yr: 5 days" ✓ Precise
   - Vector search: "carry forward days" (could be anything) ✗ Ambiguous

3. **Explainability**: Returns structured context
   - Result: "Article 78 requires 30 days minimum. You have 20. Violation."
   - Not just: "relevant articles found"

4. **Scalability**: Add rules without changing code
   - Add nodes/edges to graph
   - New compliance checks automatically get context

## Testing All Rules

Dataset is specifically designed to trigger:
- ✅ **8 cases** of annual leave minimum violations
- ✅ **13 cases** of carry-forward limit violations
- ✅ **8 cases** of EOS gratuity calculation errors
- ✅ **4 cases** of overtime rate violations
- ✅ **6 cases** of visa expiry issues (2 CRITICAL)
- ✅ **2 cases** of probation period violations

Each violation includes:
- Employee ID & name
- Rule that failed
- Current value vs. required value
- Law article reference
- Recommended fix

## Next Steps

To extend this:

1. **Add NER extraction** to auto-build graph from law documents
2. **Integrate with LLM** to generate recommendations
3. **Add Streamlit UI** to visualize violations + law context
4. **Multi-jurisdiction support** (add KSA law graph)
5. **Time-series tracking** (violations over time)

---

**Status**: GraphRAG-lite + Dataset with 41 comprehensive violations ✅  
**Ready for**: Compliance checking demo, law citation generation, rule validation
