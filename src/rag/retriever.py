"""
RETRIEVER — Core RAG Logic
===========================

Why this matters:
  This is where RAG happens.
  Instead of sending ALL columns to the LLM,
  we RETRIEVE only the SIMILAR ones.
  
  Then we AUGMENT the LLM prompt with these examples.
  Then the LLM makes better decisions.

The RAG Loop (what this module implements):
  1. User asks: "How do I map 'emp_nm'?"
  2. We embed 'emp_nm' description
  3. We search vector store for similar column descriptions
  4. We get back: "name is 85% similar", "employee_name is 90% similar"
  5. We add these as EXAMPLES to the LLM prompt
  6. LLM sees examples → better reasoning
  7. Result: better mapping with less hallucination

This is how modern AI systems work (ChatGPT plugins, Copilot Compose, etc.).
You're building the scaffolding.
"""

from typing import List, Dict, Any, Optional
import json


class Retriever:
    """Retrieve relevant context for column mapping."""
    
    def __init__(self, vector_store, embedder):
        """
        Args:
            vector_store: VectorStore instance (FAISS-powered)
            embedder: TextEmbedder instance
        """
        self.store = vector_store
        self.embedder = embedder
    
    def retrieve_similar_columns(
        self,
        messy_column_name: str,
        messy_column_type: str,
        messy_samples: List[str],
        k: int = 3
    ) -> Dict[str, Any]:
        """
        Retrieve similar canonical fields for a messy column.
        
        This is the core RAG retrieval step.
        
        Args:
            messy_column_name: e.g., "emp_nm"
            messy_column_type: e.g., "string"
            messy_samples: e.g., ["Ahmed", "Sarah"]
            k: how many results to return
        
        Returns:
            Dict with:
              - query_embedding: the vector we searched with
              - similar_fields: list of similar canonical fields
              - formatted_for_prompt: text to inject in LLM prompt
        """
        
        # Step 1: Embed the messy column
        query_emb_obj = self.embedder.embed_column_description(
            column_name=messy_column_name,
            column_type=messy_column_type,
            samples=messy_samples,
            metadata={"role": "query"}
        )
        
        # Step 2: Search vector store
        search_results = self.store.search(query_emb_obj.vector, k=k)
        
        # Step 3: Format results for LLM consumption
        similar_fields = []
        for result in search_results:
            meta = result["metadata"]
            
            # Extract the most important fields
            field_info = {
                "rank": result["rank"],
                "similarity": result["similarity"],
                "canonical_name": meta.get("canonical_name", "unknown"),
                "table": meta.get("table", "unknown"),
                "compliance_critical": meta.get("compliance_critical", False),
                "description": meta.get("text", "")[:100],  # truncate for readability
            }
            
            similar_fields.append(field_info)
        
        # Step 4: Format as text for the LLM prompt
        formatted_for_prompt = self._format_for_prompt(
            messy_column_name,
            similar_fields
        )
        
        return {
            "messy_column": {
                "name": messy_column_name,
                "type": messy_column_type,
                "samples": messy_samples
            },
            "similar_fields": similar_fields,
            "formatted_for_prompt": formatted_for_prompt,
            "num_results": len(similar_fields)
        }
    
    def _format_for_prompt(
        self,
        messy_column_name: str,
        similar_fields: List[Dict[str, Any]]
    ) -> str:
        """
        Format retrieved similar fields as text for the LLM prompt.
        
        This is what gets injected into the mapper.py prompt.
        """
        
        if not similar_fields:
            return f"No similar canonical fields found for '{messy_column_name}'."
        
        formatted = f"For column '{messy_column_name}', here are similar canonical fields:\n\n"
        
        for field in similar_fields:
            formatted += f"  • {field['canonical_name']} ({field['similarity']*100:.0f}% match)\n"
            formatted += f"    - Table: {field['table']}\n"
            
            if field.get("compliance_critical"):
                formatted += f"    - ⚠️  COMPLIANCE CRITICAL\n"
            
            formatted += f"    - Context: {field['description']}\n\n"
        
        return formatted
    
    def batch_retrieve(
        self,
        column_profiles: List[Dict[str, Any]],
        k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve context for MULTIPLE columns at once.
        
        Args:
            column_profiles: List of column descriptions from ingestion.py
            k: results per column
        
        Returns:
            List of retrieval results
        """
        
        all_retrievals = []
        
        for profile in column_profiles:
            retrieval = self.retrieve_similar_columns(
                messy_column_name=profile.get("name", "unknown"),
                messy_column_type=profile.get("inferred_type", "unknown"),
                messy_samples=profile.get("sample_values", []),
                k=k
            )
            all_retrievals.append(retrieval)
        
        return all_retrievals


class RAGContext:
    """
    Build the complete RAG context for mapping a single file.
    
    This orchestrates:
    1. Profile columns
    2. Retrieve similar fields
    3. Combine into a smart prompt for the LLM
    """
    
    def __init__(self, retriever: Retriever):
        self.retriever = retriever
    
    def build_mapping_context(
        self,
        csv_profile: Dict[str, Any],
        use_retrieval: bool = True,
        k_similar: int = 3
    ) -> str:
        """
        Build a complete, RAG-augmented prompt for mapping a CSV.
        
        Args:
            csv_profile: Profile from ingestion.py
            use_retrieval: whether to include retrieved examples (RAG)
            k_similar: how many similar fields to retrieve
        
        Returns:
            Complete prompt text ready for LLM
        """
        
        source_name = csv_profile.get("source_name", "unknown_file")
        row_count = csv_profile.get("row_count", 0)
        columns = csv_profile.get("columns", [])
        
        prompt = f"""You are an HR data migration specialist mapping CSV columns to a canonical schema.

FILE: {source_name} ({row_count} rows)

TASK: For each column, suggest the best canonical target field.

---
COLUMNS TO MAP:\n"""
        
        # Add each column with retrieval results
        for col_profile in columns:
            col_name = col_profile.get("name", "unknown")
            col_type = col_profile.get("inferred_type", "unknown")
            samples = col_profile.get("sample_values", [])
            
            prompt += f"\n**{col_name}** (type: {col_type})\n"
            prompt += f"  Samples: {', '.join(samples[:2])}\n"
            
            # RAG: retrieve similar fields
            if use_retrieval:
                retrieval = self.retriever.retrieve_similar_columns(
                    messy_column_name=col_name,
                    messy_column_type=col_type,
                    messy_samples=samples,
                    k=k_similar
                )
                
                # Add retrieved context
                if retrieval["similar_fields"]:
                    prompt += "  Related canonical fields:\n"
                    for field in retrieval["similar_fields"][:2]:  # show top 2
                        prompt += f"    - {field['canonical_name']} ({field['similarity']*100:.0f}%)\n"
        
        prompt += """

RESPOND WITH JSON:
{
  "mappings": [
    {
      "source_column": "emp_nm",
      "suggested_target": "name",
      "target_table": "employees",
      "confidence": 0.95,
      "reasoning": "Similar to 'name' field (95% match)"
    }
  ]
}

Return only valid JSON, no markdown."""
        
        return prompt


if __name__ == "__main__":
    # Test the retriever
    
    print("\n🎣 Testing Retriever (RAG Core)")
    print("=" * 70)
    
    # Setup
    from src.rag.vector_store import VectorStoreBuilder
    from src.embedder import TextEmbedder
    
    print("\n1️⃣  Building vector store...")
    builder = VectorStoreBuilder()
    canonical_fields = {
        "employees": ["name", "employee_id", "national_id", "hire_date"],
        "contracts": ["base_salary"],
        "payroll": ["overtime_hours_weekday"],
    }
    store = builder.build(canonical_fields)
    
    print("\n2️⃣  Setting up retriever...")
    embedder = TextEmbedder()
    retriever = Retriever(store, embedder)
    
    print("\n3️⃣  Retrieving context for 'emp_nm'...")
    result = retriever.retrieve_similar_columns(
        messy_column_name="emp_nm",
        messy_column_type="string",
        messy_samples=["Ahmed Al Mansouri", "Sarah Johnson"],
        k=3
    )
    
    print(f"\nFound {result['num_results']} similar fields:")
    print(result["formatted_for_prompt"])
    
    print("✓ Retriever working!")
