"""
COLUMN MAPPER — RAG-AUGMENTED LLM MAPPING
==========================================

What this does (RAG VERSION):
  1. Takes messy CSV profile from ingestion.py
  2. For EACH column, retrieves similar canonical fields from vector store
  3. Sends column + retrieved context to Claude (not all data!)
  4. Gets back: "emp_nm should map to 'name' with 95% confidence"
  5. Stores successful mapping back in vector store for future learning
  
Why RAG matters:
  - OLD (Prompt Stuffing): Send all 28 columns to LLM → hallucinations
  - NEW (RAG): For each column, retrieve top 3 similar fields → better reasoning
  - Result: Better mappings, scales to millions of columns, self-improving
  
Educational point:
  This is how modern AI systems work (ChatGPT retrieval plugin, RAG-based chatbots).
  You're building the core pattern that powers Copilot, Claude projects, etc.
"""

import json
import re
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class ColumnMapping:
    """A single column mapping suggestion."""
    source_column: str
    suggested_target: str  # canonical field name
    confidence: float  # 0.0 to 1.0
    target_table: str  # "employees", "contracts", "payroll_runs", "leave_balances"
    reasoning: str
    data_type: str  # inferred type from ingestion


class ColumnMapper:
    """Map messy CSV columns to canonical schema using Claude."""
    
    def __init__(self):
        """Initialize with canonical field mappings."""
        # This is your "reference guide" - what canonical fields exist and their tables
        self.canonical_schema = {
            "employees": [
                "employee_id", "name", "national_id", "passport_number",
                "nationality", "email", "phone", "iban", "address",
                "hire_date", "employment_type", "job_title", "department",
                "manager_id", "visa_type", "visa_expiry", "work_permit_number"
            ],
            "contracts": [
                "contract_id", "employee_id", "start_date", "end_date",
                "probation_period_months", "currency", "base_salary",
                "housing_allowance", "transport_allowance", "other_allowances"
            ],
            "leave_balances": [
                "leave_balance_id", "employee_id", "year",
                "annual_leave_entitlement", "annual_leave_used", "annual_leave_balance",
                "sick_leave_entitlement", "sick_leave_used", "sick_leave_balance",
                "maternity_leave_entitlement", "maternity_leave_used"
            ],
            "payroll_runs": [
                "payroll_run_id", "employee_id", "period_start", "period_end", "pay_date",
                "base_salary", "housing_allowance", "transport_allowance", "other_allowances",
                "overtime_hours_weekday", "overtime_hours_friday", "overtime_rate",
                "income_tax", "social_security", "employee_contribution", "other_deductions"
            ]
        }
    
    def build_prompt_with_rag(
        self,
        profiles: Dict[str, Dict[str, Any]],
        retriever=None
    ) -> str:
        """
        Build an AUGMENTED prompt using RAG retrieval.
        
        Instead of sending all columns:
          1. For EACH column, retrieve similar canonical fields
          2. Include only the top results as examples
          3. Send smaller, smarter context to LLM
        
        This is the RAG transformation:
          OLD: 28 columns × 500 tokens = 14K tokens
          NEW: 28 columns × (50 tokens + 200 retrieved tokens) = 7K tokens
          But BETTER because retrieval focuses on relevant examples
        """
        
        schemas_text = """You are an HR data migration specialist mapping messy CSV columns to a canonical schema.

CANONICAL SCHEMA (what you're mapping TO):
- EMPLOYEES: name, employee_id, national_id, hire_date, visa_type
- CONTRACTS: base_salary, housing_allowance, contract_id
- LEAVE_BALANCES: annual_leave_entitlement, sick_leave_used
- PAYROLL_RUNS: overtime_hours_weekday, overtime_rate

Now map these MESSY COLUMNS:\n"""
        
        # If we have a retriever, use RAG
        if retriever:
            try:
                for source_name, profile in profiles.items():
                    schemas_text += f"\n### {source_name}\n"
                    
                    for col_profile in profile["columns"]:
                        col_name = col_profile["name"]
                        col_type = col_profile["inferred_type"]
                        samples = col_profile.get("sample_values", [])
                        
                        # RAG RETRIEVAL: Get similar canonical fields
                        retrieval = retriever.retrieve_similar_columns(
                            messy_column_name=col_name,
                            messy_column_type=col_type,
                            messy_samples=samples,
                            k=2
                        )
                        
                        schemas_text += f"\n**{col_name}** (type: {col_type})\n"
                        schemas_text += f"  Examples: {', '.join(samples[:2])}\n"
                        
                        # Show most similar canonical fields
                        if retrieval["similar_fields"]:
                            schemas_text += "  Consider mapping to:\n"
                            for field in retrieval["similar_fields"][:2]:
                                schemas_text += f"    • {field['canonical_name']} ({field['similarity']*100:.0f}%)\n"
            
            except Exception as e:
                # Fallback if retriever fails
                pass
        
        # Always include standard instructions
        schemas_text += """

Return ONLY this JSON format:
{
  "mappings": [
    {"source_column": "emp_nm", "suggested_target": "name", "target_table": "employees", "confidence": 0.95, "reasoning": "matches canonical field", "data_type": "string"}
  ]
}"""
        
        return schemas_text
    
    def build_prompt(self, profiles: Dict[str, Dict[str, Any]]) -> str:
        """
        Create a detailed prompt for Claude to map column names.
        
        The key insight: Claude works better when you give it CONTEXT.
        Tell it about your canonical schema FIRST, then show the data.
        """
        
        # Part 1: Explain the canonical schema
        schema_explanation = """You are an HR data migration specialist. Your job is to map messy HR export columns to a clean, standardized HR schema.

Here's the CANONICAL SCHEMA you should map TO:

EMPLOYEES table (core employee info):
  - employee_id, name, national_id, passport_number, nationality
  - email, phone, iban, address, hire_date
  - employment_type, job_title, department, manager_id
  - visa_type, visa_expiry, work_permit_number

CONTRACTS table (employment terms):
  - contract_id, employee_id, start_date, end_date
  - probation_period_months, currency, base_salary
  - housing_allowance, transport_allowance, other_allowances

LEAVE_BALANCES table (entitlements):
  - leave_balance_id, employee_id, year
  - annual_leave_entitlement, annual_leave_used, annual_leave_balance
  - sick_leave_entitlement, sick_leave_used, sick_leave_balance
  - maternity_leave_entitlement, maternity_leave_used

PAYROLL_RUNS table (monthly pay):
  - payroll_run_id, employee_id, period_start, period_end, pay_date
  - base_salary, housing_allowance, transport_allowance, other_allowances
  - overtime_hours_weekday, overtime_hours_friday, overtime_rate
  - income_tax, social_security, employee_contribution, other_deductions

---

Now here's the MESSY DATA you need to map FROM:
"""
        
        # Part 2: Show the CSV profiles
        for source_name, profile in profiles.items():
            schema_explanation += f"\n\n### {source_name.upper()} (from their {source_name.replace('_', ' ')})\n"
            schema_explanation += f"This file has {profile['row_count']} rows and {profile['column_count']} columns:\n\n"
            
            for col_profile in profile["columns"]:
                col_name = col_profile["name"]
                col_type = col_profile["inferred_type"]
                samples = ", ".join(col_profile["sample_values"][:3])
                nulls = col_profile["null_percentage"]
                
                schema_explanation += f"  **{col_name}** (type: {col_type}, nulls: {nulls}%)\n"
                schema_explanation += f"    Examples: {samples}\n"
        
        # Part 3: Ask Claude for JSON output
        schema_explanation += """

---

For EACH column in the messy data, provide a JSON response with:
  - source_column: the messy column name
  - suggested_target: the canonical field it maps to (or "SKIP" if it doesn't fit)
  - target_table: which table it belongs to ("employees", "contracts", "leave_balances", "payroll_runs")
  - confidence: 0.0 to 1.0 (how sure you are)
  - reasoning: why this mapping makes sense
  - data_type: what type of data it contains

RESPONSE FORMAT - RETURN ONLY THIS JSON, NOTHING ELSE:
{
  "mappings": [
    {
      "source_column": "emp_nm",
      "suggested_target": "name",
      "target_table": "employees",
      "confidence": 0.98,
      "reasoning": "Standard abbreviation for employee name",
      "data_type": "string"
    }
  ]
}

Remember:
  - Be confident (0.8+) only if mapping is obvious
  - Use 0.5-0.7 if it's a guess (maybe 'hrly_rate' is overtime_rate?)
  - Use 0.0-0.4 if it doesn't fit anywhere
  - Return VALID JSON only, no markdown, no explanations
"""
        
        return schema_explanation

    def build_compact_prompt(
        self,
        profiles: Dict[str, Dict[str, Any]],
        max_files: int = 2,
        max_columns_per_file: int = 6,
        max_samples_per_column: int = 1,
    ) -> str:
        """
        Build a compact prompt optimized for local Ollama latency.

        Local models can time out on large payloads. This keeps enough signal
        for mapping while reducing token and parsing overhead.
        """

        prompt = (
            "Map HR columns to canonical fields.\n"
            "Canonical by table:\n"
            "E=employee_id,name,national_id,passport_number,nationality,hire_date,job_title,department,visa_type,visa_expiry\n"
            "C=contract_id,employee_id,start_date,end_date,probation_period_months,base_salary,housing_allowance,transport_allowance\n"
            "L=employee_id,annual_leave_entitlement,annual_leave_used,annual_leave_balance,sick_leave_entitlement,sick_leave_used\n"
            "P=employee_id,period_start,period_end,pay_date,base_salary,overtime_hours_weekday,overtime_hours_friday,overtime_rate\n"
            "Input columns:\n"
        )

        file_count = 0
        for source_name, profile in profiles.items():
            if file_count >= max_files:
                break
            file_count += 1

            prompt += f"\n[{source_name}]\n"
            columns = self._select_informative_columns(
                profile.get("columns", []),
                max_columns_per_file,
            )
            for col_profile in columns:
                col_name = col_profile.get("name", "")
                col_type = col_profile.get("inferred_type", "unknown")
                samples = col_profile.get("sample_values", [])[:max_samples_per_column]
                sample_text = str(samples[0])[:12] if samples else "na"
                prompt += f"- {col_name}|{col_type}|{sample_text}\n"

        prompt += (
            "Return ONLY JSON: {\"mappings\":[{\"source_column\":\"...\","
            "\"suggested_target\":\"...\",\"target_table\":\"employees|contracts|leave_balances|payroll_runs\","
            "\"confidence\":0.0,\"reasoning\":\"short\",\"data_type\":\"...\"}]}"
        )

        return prompt

    def _select_informative_columns(self, columns: List[Dict[str, Any]], max_columns: int) -> List[Dict[str, Any]]:
        """Pick columns with strongest mapping signal to keep prompt tiny but useful."""

        if not columns:
            return []

        keyword_pattern = re.compile(
            r"emp|name|id|visa|pass|national|hire|join|dept|job|salary|allow|leave|"
            r"overtime|ot|probation|contract|period|pay|tax|gratuity",
            re.IGNORECASE,
        )

        scored = []
        for col in columns:
            col_name = str(col.get("name", ""))
            inferred_type = str(col.get("inferred_type", ""))
            null_pct = float(col.get("null_percentage", 100)) if col.get("null_percentage") is not None else 100.0

            score = 0
            if keyword_pattern.search(col_name):
                score += 5
            if inferred_type in {"date", "numeric", "identifier", "string"}:
                score += 2
            if null_pct <= 20:
                score += 2
            elif null_pct <= 50:
                score += 1

            # Slight bonus for shorter names (often coded exports) since these need mapping most.
            score += 1 if len(col_name) <= 12 else 0
            scored.append((score, col))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [col for _, col in scored[:max_columns]]
    
    def map_columns_with_llm(self, profiles: Dict[str, Dict[str, Any]], retriever=None) -> List[ColumnMapping]:
        """
        Map columns using the best available LLM:
          1. Try Ollama (local, free) first
          2. Fallback to Claude if ANTHROPIC_API_KEY is set
          3. Fallback to DEMO mode for quick testing
        
        Args:
            profiles: CSV profiles from ingestion
            retriever: Optional RAG Retriever for context augmentation
        
        Returns: List of ColumnMapping objects, or empty list if all fail
        """
        
        # Store retriever for later use in prompt building
        self._retriever = retriever
        
        # Try Ollama first
        print("\n Attempting to use local Ollama for column mapping...\n")
        mappings = self._try_ollama(profiles)
        if mappings:
            return mappings
        
        # Fallback to Claude if available
        print("\n Ollama not available, trying Claude API...\n")
        mappings = self._try_claude(profiles)
        if mappings:
            return mappings
        
        # Both failed - use DEMO MODE for quick testing
        print("\n Both LLMs unavailable. Using DEMO MODE for testing...")
        return self._demo_mappings(profiles)
    
    def _try_ollama(self, profiles: Dict[str, Dict[str, Any]]) -> Optional[List[ColumnMapping]]:
        """Attempt to use local Ollama server."""
        
        try:
            import requests
        except ImportError:
            print("   (requests library needed for Ollama, skipping)")
            return None
        
        # Check if Ollama is running
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code != 200:
                print("   [ERROR] Ollama server not responding (expected on port 11434)")
                return None
            
            available_models = response.json().get("models", [])
            if not available_models:
                print("   [ERROR] No models installed in Ollama")
                print("      Try: ollama pull mistral")
                return None
            
            # List available models
            print(f"   [OK] Found {len(available_models)} model(s):")
            model_names = [m["name"] for m in available_models]
            for mn in model_names:
                print(f"      - {mn}")
            
            # Prefer qwen first for faster local inference, then deepseek.
            model_name = None
            for mn in model_names:
                if "qwen" in mn.lower():
                    model_name = mn
                    print(f"   [OK] Using Qwen model: {model_name}")
                    break
            
            if not model_name:
                for mn in model_names:
                    if "deepseek" in mn.lower():
                        model_name = mn
                        print(f"   [OK] Using Deepseek model: {model_name}")
                        break
            
            if not model_name:
                # Fallback to first available model
                model_name = model_names[0]
                print(f"   [OK] Using first available model: {model_name}")
        
        except requests.exceptions.ConnectionError:
            print("   [ERROR] Can't connect to Ollama on localhost:11434")
            print("      Make sure Ollama is running: ollama serve")
            return None
        except Exception as e:
            print(f"   [ERROR] Ollama check failed: {e}")
            return None
        
        # Build a compact prompt for Ollama to reduce latency/timeouts.
        # RAG is intentionally skipped here because local inference speed
        # is the bottleneck and compact context is more reliable.
        prompt = self.build_compact_prompt(
            profiles,
            max_files=2,
            max_columns_per_file=6,
            max_samples_per_column=1,
        )

        strict_prompt = self._build_ollama_strict_prompt(prompt)

        print(f"   Using compact Ollama prompt")
        print(f"      Prompt size: {len(prompt)} characters")

        attempts = [
            ("compact", prompt, 900),
            ("strict", strict_prompt, 1200),
        ]

        for attempt_name, attempt_prompt, num_predict in attempts:
            print(f"   Sending to Ollama ({model_name}) [{attempt_name}]...")

            try:
                response = requests.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": model_name,
                        "prompt": attempt_prompt,
                        "stream": False,
                        "format": "json",
                        "options": {
                            "num_ctx": 1536,
                            "temperature": 0,
                            "top_p": 0.9,
                            "repeat_penalty": 1.05,
                            "num_predict": num_predict,
                        },
                    },
                    timeout=75,
                )

                if response.status_code != 200:
                    print(f"   ✗ Ollama returned status {response.status_code}")
                    continue

                response_text = response.json().get("response", "")
                mappings = self._parse_ollama_mappings(response_text)

                if mappings:
                    print(f"   ✓ Ollama returned {len(mappings)} column mappings\n")
                    return mappings

                print(f"   ✗ Ollama returned 0 column mappings on {attempt_name} attempt")

            except requests.exceptions.Timeout:
                print(f"   ✗ Ollama timed out on {attempt_name} attempt")
                continue
            except TimeoutError:
                print(f"   ✗ Ollama socket timed out on {attempt_name} attempt")
                continue
            except Exception as e:
                print(f"   ✗ Ollama call failed on {attempt_name} attempt: {e}")
                continue

        return None

    def _build_ollama_strict_prompt(self, compact_prompt: str) -> str:
        """Force Ollama to map every listed column and never return an empty array."""

        return (
            compact_prompt
            + "\n\nRULES:"
            + "\n- Return a mapping for every listed input column."
            + "\n- Never return an empty mappings array."
            + "\n- If unsure, choose the closest valid target field and confidence 0.4-0.7."
            + "\n- Output only JSON."
        )

    def _parse_ollama_mappings(self, response_text: str) -> List[ColumnMapping]:
        """Parse Ollama output across common JSON shapes and key names."""

        if not response_text:
            return []

        cleaned = response_text.strip()

        if "```json" in cleaned:
            json_start = cleaned.find("```json") + 7
            json_end = cleaned.find("```", json_start)
            cleaned = cleaned[json_start:json_end].strip()
        elif "```" in cleaned:
            json_start = cleaned.find("```") + 3
            json_end = cleaned.find("```", json_start)
            cleaned = cleaned[json_start:json_end].strip()
        elif "{" in cleaned:
            json_start = cleaned.find("{")
            json_end = cleaned.rfind("}") + 1
            cleaned = cleaned[json_start:json_end]

        try:
            response_json = json.loads(cleaned)
        except json.JSONDecodeError:
            return []

        raw_mappings = []
        if isinstance(response_json, list):
            raw_mappings = response_json
        elif isinstance(response_json, dict):
            for key in ("mappings", "mapping", "results", "columns", "items", "data"):
                if key in response_json and isinstance(response_json[key], list):
                    raw_mappings = response_json[key]
                    break
            if not raw_mappings and any(isinstance(v, dict) for v in response_json.values()):
                raw_mappings = [response_json]

        mappings: List[ColumnMapping] = []
        for mapping_dict in raw_mappings:
            if not isinstance(mapping_dict, dict):
                continue

            source_column = mapping_dict.get("source_column") or mapping_dict.get("source") or mapping_dict.get("column") or mapping_dict.get("name")
            suggested_target = mapping_dict.get("suggested_target") or mapping_dict.get("target") or mapping_dict.get("canonical_field") or mapping_dict.get("mapped_to")
            target_table = mapping_dict.get("target_table") or mapping_dict.get("table") or mapping_dict.get("canonical_table") or "unknown"
            confidence = mapping_dict.get("confidence", mapping_dict.get("score", 0.5))
            reasoning = mapping_dict.get("reasoning") or mapping_dict.get("reason") or mapping_dict.get("explanation") or ""
            data_type = mapping_dict.get("data_type") or mapping_dict.get("type") or "unknown"

            if not source_column or not suggested_target:
                continue

            try:
                confidence = float(confidence)
            except Exception:
                confidence = 0.5

            mappings.append(
                ColumnMapping(
                    source_column=str(source_column),
                    suggested_target=str(suggested_target),
                    confidence=confidence,
                    target_table=str(target_table),
                    reasoning=str(reasoning),
                    data_type=str(data_type),
                )
            )

        return mappings
    
    def _try_claude(self, profiles: Dict[str, Dict[str, Any]]) -> Optional[List[ColumnMapping]]:
        """Attempt to use Claude API (requires ANTHROPIC_API_KEY)."""
        
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("   ✗ ANTHROPIC_API_KEY not set")
            return None
        
        try:
            from anthropic import Anthropic
        except ImportError:
            print("   ✗ Anthropic SDK not installed: pip install anthropic")
            return None
        
        client = Anthropic()
        
        # Build the prompt (with optional RAG)
        if hasattr(self, '_retriever') and self._retriever:
            print(f"   Using RAG retrieval for smart context...")
            prompt = self.build_prompt_with_rag(profiles, self._retriever)
        else:
            print(f"   Using standard prompt (no RAG)")
            prompt = self.build_prompt(profiles)
        
        print(f"\n   Sending to Claude (claude-3-5-sonnet)...")
        print(f"      Prompt size: {len(prompt)} characters")
        
        try:
            # Call Claude
            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Extract the response
            response_text = message.content[0].text
            
            # Parse JSON from response
            try:
                # Claude might wrap JSON in markdown code blocks
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()
                
                response_json = json.loads(response_text)
                
                # Convert to ColumnMapping objects
                mappings = []
                for mapping_dict in response_json.get("mappings", []):
                    mapping = ColumnMapping(
                        source_column=mapping_dict["source_column"],
                        suggested_target=mapping_dict["suggested_target"],
                        confidence=mapping_dict["confidence"],
                        target_table=mapping_dict["target_table"],
                        reasoning=mapping_dict["reasoning"],
                        data_type=mapping_dict.get("data_type", "unknown")
                    )
                    mappings.append(mapping)
                
                print(f"   ✓ Claude returned {len(mappings)} column mappings\n")
                return mappings
            
            except json.JSONDecodeError as e:
                print(f"   ✗ Failed to parse Claude's JSON: {e}")
                print(f"      Response: {response_text[:200]}")
                return None
        
        except Exception as e:
            print(f"   ✗ Claude API failed: {e}")
            return None
    
    def _demo_mappings(self, profiles: Dict[str, Dict[str, Any]]) -> List[ColumnMapping]:
        """
        Generate demo/sample mappings for UI testing when LLMs are unavailable.
        This uses heuristic matching on column names.
        """
        print("\n   Using DEMO MODE - smart heuristic matching\n")
        
        mappings = []
        
        # Common column name patterns and their mappings
        patterns = {
            # Names (very common patterns first)
            r"emp_nm|empnm|emp_name|employee_nm|employee_name|fname|first.*name|full.*name|full_name|employee.*name|name": 
                ("name", "employees", 0.95, "Matches common employee name patterns"),
            r"emp.*id|employee.*id|empid":
                ("employee_id", "employees", 0.95, "Clearly marked as employee ID"),
            r"nat.*id|national.*id|nid|eid|national_id":
                ("national_id", "employees", 0.90, "National ID abbreviation"),
            
            # Dates
            r"hire.*date|join.*date|start.*date|hiredate|hire_dt":
                ("hire_date", "employees", 0.90, "Hire/join date pattern"),
            r"visa.*exp|exp.*date|expiry|visa_exp":
                ("visa_expiry", "employees", 0.85, "Visa expiry pattern"),
            
            # Salary
            r"base.*salary|salary|base_sal|base_salary":
                ("base_salary", "contracts", 0.95, "Base salary field"),
            r"housing|h_allow|house_allow|housing_all|housing_allowance":
                ("housing_allowance", "contracts", 0.90, "Housing allowance"),
            r"transport|t_allow|trans_allow|transport_allowance":
                ("transport_allowance", "contracts", 0.90, "Transport allowance"),
            
            # Leave
            r"annual.*leave.*entitle|al_entitle|anl_ent|annual_entitlement":
                ("annual_leave_entitlement", "leave_balances", 0.90, "Annual leave entitlement"),
            r"annual.*leave.*used|al_used|annual_leave_used":
                ("annual_leave_used", "leave_balances", 0.90, "Annual leave used"),
            r"sick.*leave.*entitle|sl_entitle|sick_leave_entitlement":
                ("sick_leave_entitlement", "leave_balances", 0.90, "Sick leave entitlement"),
            
            # Payroll
            r"overtime.*weekday|ot_weekday|ot_hours|overtime_hours_weekday":
                ("overtime_hours_weekday", "payroll_runs", 0.85, "Weekday overtime hours"),
            r"overtime.*rate|ot_rate|overtime_rate|ot_rate_multiplier":
                ("overtime_rate", "payroll_runs", 0.85, "Overtime rate"),
        }
        
        # Process each column from profiles
        for source_name, profile in profiles.items():
            if "columns" not in profile:
                continue
            
            for col_profile in profile["columns"]:
                col_name = col_profile["name"].lower().strip()
                col_type = col_profile.get("inferred_type", "unknown")
                
                # Try to match against patterns
                matched = False
                for pattern, (target, table, confidence, reason) in patterns.items():
                    import re
                    if re.search(pattern, col_name, re.IGNORECASE):
                        mapping = ColumnMapping(
                            source_column=col_profile["name"],
                            suggested_target=target,
                            confidence=confidence,
                            target_table=table,
                            reasoning=reason,
                            data_type=col_type
                        )
                        mappings.append(mapping)
                        matched = True
                        break
                
                # If no match, skip this column
                if not matched:
                    pass  # Could add as SKIP mapping if needed
        
        print(f"   [OK] Generated {len(mappings)} demo mappings using heuristics\n")
        return mappings
    
    def print_mappings(self, mappings: List[ColumnMapping]) -> None:
        """Pretty-print the mapped columns."""
        
        print("\n" + "=" * 100)
        print("COLUMN MAPPING RESULTS")
        print("=" * 100)
        
        # Group by confidence level
        high_confidence = [m for m in mappings if m.confidence >= 0.8]
        medium_confidence = [m for m in mappings if 0.5 <= m.confidence < 0.8]
        low_confidence = [m for m in mappings if m.confidence < 0.5]
        
        print(f"\n🟢 HIGH CONFIDENCE ({len(high_confidence)} mappings, 80%+):")
        for m in high_confidence:
            print(f"   {m.source_column:<20} → {m.suggested_target:<25} "
                  f"[{m.confidence:.0%}] {m.target_table}")
            print(f"      └─ {m.reasoning}\n")
        
        print(f"\n🟡 MEDIUM CONFIDENCE ({len(medium_confidence)} mappings, 50-80%):")
        for m in medium_confidence:
            print(f"   {m.source_column:<20} → {m.suggested_target:<25} "
                  f"[{m.confidence:.0%}] {m.target_table}")
            print(f"      └─ {m.reasoning}\n")
        
        print(f"\n🔴 LOW CONFIDENCE ({len(low_confidence)} mappings, <50%):")
        for m in low_confidence:
            print(f"   {m.source_column:<20} → {m.suggested_target:<25} "
                  f"[{m.confidence:.0%}] {m.target_table}")
            print(f"      └─ {m.reasoning}\n")
        
        # Summary
        print("\n" + "=" * 100)
        print(f"SUMMARY: {len(mappings)} total mappings")
        print(f"  Average confidence: {sum(m.confidence for m in mappings) / len(mappings) * 100:.1f}%")
        print(f"  Ready to use (80%+): {len(high_confidence)}")
        print(f"  Needs review: {len(medium_confidence) + len(low_confidence)}")


if __name__ == "__main__":
    # This is how Phase 2 gets called
    
    from ingestion import DataIngestionPipeline
    
    # Step 1: Re-run ingestion to get profiles
    print(" [Step 1/2] Loading and profiling CSV files...\n")
    pipeline = DataIngestionPipeline(data_dir="datasets")
    profiles = pipeline.ingest_all()
    
    # Step 2: Map columns using best available LLM
    print("\n" + "=" * 100)
    print("PHASE 2: COLUMN MAPPING WITH LLM")
    print("=" * 100)
    
    mapper = ColumnMapper()
    mappings = mapper.map_columns_with_llm(profiles)
    
    if mappings:
        mapper.print_mappings(mappings)
    else:
        print("\n Column mapping failed. See errors above.")

