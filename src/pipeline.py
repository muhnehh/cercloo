"""
PIPELINE — Orchestrates the complete RAG system
================================================

What this does:
  Coordinates all the pieces:
  1. Ingestion → profile the data
  2. Embedder → create embeddings of canonical schema
  3. Vector Store → index all canonical fields
  4. Retriever → set up RAG retrieval
  5. Mapper → map columns with RAG-augmented prompts

Why unified pipeline:
  Real data systems need orchestration.
  Pipelines manage state, error handling, caching, logging.
  This is comparable to Airflow/Prefect/Dagster but simpler.

Educational point:
  This is how you structure a production ML system.
  All pieces work together; no piece is isolated.
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import sys

# Add src to path for module discovery
sys.path.insert(0, str(Path(__file__).parent))

from ingestion import DataIngestionPipeline
from schema import CANONICAL_SCHEMA
from mapper import ColumnMapper

# Compliance checker (optional)
try:
    from compliance.integration import ComplianceIntegration
except:
    try:
        from src.compliance.integration import ComplianceIntegration
    except:
        ComplianceIntegration = None


class RAGMappingPipeline:
    """
    End-to-end RAG column mapping system.
    
    Handles: ingestion → embedding → retrieval → mapping
    """
    
    def __init__(
        self,
        data_dir: str = "datasets",
        use_rag: bool = True,
        cache_vectors: bool = True,
        vector_cache_path: str = ".cache/vectors.st",
        check_compliance: bool = False,
        jurisdiction: str = "UAE"
    ):
        """
        Initialize the pipeline.
        
        Args:
            data_dir: where CSV files live
            use_rag: whether to use vector retrieval
            cache_vectors: whether to save/load vector store
            vector_cache_path: where to cache vectors
            check_compliance: whether to run compliance checks (requires clean data)
            jurisdiction: compliance jurisdiction (UAE, KSA, etc)
        """
        self.data_dir = data_dir
        self.use_rag = use_rag
        self.cache_vectors = cache_vectors
        self.vector_cache_path = vector_cache_path
        self.check_compliance = check_compliance and ComplianceIntegration is not None
        self.jurisdiction = jurisdiction
        
        # Components (initialized on demand)
        self.ingestion_pipeline = None
        self.embedder = None
        self.vector_store = None
        self.retriever = None
        self.mapper = None
        self.compliance_checker = None
        
        if self.check_compliance:
            self.compliance_checker = ComplianceIntegration(jurisdiction=jurisdiction)
    
    def run(self) -> Dict[str, Any]:
        """
        Execute the complete pipeline.
        
        Returns:
            {
                "profiles": CSV profiles,
                "mappings": column mappings,
                "compliance_report": compliance violations (if enabled),
                "statistics": timing/quality stats,
                "rag_info": info about retrieval performance
            }
        """
        
        print("\n" + "="*80)
        print("RAG COLUMN MAPPING PIPELINE")
        print("="*80)
        
        # Step 1: Data ingestion
        print("\n[1/6] 📂 Loading and profiling CSV files...")
        profiles = self._step_ingest()
        
        # Step 2: Build RAG if enabled
        if self.use_rag:
            print("\n[2/6] 🧬 Initializing RAG retrieval system...")
            self._step_build_rag()
        else:
            print("\n[2/6] ⏭️  RAG disabled, skipping retrieval setup")
        
        # Step 3: Map columns
        print("\n[3/6] 🗺️  Mapping columns with LLM...")
        mappings = self._step_map(profiles)
        
        # Step 4: Store learned mappings
        if self.use_rag and self.retriever:
            print("\n[4/6] 💾 Storing mappings back in vector store (learning)...")
            self._step_store_learnings(mappings)
        else:
            print("\n[4/6] ⏭️  Skipping storage (RAG disabled)")
        
        # Step 5: Check compliance (optional)
        compliance_result = None
        if self.check_compliance:
            print("\n[5/6] ✅ Running compliance checks...")
            compliance_result = self._step_check_compliance(profiles)
        else:
            print("\n[5/6] ⏭️  Compliance check disabled")
        
        # Step 6: Report results
        print("\n[6/6] 📊 Generating results...")
        results = self._step_report(profiles, mappings, compliance_result)
        
        print("\n" + "="*80)
        print("✓ PIPELINE COMPLETE")
        print("="*80)
        
        return results
    
    def _step_ingest(self) -> Dict[str, Dict[str, Any]]:
        """Step 1: Load and profile CSV files."""
        
        self.ingestion_pipeline = DataIngestionPipeline(self.data_dir)
        profiles = self.ingestion_pipeline.ingest_all()
        
        print(f"  ✓ Loaded {len(profiles)} CSV files")
        for name, profile in profiles.items():
            print(f"    • {name}: {profile['row_count']} rows, {profile['column_count']} columns")
        
        return profiles
    
    def _step_build_rag(self) -> None:
        """Step 2: Build RAG system (embeddings + vector store + retriever)."""
        
        try:
            from rag.vector_store import VectorStoreBuilder
            from rag.retriever import Retriever
            from embedder import TextEmbedder
        except ImportError:
            try:
                from src.rag.vector_store import VectorStoreBuilder
                from src.rag.retriever import Retriever
                from src.embedder import TextEmbedder
            except ImportError:
                print("  ✗ Failed to import RAG modules")
                self.use_rag = False
                return
        
        # Check cache first
        if self.cache_vectors and Path(self.vector_cache_path).with_suffix(".idx").exists():
            print(f"  📚 Loading cached vector store...")
            try:
                self.vector_store = VectorStoreBuilder().store
                self.vector_store.load(self.vector_cache_path)
                print(f"  ✓ Loaded {self.vector_store.stats()['total_vectors']} cached vectors")
            except Exception as e:
                print(f"  ⚠️  Failed to load cache: {e}, rebuilding...")
                self.vector_store = None
        
        # Build vector store if not cached
        if not self.vector_store:
            print(f"  🧬 Building vector store from canonical schema...")
            
            # Extract canonical fields for indexing
            canonical_fields = {}
            for table, fields in CANONICAL_SCHEMA.items():
                canonical_fields[table] = fields.get("fields", [])
            
            builder = VectorStoreBuilder()
            self.vector_store = builder.build(canonical_fields)
            
            # Cache it
            if self.cache_vectors:
                Path(self.vector_cache_path).parent.mkdir(parents=True, exist_ok=True)
                self.vector_store.save(self.vector_cache_path)
            
            print(f"  ✓ Vector store built: {self.vector_store.stats()['total_vectors']} vectors")
        
        # Setup retriever
        self.embedder = TextEmbedder()
        self.retriever = Retriever(self.vector_store, self.embedder)
        
        print(f"  ✓ RAG system ready")
    
    def _step_map(self, profiles: Dict[str, Dict[str, Any]]) -> List[Any]:
        """Step 3: Map columns using LLM + RAG."""
        
        self.mapper = ColumnMapper()
        
        print(f"  🤖 Initializing LLM mapper...")
        
        # Map with RAG if available
        mappings = self.mapper.map_columns_with_llm(
            profiles,
            retriever=self.retriever if self.use_rag else None
        )
        
        if mappings:
            print(f"  ✓ Generated {len(mappings)} column mappings")
            return mappings
        else:
            print(f"  ✗ Mapping failed")
            return []
    
    def _step_store_learnings(self, mappings: List[Any]) -> None:
        """Step 4: Store successful mappings back in vector store for self-improvement."""
        
        if not mappings or not self.retriever:
            return
        
        # Convert successful mappings to embedding examples
        try:
            from embedder import TextEmbedder
        except:
            from src.embedder import TextEmbedder
        
        print(f"  📚 Converting learned mappings to embeddings...")
        
        # Extract high-confidence mappings
        high_confidence = [m for m in mappings if m.confidence >= 0.80]
        
        if high_confidence:
            embedder = TextEmbedder()
            
            embedding_examples = []
            for mapping in high_confidence:
                emb = embedder.embed_mapping_example(
                    source_column=mapping.source_column,
                    target_column=mapping.suggested_target,
                    confidence=mapping.confidence,
                    reasoning=mapping.reasoning
                )
                embedding_examples.append(emb)
            
            # Add to vector store for future learning
            self.vector_store.add_embeddings(embedding_examples, source="learned_mappings")
            
            # Save updated store
            if self.cache_vectors:
                self.vector_store.save(self.vector_cache_path)
            
            print(f"  ✓ Stored {len(high_confidence)} learnings in vector store")
    
    def _step_check_compliance(self, profiles: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Step 5: Check compliance violations against employee data (if enabled)."""
        
        if not self.compliance_checker:
            return None
        
        try:
            # Try to load employee data from profiles
            # This would require the data to be mapped to canonical schema first
            # For now, we return a placeholder
            
            print(f"  ℹ️  Note: Compliance checks require clean canonical data")
            print(f"  Use ComplianceIntegration.check_company_data() with mapped data")
            
            return {
                "status": "ready",
                "jurisdiction": self.jurisdiction,
                "enabled": True
            }
        
        except Exception as e:
            print(f"  ✗ Compliance check failed: {e}")
            return None
    
    def _step_report(
        self,
        profiles: Dict[str, Dict[str, Any]],
        mappings: List[Any],
        compliance_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Step 6: Generate results summary."""
        
        report = {
            "profiles": profiles,
            "mappings": mappings,
            "compliance": compliance_result,
            "statistics": {
                "total_columns": sum(p["column_count"] for p in profiles.values()),
                "total_rows": sum(p["row_count"] for p in profiles.values()),
                "successful_mappings": len(mappings),
                "high_confidence_mappings": len([m for m in mappings if m.confidence >= 0.8]),
            },
            "rag_info": {
                "enabled": self.use_rag,
                "vector_store_size": (
                    self.vector_store.stats() if self.vector_store else None
                ),
            }
        }
        
        # Pretty print stats
        stats = report["statistics"]
        print(f"  Mapped {stats['successful_mappings']} / {stats['total_columns']} columns")
        print(f"  High-confidence: {stats['high_confidence_mappings']} ({stats['high_confidence_mappings']/stats['total_columns']*100:.0f}%)")
        
        if compliance_result and compliance_result.get("status") == "ready":
            print(f"  ✓ Compliance checker ready for {compliance_result['jurisdiction']}")
        
        return report


if __name__ == "__main__":
    # Run the complete pipeline with compliance checking
    
    pipeline = RAGMappingPipeline(
        data_dir="datasets",
        use_rag=True,  # Try RAG
        cache_vectors=True,  # Cache vectors for speed
        check_compliance=True,  # Also run compliance checks
        jurisdiction="UAE"
    )
    
    results = pipeline.run()
    
    # Print results
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    
    if results["mappings"]:
        print("\nTop 5 mappings:")
        for mapping in results["mappings"][:5]:
            print(f"  {mapping.source_column:<20} → {mapping.suggested_target:<20} ({mapping.confidence*100:.0f}%)")
    else:
        print("\nNo mappings generated. Check errors above.")
    
    if results["compliance"]:
        print(f"\nCompliance Status: {results['compliance']}")
