"""
DATA INGESTION & PROFILING MODULE
==================================

What this does:
  1. Loads messy CSVs (employee_master, payroll_run, leave_records)
  2. Profiles each one (column names, types, nulls, sample values)
  3. Returns a structured summary that NEXT STEP sends to the LLM mapper

Why this matters:
  The LLM needs to understand the SOURCE data deeply before it can map columns.
  This module is your "eyes" on the data.
  
Educational point:
  Good data pipelines start with PROFILING — you need to know what you're dealing with.
  Real companies spend 80% of data engineering time on this step.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


class DataProfiler:
    """Profile a CSV to extract schema information."""
    
    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.df = pd.read_csv(filepath)
        self.name = self.filepath.stem  # filename without extension
    
    def profile(self) -> Dict[str, Any]:
        """
        Analyze the CSV and return profiling information.
        
        Returns:
        {
            "source_name": "employee_master",
            "row_count": 20,
            "columns": [
                {
                    "name": "emp_nm",
                    "inferred_type": "string",
                    "null_count": 1,
                    "null_percentage": 5.0,
                    "sample_values": ["Ahmed Al Mansouri", ...],
                    "unique_count": 20,
                    "numeric_stats": {...} or None
                },
                ...
            ]
        }
        """
        
        profile = {
            "source_name": self.name,
            "row_count": len(self.df),
            "column_count": len(self.df.columns),
            "columns": []
        }
        
        for col in self.df.columns:
            col_profile = self._profile_column(col)
            profile["columns"].append(col_profile)
        
        return profile
    
    def _profile_column(self, col: str) -> Dict[str, Any]:
        """Profile a single column."""
        
        series = self.df[col]
        null_count = series.isnull().sum()
        null_pct = (null_count / len(series)) * 100
        
        # Infer type
        inferred_type = self._infer_type(series)
        
        # Get sample values (non-null)
        sample_values = series.dropna().unique()[:3].tolist()
        
        col_profile = {
            "name": col,
            "inferred_type": inferred_type,
            "null_count": int(null_count),
            "null_percentage": round(null_pct, 1),
            "unique_count": series.nunique(),
            "sample_values": [str(v) for v in sample_values],
        }
        
        # Add numeric stats if applicable
        if inferred_type == "numeric":
            col_profile["numeric_stats"] = {
                "min": float(series.min()),
                "max": float(series.max()),
                "mean": float(series.mean()),
                "median": float(series.median()),
            }
        
        # Add categorical stats if few unique values
        if inferred_type == "categorical" or series.nunique() < 10:
            value_counts = series.value_counts().head(5).to_dict()
            col_profile["value_distribution"] = {str(k): int(v) for k, v in value_counts.items()}
        
        return col_profile
    
    @staticmethod
    def _infer_type(series: pd.Series) -> str:
        """Guess the semantic type of a column."""
        
        # Remove nulls
        non_null = series.dropna()
        
        if len(non_null) == 0:
            return "unknown"
        
        # Check if numeric
        try:
            pd.to_numeric(non_null)
            return "numeric"
        except (ValueError, TypeError):
            pass
        
        # Check if date
        date_formats = ["%d/%m/%Y", "%d-%b-%Y", "%Y/%m/%d", "%d.%m.%Y", 
                       "%Y-%m-%d", "%m/%d/%Y"]
        for fmt in date_formats:
            try:
                pd.to_datetime(non_null, format=fmt)
                return "date"
            except (ValueError, TypeError):
                pass
        
        # Heuristic: if short strings with no spaces, might be ID
        if all(isinstance(v, str) and len(v) < 20 and ' ' not in str(v) 
               for v in non_null.head()):
            return "identifier"
        
        # Default: string
        return "string"


class DataIngestionPipeline:
    """Load and profile all messy CSV files."""
    
    def __init__(self, data_dir: str = "datasets"):
        self.data_dir = Path(data_dir)
    
    def ingest_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Load and profile all CSV files in the data directory.
        
        Returns:
        {
            "employee_master": {...profile...},
            "payroll_run": {...profile...},
            "leave_records": {...profile...},
        }
        """
        
        profiles = {}
        
        # Ensure directory exists first
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)
        
        csv_files = list(self.data_dir.glob("*.csv"))
        
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in {self.data_dir}")
        
        print(f"\n📂 Loading {len(csv_files)} CSV files from {self.data_dir}...\n")
        
        for csv_file in sorted(csv_files):
            # Skip "gold standard" evaluations files for now
            if csv_file.stem in ["mapping_labels", "compliance_violations"]:
                continue
            
            try:
                print(f"  ⏳ Processing {csv_file.name}...")
                profiler = DataProfiler(str(csv_file))
                profile = profiler.profile()
                profiles[csv_file.stem] = profile
                print(f"  ✓ {csv_file.stem}: {profile['row_count']} rows, {profile['column_count']} columns\n")
            
            except Exception as e:
                print(f"  ✗ Error processing {csv_file.name}: {e}\n")
        
        return profiles
    
    def print_summary(self, profiles: Dict[str, Dict[str, Any]]) -> None:
        """
        Pretty-print the profiles so you can see what data you're working with.
        
        This is what you'll later send to Claude for column mapping.
        """
        
        print("\n" + "=" * 80)
        print("DATA PROFILING SUMMARY")
        print("=" * 80)
        
        for source_name, profile in profiles.items():
            print(f"\n📊 {source_name.upper()}")
            print(f"   Rows: {profile['row_count']} | Columns: {profile['column_count']}")
            print("   " + "-" * 70)
            
            for col_profile in profile["columns"]:
                col_name = col_profile["name"]
                col_type = col_profile["inferred_type"]
                nulls = col_profile["null_percentage"]
                samples = ", ".join(col_profile["sample_values"][:2])
                
                print(f"   • {col_name:<20} [{col_type:<12}] Nulls: {nulls:>5.1f}%")
                print(f"     Samples: {samples}")
                
                # Show numeric ranges if applicable
                if col_type == "numeric" and "numeric_stats" in col_profile:
                    stats = col_profile["numeric_stats"]
                    print(f"     Range: {stats['min']:.0f} - {stats['max']:.0f} "
                          f"(mean: {stats['mean']:.0f})")
                
                # Show value distribution if categorical
                if "value_distribution" in col_profile:
                    dist = col_profile["value_distribution"]
                    top_values = ", ".join(list(dist.keys())[:3])
                    print(f"     Values: {top_values}")
                
                print()


def prepare_for_llm_mapping(profiles: Dict[str, Dict[str, Any]]) -> str:
    """
    Convert profiles into a prompt for Claude to understand the mapping task.
    
    This is what you'll send to the Anthropic API next.
    The LLM will read this and say: "emp_nm probably maps to name",
    "joining_dt probably maps to hire_date", etc.
    """
    
    prompt = """You are an HR data scientist. A company has exported their legacy HR data as CSVs with messy column names and inconsistent formatting.

Your job: For each column, suggest the CANONICAL mapping (what we call it in our clean HR schema).

Here's the data you're working with:

"""
    
    for source_name, profile in profiles.items():
        prompt += f"\n### {source_name}\n"
        prompt += f"({profile['row_count']} employees, {profile['column_count']} fields)\n\n"
        
        for col_profile in profile["columns"]:
            prompt += f"**{col_profile['name']}** (inferred: {col_profile['inferred_type']})\n"
            prompt += f"  - Nulls: {col_profile['null_percentage']}%\n"
            prompt += f"  - Samples: {', '.join(col_profile['sample_values'])}\n\n"
    
    prompt += """
For each column, respond with JSON:
{
  "mappings": [
    {
      "source_column": "emp_nm",
      "suggested_target": "name",
      "confidence": 0.95,
      "target_table": "employees",
      "reasoning": "Full name of employee"
    }
  ]
}

Return ONLY valid JSON, no other text.
"""
    
    return prompt


if __name__ == "__main__":
    # Example usage — this is how you run Phase 1
    
    pipeline = DataIngestionPipeline(data_dir="datasets")
    
    # Step 1: Load and profile all CSVs
    profiles = pipeline.ingest_all()
    
    # Step 2: Print a nice summary
    pipeline.print_summary(profiles)
    
    # Step 3: Prepare the data for LLM mapping (next step)
    llm_prompt = prepare_for_llm_mapping(profiles)
    
    print("\n" + "=" * 80)
    print("READY FOR LLM MAPPING")
    print("=" * 80)
    print(f"\nGenerated prompt ({len(llm_prompt)} chars) ready to send to Claude.")
    print("\nNext step: mapper.py will call Anthropic API with this prompt.")
