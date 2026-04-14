"""
CERCLI AGENTIC ORCHESTRATOR
===========================

This module turns the existing HR migration pipeline into an agentic system.

What it does:
  1. Inspects the dataset and available labels
  2. Plans the next action from state, not from a fixed script
  3. Executes tools for ingestion, RAG, mapping, evaluation, compliance
  4. Reflects on the outcome and stores memory for the next run
  5. Exports machine-readable and human-readable artifacts

The goal is not to replace the existing components. The goal is to wrap them
in a control loop that behaves like an agent: plan -> act -> observe -> adapt.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

try:
    from ingestion import DataIngestionPipeline
    from mapper import ColumnMapper, ColumnMapping
    from compliance.integration import ComplianceIntegration
    from schema import CANONICAL_SCHEMA
except ImportError:
    from src.ingestion import DataIngestionPipeline
    from src.mapper import ColumnMapper, ColumnMapping
    from src.compliance.integration import ComplianceIntegration
    from src.schema import CANONICAL_SCHEMA


FIELD_ALIASES = {
    "full_name": "name",
    "employee_name": "name",
    "emirates_id": "national_id",
    "visa_expiry_date": "visa_expiry",
    "passport_expiry_date": "passport_expiry",
    "phone_number": "phone",
    "department_code": "department",
    "annual_leave_balance": "annual_leave_balance",
    "leave_balance_remaining": "annual_leave_balance",
    "annual_leave_carried_forward": "annual_leave_carried_forward",
    "carried_forward_days": "annual_leave_carried_forward",
    "overtime_hours": "overtime_hours_weekday",
    "gross_salary": "gross_pay",
    "net_salary": "net_pay",
    "employee_id": "employee_id",
    "base_salary": "base_salary",
    "housing_allowance": "housing_allowance",
    "transport_allowance": "transport_allowance",
    "probation_period_months": "probation_period_months",
    "visa_type": "visa_type",
    "nationality": "nationality",
    "hire_date": "hire_date",
    "job_title": "job_title",
}

EVALUATION_ALIASES = {
    "name": "name",
    "full_name": "name",
    "employee_name": "name",
    "employee_id": "employee_id",
    "hire_date": "hire_date",
    "job_title": "job_title",
    "national_id": "national_id",
    "emirates_id": "national_id",
    "visa_type": "visa_type",
    "visa_expiry": "visa_expiry",
    "visa_expiry_date": "visa_expiry",
    "passport_number": "passport_number",
    "passport_expiry": "passport_expiry",
    "passport_expiry_date": "passport_expiry",
    "department": "department",
    "department_code": "department",
    "base_salary": "base_salary",
    "housing_allowance": "housing_allowance",
    "transport_allowance": "transport_allowance",
    "annual_leave_balance": "annual_leave_balance",
    "annual_leave_carried_forward": "annual_leave_carried_forward",
    "overtime_hours": "overtime_hours",
    "overtime_hours_weekday": "overtime_hours",
    "overtime_rate_multiplier": "overtime_rate_multiplier",
    "gross_salary": "gross_salary",
    "net_salary": "net_salary",
}


@dataclass
class AgentStep:
    """One agent action and its observation."""

    name: str
    objective: str
    status: str = "pending"
    outcome: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRun:
    """Structured run record for traceability."""

    goal: str
    started_at: str
    finished_at: Optional[str] = None
    plan: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    evaluation: Dict[str, Any] = field(default_factory=dict)
    compliance: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, str] = field(default_factory=dict)


class CercliAgent:
    """
    Agentic wrapper around the Cercli HR migration stack.

    The agent decides what to do based on the state of the run:
      discover -> build context -> map -> evaluate -> remediate/review -> comply -> export
    """

    def __init__(
        self,
        data_dir: str = "datasets",
        output_dir: str = "outputs",
        jurisdiction: str = "UAE",
        use_rag: bool = True,
        confidence_threshold: float = 0.8,
        max_iterations: int = 2,
        memory_path: str = ".cache/cercli_agent_memory.json",
    ):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.jurisdiction = jurisdiction
        self.use_rag = use_rag
        self.confidence_threshold = confidence_threshold
        self.max_iterations = max(1, max_iterations)
        self.memory_path = Path(memory_path)
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)

        self.goal = "Autonomously migrate messy HR exports into canonical data and compliance artifacts."
        self.run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        self.memory = self._load_memory()
        self.run = AgentRun(goal=self.goal, started_at=datetime.utcnow().isoformat())

        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.raw_frames: Dict[str, pd.DataFrame] = {}
        self.mappings: List[ColumnMapping] = []
        self.retriever = None
        self.compliance_integration: Optional[ComplianceIntegration] = None
        self.mapping_evaluation: Dict[str, Any] = {}
        self.compliance_report: Dict[str, Any] = {}

    def plan(self) -> List[Dict[str, Any]]:
        """Produce the next action plan from current state."""

        plan = [
            {
                "step": "discover",
                "objective": "Inspect available source files and profile the inputs.",
                "success": "Profiles and raw frames are loaded.",
            },
            {
                "step": "build_context",
                "objective": "Build the retrieval context and canonical field index.",
                "success": "Retriever is ready or a fallback is recorded.",
            },
            {
                "step": "map",
                "objective": "Generate column mappings with the best available mapper.",
                "success": "Mappings exist with confidence scores.",
            },
            {
                "step": "evaluate",
                "objective": "Benchmark mappings against the labeled dataset when available.",
                "success": "Accuracy and review queue are computed.",
            },
            {
                "step": "compliance",
                "objective": "Materialize canonical records and run compliance checks.",
                "success": "Compliance report or readiness report is generated.",
            },
            {
                "step": "export",
                "objective": "Write agent artifacts and memory to disk.",
                "success": "JSON, CSV, and Markdown artifacts are saved.",
            },
        ]

        self.run.plan = plan
        return plan

    def run_agent(self) -> Dict[str, Any]:
        """Execute the agent loop end to end."""

        print("\n" + "=" * 88)
        print("CERCLI AGENT MODE")
        print("=" * 88)
        print(f"Goal: {self.goal}")
        print(f"Data directory: {self.data_dir}")
        print(f"Output directory: {self.output_dir}")
        print(f"Jurisdiction: {self.jurisdiction}")
        print("=" * 88)

        plan = self.plan()
        for item in plan:
            step = AgentStep(name=item["step"], objective=item["objective"])
            print(f"\n[{step.name.upper()}] {step.objective}")

            try:
                if step.name == "discover":
                    result = self._discover()
                elif step.name == "build_context":
                    result = self._build_context()
                elif step.name == "map":
                    result = self._map()
                elif step.name == "evaluate":
                    result = self._evaluate_mappings()
                elif step.name == "compliance":
                    result = self._run_compliance()
                elif step.name == "export":
                    result = self._export_artifacts()
                else:
                    result = {"status": "skipped", "reason": f"Unknown step: {step.name}"}

                step.status = "done"
                step.metrics = result if isinstance(result, dict) else {"result": result}
                step.outcome = item["success"]
                self.run.steps.append(asdict(step))
                print(f"  ok: {step.outcome}")

            except Exception as exc:
                step.status = "failed"
                step.outcome = str(exc)
                self.run.steps.append(asdict(step))
                print(f"  fail: {exc}")
                break

        self.run.finished_at = datetime.utcnow().isoformat()
        self.run.evaluation = self.mapping_evaluation
        self.run.compliance = self.compliance_report

        self.memory["last_run"] = self.run.finished_at
        self.memory["last_goal"] = self.goal
        self.memory["successful_mappings"] = self._memory_successful_mappings()
        self.memory["review_queue"] = self.mapping_evaluation.get("review_queue", [])
        self._save_memory()

        print("\n" + "=" * 88)
        print("AGENT COMPLETE")
        print("=" * 88)

        return {
            "run": asdict(self.run),
            "profiles": self.profiles,
            "mapping_evaluation": self.mapping_evaluation,
            "compliance_report": self.compliance_report,
            "artifacts": self.run.artifacts,
        }

    def _discover(self) -> Dict[str, Any]:
        ingestion = DataIngestionPipeline(str(self.data_dir))
        self.profiles = ingestion.ingest_all()

        self.raw_frames = {}
        for csv_path in sorted(self.data_dir.glob("*.csv")):
            if csv_path.stem in {"mapping_labels", "compliance_violations"}:
                continue
            try:
                self.raw_frames[csv_path.stem] = pd.read_csv(csv_path)
            except Exception:
                continue

        return {
            "status": "ok",
            "files": list(self.profiles.keys()),
            "total_files": len(self.profiles),
            "total_rows": sum(profile.get("row_count", 0) for profile in self.profiles.values()),
        }

    def _build_context(self) -> Dict[str, Any]:
        if not self.use_rag:
            self.retriever = None
            return {"status": "disabled", "reason": "RAG disabled by configuration"}

        try:
            try:
                from rag.vector_store import VectorStoreBuilder
                from rag.retriever import Retriever
                from embedder import TextEmbedder
            except ImportError:
                from src.rag.vector_store import VectorStoreBuilder
                from src.rag.retriever import Retriever
                from src.embedder import TextEmbedder

            canonical_fields: Dict[str, Any] = {}
            for table_name, table_info in CANONICAL_SCHEMA.items():
                canonical_fields[table_name] = table_info.get("fields", [])

            builder = VectorStoreBuilder()
            vector_store = builder.build(canonical_fields)
            self.retriever = Retriever(vector_store, TextEmbedder())

            return {
                "status": "ok",
                "vector_count": vector_store.stats().get("total_vectors", 0),
            }

        except Exception as exc:
            # Keep the agent loop alive even if vector/embedding backend fails.
            # Mapping can still continue via LLM/heuristic mode.
            self.retriever = None
            return {
                "status": "degraded",
                "reason": str(exc),
                "fallback": "continuing without retriever",
            }

    def _map(self) -> Dict[str, Any]:
        mapper = ColumnMapper()

        force_demo = os.environ.get("CERCLI_FORCE_DEMO", "0") == "1"
        if force_demo:
            self.mappings = mapper._demo_mappings(self.profiles)
        else:
            try:
                self.mappings = mapper.map_columns_with_llm(
                    self.profiles,
                    retriever=self.retriever if self.use_rag else None,
                )
            except Exception as exc:
                print(f"  map warning: {exc}")
                print("  map fallback: using deterministic demo mappings")
                self.mappings = mapper._demo_mappings(self.profiles)

        return {
            "status": "ok" if self.mappings else "empty",
            "mapping_count": len(self.mappings),
            "high_confidence": len([m for m in self.mappings if m.confidence >= self.confidence_threshold]),
        }

    def _evaluate_mappings(self) -> Dict[str, Any]:
        labels_path = self.data_dir / "mapping_labels.csv"
        review_queue: List[Dict[str, Any]] = []

        if not labels_path.exists() or not self.mappings:
            self.mapping_evaluation = {
                "labels_available": False,
                "accuracy": None,
                "coverage": None,
                "review_required": len([m for m in self.mappings if m.confidence < self.confidence_threshold]) > 0,
                "review_queue": self._low_confidence_queue(),
            }
            return self.mapping_evaluation

        labels = pd.read_csv(labels_path)
        expected = {
            (row.source_file, row.original_column): row.correct_canonical_mapping
            for _, row in labels.iterrows()
        }

        predicted = {(self._guess_source_file(mapping.source_column), mapping.source_column): mapping for mapping in self.mappings}

        matched = 0
        evaluated = 0
        for key, expected_target in expected.items():
            mapping = predicted.get(key)
            if not mapping:
                review_queue.append({
                    "source_file": key[0],
                    "source_column": key[1],
                    "expected": expected_target,
                    "predicted": None,
                    "reason": "missing prediction",
                })
                continue

            evaluated += 1
            predicted_family = self._family(mapping.suggested_target)
            expected_family = self._family(expected_target)

            if predicted_family == expected_family:
                matched += 1
            else:
                review_queue.append({
                    "source_file": key[0],
                    "source_column": key[1],
                    "expected": expected_target,
                    "predicted": mapping.suggested_target,
                    "confidence": mapping.confidence,
                    "reason": "family mismatch",
                })

        review_queue.extend(self._low_confidence_queue())

        accuracy = matched / evaluated if evaluated else None
        coverage = evaluated / len(expected) if expected else None
        review_required = bool(review_queue)

        self.mapping_evaluation = {
            "labels_available": True,
            "accuracy": accuracy,
            "coverage": coverage,
            "evaluated_columns": evaluated,
            "matched_columns": matched,
            "review_required": review_required,
            "review_queue": review_queue,
        }

        return self.mapping_evaluation

    def _run_compliance(self) -> Dict[str, Any]:
        self.compliance_integration = ComplianceIntegration(jurisdiction=self.jurisdiction)
        employees, contracts, leave_records, payroll_records = self._prepare_compliance_tables()

        violations = self.compliance_integration.check_company_data(
            employees,
            contracts,
            leave_records,
            payroll_records,
        )

        report = self.compliance_integration.generate_compliance_report(violations)
        self.compliance_report = report

        summary = report.get("summary", {})
        return {
            "status": "ok",
            "violations": len(violations),
            "critical": summary.get("critical", 0),
            "errors": summary.get("errors", 0),
            "warnings": summary.get("warnings", 0),
        }

    def _export_artifacts(self) -> Dict[str, Any]:
        session_dir = self.output_dir / f"agent_{self.run_id}"
        session_dir.mkdir(parents=True, exist_ok=True)

        artifacts: Dict[str, str] = {}

        run_json = session_dir / "agent_run.json"
        with open(run_json, "w", encoding="utf-8") as handle:
            json.dump(self._serializable_run(), handle, indent=2, default=str)
        artifacts["agent_run_json"] = str(run_json)

        summary_md = session_dir / "agent_summary.md"
        summary_md.write_text(self._build_summary_markdown(), encoding="utf-8")
        artifacts["agent_summary_md"] = str(summary_md)

        mappings_csv = session_dir / "column_mappings.csv"
        self._write_mappings_csv(mappings_csv)
        artifacts["column_mappings_csv"] = str(mappings_csv)

        review_csv = session_dir / "review_queue.csv"
        self._write_review_csv(review_csv)
        artifacts["review_queue_csv"] = str(review_csv)

        if self.compliance_report:
            compliance_json = session_dir / "compliance_report.json"
            with open(compliance_json, "w", encoding="utf-8") as handle:
                json.dump(self.compliance_report, handle, indent=2, default=str)
            artifacts["compliance_report_json"] = str(compliance_json)

        self.run.artifacts = artifacts
        return {"status": "ok", "artifacts": artifacts}

    def _serializable_run(self) -> Dict[str, Any]:
        return {
            "goal": self.run.goal,
            "started_at": self.run.started_at,
            "finished_at": self.run.finished_at,
            "plan": self.run.plan,
            "steps": self.run.steps,
            "evaluation": self.mapping_evaluation,
            "compliance": self.compliance_report,
            "artifacts": self.run.artifacts,
        }

    def _build_summary_markdown(self) -> str:
        mapping_stats = self.mapping_evaluation or {}
        compliance_stats = self.compliance_report or {}

        lines = [
            "# Cercli Agent Run",
            "",
            f"- Goal: {self.goal}",
            f"- Started: {self.run.started_at}",
            f"- Finished: {self.run.finished_at or 'in progress'}",
            f"- Jurisdiction: {self.jurisdiction}",
            "",
            "## Evaluation",
            f"- Labels available: {mapping_stats.get('labels_available', False)}",
            f"- Accuracy: {self._format_ratio(mapping_stats.get('accuracy'))}",
            f"- Coverage: {self._format_ratio(mapping_stats.get('coverage'))}",
            f"- Review required: {mapping_stats.get('review_required', False)}",
            "",
            "## Compliance",
        ]

        if compliance_stats:
            summary = compliance_stats.get("summary", {})
            lines.extend([
                f"- Critical: {summary.get('critical', 0)}",
                f"- Errors: {summary.get('errors', 0)}",
                f"- Warnings: {summary.get('warnings', 0)}",
                f"- Total violations: {compliance_stats.get('total_violations', 0)}",
            ])
        else:
            lines.append("- Compliance report was not generated.")

        lines.extend([
            "",
            "## Agent Memory",
            f"- Stored successful mappings: {len(self.memory.get('successful_mappings', {}))}",
            f"- Review queue items: {len(self.mapping_evaluation.get('review_queue', []))}",
        ])

        return "\n".join(lines)

    def _write_mappings_csv(self, path: Path) -> None:
        rows = []
        for mapping in self.mappings:
            rows.append({
                "source_column": mapping.source_column,
                "suggested_target": mapping.suggested_target,
                "target_table": mapping.target_table,
                "confidence": mapping.confidence,
                "data_type": mapping.data_type,
                "reasoning": mapping.reasoning,
            })

        pd.DataFrame(rows).to_csv(path, index=False)

    def _write_review_csv(self, path: Path) -> None:
        review_queue = self.mapping_evaluation.get("review_queue", [])
        pd.DataFrame(review_queue).to_csv(path, index=False)

    def _prepare_compliance_tables(self):
        if not self.raw_frames:
            return [], [], [], []

        labels = self._load_mapping_labels()
        label_lookup = self._label_lookup(labels)

        employee_records: List[Dict[str, Any]] = []
        contract_records: List[Dict[str, Any]] = []
        leave_records: List[Dict[str, Any]] = []
        payroll_records: List[Dict[str, Any]] = []

        if "employee_master" in self.raw_frames:
            employee_master = self._normalize_source_frame("employee_master", self.raw_frames["employee_master"], label_lookup)
            employee_records.extend(self._records_from_frame(
                employee_master,
                ["employee_id", "name", "national_id", "passport_number", "nationality", "hire_date", "visa_type", "visa_expiry", "job_title", "department"],
            ))
            contract_records.extend(self._records_from_frame(
                employee_master,
                ["employee_id", "base_salary", "housing_allowance", "transport_allowance", "probation_period_months"],
            ))
            leave_records.extend(self._records_from_frame(
                employee_master,
                ["employee_id", "annual_leave_entitlement", "annual_leave_used", "annual_leave_balance", "annual_leave_carried_forward"],
            ))

        if "leave_records" in self.raw_frames:
            leave_source = self._normalize_source_frame("leave_records", self.raw_frames["leave_records"], label_lookup)
            leave_records.extend(self._records_from_frame(
                leave_source,
                ["employee_id", "annual_leave_entitlement", "annual_leave_used", "annual_leave_balance", "annual_leave_carried_forward"],
                aggregate=True,
            ))

        if "payroll_run" in self.raw_frames:
            payroll_source = self._normalize_source_frame("payroll_run", self.raw_frames["payroll_run"], label_lookup)
            payroll_records.extend(self._records_from_frame(
                payroll_source,
                ["employee_id", "base_salary", "housing_allowance", "transport_allowance", "other_allowances", "overtime_hours_weekday", "overtime_hours_friday", "overtime_rate", "eos_gratuity"],
                aggregate=True,
            ))

        return employee_records, contract_records, leave_records, payroll_records

    def _normalize_source_frame(self, source_name: str, frame: pd.DataFrame, label_lookup: Dict[str, Dict[str, str]]) -> pd.DataFrame:
        rename_map = {}
        for original_column, target in label_lookup.get(source_name, {}).items():
            rename_map[original_column] = self._field_alias(target)

        normalized = frame.rename(columns=rename_map).copy()

        if "annual_leave_entitlement" in normalized.columns and "annual_leave_balance" in normalized.columns and "annual_leave_used" not in normalized.columns:
            normalized["annual_leave_used"] = normalized["annual_leave_entitlement"] - normalized["annual_leave_balance"]

        if "leave_balance_remaining" in normalized.columns and "annual_leave_balance" not in normalized.columns:
            normalized["annual_leave_balance"] = normalized["leave_balance_remaining"]

        if "carried_forward_days" in normalized.columns and "annual_leave_carried_forward" not in normalized.columns:
            normalized["annual_leave_carried_forward"] = normalized["carried_forward_days"]

        if "overtime_rate_multiplier" in normalized.columns and "base_salary" in normalized.columns:
            try:
                normalized["overtime_rate"] = (pd.to_numeric(normalized["base_salary"], errors="coerce") / 160.0) * pd.to_numeric(
                    normalized["overtime_rate_multiplier"], errors="coerce"
                )
            except Exception:
                pass

        return normalized

    def _records_from_frame(self, frame: pd.DataFrame, columns: List[str], aggregate: bool = False) -> List[Dict[str, Any]]:
        available_columns = [column for column in columns if column in frame.columns]
        if not available_columns or "employee_id" not in frame.columns:
            return []

        subset = frame[available_columns].copy()
        subset = subset.dropna(subset=["employee_id"])

        if aggregate:
            records: List[Dict[str, Any]] = []
            for employee_id, group in subset.groupby("employee_id", dropna=True):
                record: Dict[str, Any] = {"employee_id": employee_id}
                for column in available_columns:
                    if column == "employee_id":
                        continue
                    series = group[column].dropna()
                    if series.empty:
                        continue
                    if column == "annual_leave_used":
                        record[column] = float(pd.to_numeric(series, errors="coerce").fillna(0).sum())
                    elif column == "annual_leave_entitlement":
                        numeric = pd.to_numeric(series, errors="coerce").dropna()
                        if not numeric.empty:
                            record[column] = self._coerce_value(column, numeric.iloc[-1])
                    else:
                        record[column] = self._coerce_value(column, series.iloc[-1])

                if "annual_leave_entitlement" in record and "annual_leave_used" in record and "annual_leave_balance" not in record:
                    try:
                        record["annual_leave_balance"] = float(record["annual_leave_entitlement"]) - float(record["annual_leave_used"])
                    except Exception:
                        pass

                records.append(record)

            return records

        deduped = subset.drop_duplicates(subset=["employee_id"], keep="last")
        records = deduped.to_dict(orient="records")
        normalized_records: List[Dict[str, Any]] = []
        for row in records:
            normalized_records.append({
                key: self._coerce_value(key, value)
                for key, value in row.items()
            })
        return normalized_records

    def _coerce_value(self, column: str, value: Any) -> Any:
        if value is None:
            return None

        date_columns = {
            "hire_date",
            "visa_expiry",
            "passport_expiry",
            "start_date",
            "end_date",
            "pay_date",
            "period_start",
            "period_end",
        }
        int_columns = {"probation_period_months"}
        float_columns = {
            "base_salary",
            "housing_allowance",
            "transport_allowance",
            "other_allowances",
            "annual_leave_entitlement",
            "annual_leave_used",
            "annual_leave_balance",
            "annual_leave_carried_forward",
            "overtime_hours_weekday",
            "overtime_hours_friday",
            "overtime_rate",
            "eos_gratuity",
        }

        if column in date_columns:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.isna(parsed):
                return None
            return parsed.date()

        if column in int_columns:
            numeric = pd.to_numeric(value, errors="coerce")
            if pd.isna(numeric):
                return 0
            return int(numeric)

        if column in float_columns:
            numeric = pd.to_numeric(value, errors="coerce")
            if pd.isna(numeric):
                return 0.0
            return float(numeric)

        return value

    def _load_mapping_labels(self) -> Optional[pd.DataFrame]:
        labels_path = self.data_dir / "mapping_labels.csv"
        if not labels_path.exists():
            return None
        try:
            return pd.read_csv(labels_path)
        except Exception:
            return None

    def _label_lookup(self, labels: Optional[pd.DataFrame]) -> Dict[str, Dict[str, str]]:
        lookup: Dict[str, Dict[str, str]] = {}
        if labels is None:
            return lookup

        for _, row in labels.iterrows():
            source_file = str(row.source_file)
            original_column = str(row.original_column)
            correct_canonical_mapping = str(row.correct_canonical_mapping)

            lookup.setdefault(source_file, {})[original_column] = correct_canonical_mapping

        return lookup

    def _family(self, value: Any) -> str:
        normalized = str(value or "").strip().lower().replace(" ", "_")
        return EVALUATION_ALIASES.get(normalized, normalized)

    def _field_alias(self, value: Any) -> str:
        normalized = str(value or "").strip().lower().replace(" ", "_")
        return FIELD_ALIASES.get(normalized, normalized)

    def _guess_source_file(self, source_column: str) -> str:
        if source_column.startswith("pay_") or source_column.startswith("ot_"):
            return "payroll_run"
        if source_column.startswith("leave_") or source_column.startswith("annual_") or source_column.startswith("carry_"):
            return "leave_records"
        return "employee_master"

    def _low_confidence_queue(self) -> List[Dict[str, Any]]:
        queue = []
        for mapping in self.mappings:
            if mapping.confidence < self.confidence_threshold:
                queue.append({
                    "source_column": mapping.source_column,
                    "suggested_target": mapping.suggested_target,
                    "confidence": mapping.confidence,
                    "target_table": mapping.target_table,
                    "reason": "low confidence",
                })
        return queue

    def _memory_successful_mappings(self) -> Dict[str, str]:
        memory: Dict[str, str] = self.memory.get("successful_mappings", {})
        for mapping in self.mappings:
            if mapping.confidence >= self.confidence_threshold:
                memory[mapping.source_column] = mapping.suggested_target
        return memory

    def _load_memory(self) -> Dict[str, Any]:
        if not self.memory_path.exists():
            return {
                "successful_mappings": {},
                "review_queue": [],
                "last_goal": None,
                "last_run": None,
            }

        try:
            with open(self.memory_path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return {
                "successful_mappings": {},
                "review_queue": [],
                "last_goal": None,
                "last_run": None,
            }

    def _save_memory(self) -> None:
        with open(self.memory_path, "w", encoding="utf-8") as handle:
            json.dump(self.memory, handle, indent=2, default=str)

    def _format_ratio(self, value: Any) -> str:
        if value is None:
            return "n/a"
        try:
            return f"{float(value) * 100:.1f}%"
        except Exception:
            return str(value)


def run_agent_demo() -> Dict[str, Any]:
    """Convenience wrapper for scripts and tests."""

    agent = CercliAgent()
    return agent.run_agent()
