"""
VECTOR STORE — Manage embeddings with FAISS
============================================

Why this matters (RAG storage layer):
  You need to store THOUSANDS of embeddings and search them FAST.
  FAISS (Facebook AI Similarity Search) is the industry standard.
  
Educational point:
  - How to index vectors efficiently (hashing, quantization)
  - How to search similar vectors in milliseconds
  - This is what powers recommendation systems, search engines, etc.

How it works:
  1. You have N embeddings (canonical fields + past mappings)
  2. FAISS indexes them (builds a searchable database)
  3. At query time: give it your messy column embedding
  4. FAISS returns top-k most similar canonical fields
  5. You use those for the LLM prompt (RAG!)
"""

import numpy as np
from typing import List, Dict, Tuple, Any, Optional
import pickle
from pathlib import Path
import json


class VectorStore:
    """
    Manages embeddings for columns using FAISS.
    
    Two types of embeddings stored:
    1. CANONICAL fields (target schema) - the "north star"
    2. PAST MAPPINGS (learned examples) - self-improvement
    """
    
    def __init__(self, embedding_dim: int = 384):
        """Initialize empty vector store."""
        try:
            import faiss
            self.faiss = faiss
        except ImportError:
            raise ImportError(
                "FAISS not installed. Run:\n"
                "pip install faiss-cpu   (CPU version)\n"
                "or\n"
                "pip install faiss-gpu   (GPU version, if you have CUDA)"
            )
        
        self.embedding_dim = embedding_dim
        self.index = None  # Will be set up in add_to_index()
        self.metadata_list = []  # Parallel list of metadata for each vector
        self.initialized = False
    
    def initialize_index(self):
        """Create an empty FAISS index."""
        if not self.initialized:
            # Use simple L2 distance (Euclidean) for normalized embeddings
            # Alternative: use cosine distance via dot product
            self.index = self.faiss.IndexFlatL2(self.embedding_dim)
            self.initialized = True
    
    def add_embeddings(self, embeddings: List[Any], source: str = "unknown") -> int:
        """
        Add a batch of embeddings to the index.
        
        Args:
            embeddings: List of Embedding objects (from embedder.py)
            source: where these came from ("canonical", "past_mappings", etc.)
        
        Returns:
            Number of vectors added
        """
        
        if not self.initialized:
            self.initialize_index()
        
        vectors = []
        for emb in embeddings:
            vectors.append(emb.vector)
            
            # Store metadata alongside
            metadata_entry = {
                "text": emb.text,
                "source": source,
                "embedding_source": emb.source,
                **emb.metadata
            }
            self.metadata_list.append(metadata_entry)
        
        # Convert to numpy array (FAISS requirement)
        vectors_np = np.array(vectors, dtype=np.float32)
        
        # Add to index
        self.index.add(vectors_np)
        
        return len(vectors)
    
    def search(self, query_embedding: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        """
        Find the k most similar embeddings to the query.
        
        Args:
            query_embedding: vector to search for (shape: (384,))
            k: number of results to return
        
        Returns:
            List of dicts with:
              - distance: how close (lower = more similar)
              - rank: position (1st, 2nd, etc.)
              - metadata: the stored metadata
              - similarity_score: 1.0 / (1.0 + distance) for human readability
        """
        
        if not self.initialized or self.index.ntotal == 0:
            return []
        
        # FAISS expects batch queries (2D array)
        query_batch = np.array([query_embedding], dtype=np.float32)
        
        # Search (returns distances and indices)
        distances, indices = self.index.search(query_batch, k=min(k, self.index.ntotal))
        
        results = []
        for rank, idx in enumerate(indices[0], start=1):
            distance = float(distances[0][rank - 1])
            
            # Convert distance to 0-1 similarity score
            # (for L2 distance on normalized vectors, this is intuitive)
            similarity = 1.0 / (1.0 + distance)
            
            result = {
                "rank": rank,
                "distance": distance,
                "similarity": similarity,
                "metadata": self.metadata_list[idx]
            }
            results.append(result)
        
        return results
    
    def search_and_format(self, query_embedding: np.ndarray, k: int = 5) -> str:
        """
        Search and return a formatted string (for putting in LLM prompts).
        
        This is the key bridge between RAG retrieval and LLM reasoning!
        """
        
        results = self.search(query_embedding, k=k)
        
        if not results:
            return "No similar mappings found in vector store."
        
        formatted = "Similar mappings found:\n\n"
        for result in results:
            metadata = result["metadata"]
            similarity = result["similarity"]
            
            formatted += f"• {similarity*100:.0f}% similar\n"
            formatted += f"  {metadata.get('text', 'N/A')}\n\n"
        
        return formatted
    
    def save(self, filepath: str) -> None:
        """Save the vector store to disk (index + metadata)."""
        
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save FAISS index
        self.faiss.write_index(self.index, str(path.with_suffix(".idx")))
        
        # Save metadata as JSON
        with open(path.with_suffix(".meta.json"), "w") as f:
            json.dump(self.metadata_list, f, indent=2)
        
        print(f"✓ Vector store saved to {filepath}")
    
    def load(self, filepath: str) -> None:
        """Load vector store from disk."""
        
        path = Path(filepath)
        
        # Load FAISS index
        self.index = self.faiss.read_index(str(path.with_suffix(".idx")))
        self.initialized = True
        
        # Load metadata
        with open(path.with_suffix(".meta.json"), "r") as f:
            self.metadata_list = json.load(f)
        
        print(f"✓ Vector store loaded from {filepath}")
    
    def stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store."""
        
        if not self.initialized:
            return {"status": "not initialized"}
        
        return {
            "total_vectors": self.index.ntotal,
            "embedding_dimension": self.embedding_dim,
            "metadata_entries": len(self.metadata_list),
        }


class VectorStoreBuilder:
    """
    Helper to build a complete vector store from scratch.
    
    Combines canonical schema + past mappings into one searchable store.
    """
    
    def __init__(self, embedding_dim: int = 384):
        self.store = VectorStore(embedding_dim)
        self.embedder = None  # Will be set in build()
    
    def build(
        self,
        canonical_fields: Dict[str, List[str]],  # from schema
        past_mappings: Optional[List[Dict[str, Any]]] = None  # learned examples
    ) -> VectorStore:
        """
        Build a complete vector store.
        
        Args:
            canonical_fields: dictionary of tables → field names
            past_mappings: list of {"source": "...", "target": "...", "confidence": 0.9}
        
        Returns:
            Initialized and populated VectorStore
        """
        
        try:
            from embedder import TextEmbedder
        except ImportError:
            from src.embedder import TextEmbedder
        
        self.embedder = TextEmbedder()
        self.store.initialize_index()
        
        # Add canonical fields
        print("\n📚 Adding canonical schema to vector store...")
        canonical_descriptions = {
            "name": "Full name of the employee",
            "employee_id": "Unique identifier for the employee",
            "national_id": "National ID or Emirate ID (compliance required)",
            "passport_number": "Passport number (compliance required)",
            "nationality": "Country of origin (ISO code, e.g., AE, SA, IN)",
            "email": "Work email address",
            "phone": "Work phone number",
            "iban": "Bank account for payroll",
            "hire_date": "When employee started",
            "employment_type": "Full-time, Part-time, or Contractor",
            "job_title": "Job position",
            "department": "Department name",
            "visa_type": "Type of visa (Employment, Residence, etc.)",
            "visa_expiry": "When visa expires (compliance required)",
            "base_salary": "Monthly base compensation",
            "housing_allowance": "Housing allowance component",
            "transport_allowance": "Transportation allowance",
            "annual_leave_entitlement": "Legal annual leave days per year",
            "sick_leave_entitlement": "Legal sick leave days per year",
            "overtime_hours_weekday": "Hours worked beyond regular (paid 1.25x)",
            "overtime_hours_friday": "Friday/holiday hours (paid 1.5x)",
        }
        
        canonical_embeddings = []
        for field_name, description in canonical_descriptions.items():
            emb = self.embedder.embed_canonical_field(
                canonical_name=field_name,
                description=description,
                table="canonical_schema",
                compliance_critical="compliance" in description.lower()
            )
            canonical_embeddings.append(emb)
        
        self.store.add_embeddings(canonical_embeddings, source="canonical_schema")
        print(f"  ✓ Added {len(canonical_embeddings)} canonical fields")
        
        # Add past mappings if provided
        if past_mappings:
            print(f"\n📚 Adding {len(past_mappings)} past mappings for learning...")
            
            mapping_embeddings = []
            for mapping in past_mappings:
                emb = self.embedder.embed_mapping_example(
                    source_column=mapping.get("source", "unknown"),
                    target_column=mapping.get("target", "unknown"),
                    confidence=mapping.get("confidence", 0.5),
                    reasoning=mapping.get("reasoning", "")
                )
                mapping_embeddings.append(emb)
            
            self.store.add_embeddings(mapping_embeddings, source="past_mappings")
            print(f"  ✓ Added {len(mapping_embeddings)} past mappings")
        
        return self.store


if __name__ == "__main__":
    # Test the vector store
    
    print("\n🗂️  Testing Vector Store with FAISS")
    print("=" * 70)
    
    # Build a store
    builder = VectorStoreBuilder()
    canonical_fields = {
        "employees": ["name", "employee_id", "national_id", "hire_date"],
        "contracts": ["base_salary", "contract_id"],
        "payroll": ["overtime_hours_weekday", "overtime_rate"],
    }
    
    past_mappings = [
        {
            "source": "emp_nm",
            "target": "name",
            "confidence": 0.98,
            "reasoning": "Standard abbreviation for name"
        },
        {
            "source": "emp_no",
            "target": "employee_id",
            "confidence": 0.95,
            "reasoning": "Common abbreviation for employee number"
        },
    ]
    
    store = builder.build(canonical_fields, past_mappings)
    
    print(f"\n✓ Vector store built!")
    print(f"  Stats: {store.stats()}")
    
    # Test a search
    print("\n🔍 Testing vector search...")
    
    from src.embedder import TextEmbedder
    embedder = TextEmbedder()
    
    # Create a query: a messy column we want to map
    query_emb = embedder.embed_column_description(
        column_name="employee_name",
        column_type="string",
        samples=["Ahmed Al Mansouri", "Sarah Johnson"]
    )
    
    results = store.search(query_emb.vector, k=3)
    
    print(f"\nSearching for mappings similar to 'employee_name':")
    print(f"Found {len(results)} results:\n")
    
    for result in results:
        print(f"  [{result['rank']}] {result['similarity']*100:.0f}% similar")
        print(f"      {result['metadata']['text'][:80]}...")
        print()
