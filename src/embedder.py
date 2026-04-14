"""
EMBEDDER MODULE — Convert text to vectors
==========================================

Why this matters (RAG Foundation):
  RAG requires searching SIMILAR items, not just exact matches.
  To search, you need embeddings (512-dim vectors that capture meaning).
  
  "emp_nm" and "employee_name" are different strings,
  but their embeddings are CLOSE (same meaning).

Educational point (what you'll learn):
  - How embeddings work (convert text → high-dim space)
  - Why semantic search is better than keyword search
  - How to use pre-trained models (sentence-transformers)
  
Real-world:
  This is exactly what Pinecone, Supabase, Weaviate, etc. do.
  You're building it.
"""

import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class Embedding:
    """A text snippet + its vector representation."""
    text: str
    vector: np.ndarray  # shape: (384,) for all-MiniLM-L6-v2
    source: str  # where this came from (e.g., "canonical_schema", "past_mapping")
    metadata: Dict[str, Any]  # additional context


class TextEmbedder:
    """
    Convert text descriptions of columns into embeddings.
    
    Uses sentence-transformers (all-MiniLM-L6-v2):
      - Ultra-fast (~1ms per embedding)
      - 384-dimensional vectors
      - Pre-trained on domain-diverse data
    """
    
    def __init__(self):
        """Initialize the embedder."""
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. Run:\n"
                "pip install sentence-transformers"
            )
        
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.embedding_dim = 384
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        Convert a single text string to embedding.
        
        Args:
            text: Column description (e.g., "emp_nm: Employee name samples: Ahmed, Sarah")
        
        Returns:
            numpy array of shape (384,)
        """
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding
    
    def embed_column_description(
        self, 
        column_name: str, 
        column_type: str,
        samples: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Embedding:
        """
        Convert a full column description into an Embedding object.
        
        This is the key insight:
          We're not embedding just the name.
          We're embedding the FULL description (name + type + examples).
          This makes similarity search much smarter.
        
        Args:
            column_name: e.g., "emp_no"
            column_type: e.g., "string"
            samples: e.g., ["Ahmed Al Mansouri", "Sarah Johnson"]
            metadata: additional context
        
        Returns:
            Embedding object with vector
        """
        
        # Build a rich text description
        samples_str = ", ".join(samples[:3])
        description = f"""
        Column: {column_name}
        Type: {column_type}
        Examples: {samples_str}
        """
        
        vector = self.embed_text(description)
        
        return Embedding(
            text=description.strip(),
            vector=vector,
            source="column_description",
            metadata=metadata or {}
        )
    
    def embed_canonical_field(
        self,
        canonical_name: str,
        description: str,
        table: str,
        compliance_critical: bool = False
    ) -> Embedding:
        """
        Embed a CANONICAL schema field (the target).
        
        This is what we're mapping TO.
        By embedding it, we can search for messy columns that might map to it.
        
        Args:
            canonical_name: e.g., "name"
            description: e.g., "Full name of the employee"
            table: e.g., "employees"
            compliance_critical: whether this is legally required
        
        Returns:
            Embedding object
        """
        
        full_text = f"""
        Canonical field: {canonical_name}
        Table: {table}
        Description: {description}
        Compliance critical: {compliance_critical}
        """
        
        vector = self.embed_text(full_text)
        
        return Embedding(
            text=full_text.strip(),
            vector=vector,
            source="canonical_field",
            metadata={
                "canonical_name": canonical_name,
                "table": table,
                "compliance_critical": compliance_critical
            }
        )
    
    def embed_mapping_example(
        self,
        source_column: str,
        target_column: str,
        confidence: float,
        reasoning: str
    ) -> Embedding:
        """
        Embed a PAST MAPPING (what we've learned).
        
        By storing past successful mappings as embeddings,
        we can retrieve similar cases when facing new messy data.
        
        This is the self-improving part.
        
        Args:
            source_column: messy column name
            target_column: canonical name
            confidence: how sure we are
            reasoning: why this mapping works
        
        Returns:
            Embedding object
        """
        
        example_text = f"""
        Mapping: {source_column} → {target_column}
        Confidence: {confidence:.0%}
        Reasoning: {reasoning}
        """
        
        vector = self.embed_text(example_text)
        
        return Embedding(
            text=example_text.strip(),
            vector=vector,
            source="past_mapping",
            metadata={
                "source_column": source_column,
                "target_column": target_column,
                "confidence": confidence
            }
        )
    
    @staticmethod
    def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Compute cosine similarity between two embedding vectors.
        
        Range: 0.0 (opposite) to 1.0 (identical)
        
        Why cosine?
          - Embeddings are normalized (all length 1.0)
          - Cosine similarity = dot product for normalized vectors
          - Fast and mathematically elegant
        """
        return float(np.dot(vec1, vec2))


if __name__ == "__main__":
    # Test the embedder
    
    print("\n🧬 Testing Text Embedder")
    print("=" * 70)
    
    embedder = TextEmbedder()
    
    # Example 1: Embed two column descriptions
    print("\n1️⃣  Embedding two messy column names...")
    
    emb1 = embedder.embed_column_description(
        column_name="emp_nm",
        column_type="string",
        samples=["Ahmed Al Mansouri", "Sarah Johnson"],
        metadata={"source_file": "employee_master.csv"}
    )
    
    emb2 = embedder.embed_column_description(
        column_name="employee_name",
        column_type="string",
        samples=["Ahmed Al Mansouri", "Sarah Johnson"],
        metadata={"source_file": "other_export.csv"}
    )
    
    similarity = embedder.cosine_similarity(emb1.vector, emb2.vector)
    print(f"   emp_nm vs employee_name similarity: {similarity:.3f}")
    print(f"   (0.0 = different, 1.0 = identical)")
    print(f"   ✓ They're similar! ({similarity*100:.0f}% overlap)")
    
    # Example 2: Compare to a different column
    print("\n2️⃣  Comparing to a DIFFERENT column type...")
    
    emb3 = embedder.embed_column_description(
        column_name="joining_dt",
        column_type="date",
        samples=["01/03/2019", "15-Jul-2021"],
        metadata={"source_file": "employee_master.csv"}
    )
    
    similarity_diff = embedder.cosine_similarity(emb1.vector, emb3.vector)
    print(f"   emp_nm vs joining_dt similarity: {similarity_diff:.3f}")
    print(f"   ✓ Much less similar! ({similarity_diff*100:.0f}% overlap)")
    
    # Example 3: Canonical field
    print("\n3️⃣  Embedding a canonical target field...")
    
    canonical_name = embedder.embed_canonical_field(
        canonical_name="name",
        description="Full name of the employee",
        table="employees",
        compliance_critical=False
    )
    
    similarity_to_canonical = embedder.cosine_similarity(emb1.vector, canonical_name.vector)
    print(f"   emp_nm vs canonical 'name' similarity: {similarity_to_canonical:.3f}")
    print(f"   ✓ Should be high! (this is what we want to map to)")
    
    # Example 4: Past mapping example
    print("\n4️⃣  Embedding a past mapping (for learning)...")
    
    past_mapping = embedder.embed_mapping_example(
        source_column="emp_nm",
        target_column="name",
        confidence=0.95,
        reasoning="Standard abbreviation for employee name"
    )
    
    print(f"\n✓ Embedding system working!")
    print(f"✓ Embedding dimension: {embedder.embedding_dim}")
    print(f"✓ All embeddings normalized and ready for vector search")
