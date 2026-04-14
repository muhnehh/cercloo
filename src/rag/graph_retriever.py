"""
GRAPH RAG RETRIEVER — Knowledge Graph + Vector Store
=====================================================

What this does:
  Combines entity extraction with vector retrieval.
  Instead of just searching embeddings, we:
  1. Extract entities from compliance check (e.g., "annual leave")
  2. Look up in knowledge graph (find relationships & thresholds)
  3. Retrieve relevant law text from vector store
  4. Return formatted citation with context

Why this matters:
  This is GraphRAG-lite: smarter retrieval through structured relationships.
  Example: 
    - User asks: "Is 20 days annual leave legal?"
    - Graph lookup: finds "annual_leave" entity → "30 days minimum" relationship
    - Vector search: retrieves Article 78 text
    - Result: "Article 78 requires 30 days minimum. You have 20 days. Violation."

Educational point:
  This is how advanced AI systems (Azure, Anthropic research) improve retrieval.
  You're implementing the core idea without full infrastructure.
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import networkx as nx
import numpy as np
from dataclasses import dataclass


@dataclass
class EntityRelationship:
    """A relationship in the knowledge graph."""
    source: str
    relation: str
    target: str
    metadata: Dict[str, Any]


class KnowledgeGraph:
    """
    Knowledge graph for labor law.
    
    Structure:
      Nodes: entities (annual_leave, overtime, visa, etc.)
      Edges: relationships with metadata
      
    Example:
      annual_leave --[minimum_days]--> "30"
      annual_leave --[applies_after]--> "1_year_tenure"
    """
    
    def __init__(self):
        """Initialize empty knowledge graph."""
        self.graph = nx.DiGraph()
        self.entity_to_articles = {}  # entity -> list of article numbers
    
    def add_entity(self, entity_name: str, entity_type: str, metadata: Dict[str, Any] = None):
        """Add an entity node."""
        if metadata is None:
            metadata = {}
        self.graph.add_node(
            entity_name,
            entity_type=entity_type,
            **metadata
        )
    
    def add_relationship(self, source: str, relation: str, target: str, metadata: Dict[str, Any] = None):
        """Add an edge between entities."""
        if metadata is None:
            metadata = {}
        
        self.graph.add_edge(
            source,
            target,
            relation=relation,
            **metadata
        )
    
    def add_article_reference(self, entity: str, article: str):
        """Link an entity to a law article."""
        if entity not in self.entity_to_articles:
            self.entity_to_articles[entity] = []
        if article not in self.entity_to_articles[entity]:
            self.entity_to_articles[entity].append(article)
    
    def get_related_entities(self, entity: str, depth: int = 1) -> Dict[str, Any]:
        """
        Get all related entities (neighbors in graph).
        
        Returns dict with immediate neighbors and their relationship types.
        """
        if entity not in self.graph:
            return {}
        
        related = {}
        
        # Outgoing edges (properties of entity)
        for neighbor in self.graph.successors(entity):
            edge_data = self.graph[entity][neighbor]
            relation = edge_data.get('relation', 'related_to')
            
            related[f"{relation}"] = {
                "target": neighbor,
                "metadata": {k: v for k, v in edge_data.items() if k != 'relation'}
            }
        
        return related
    
    def get_articles_for_entity(self, entity: str) -> List[str]:
        """Get all law articles relevant to an entity."""
        return self.entity_to_articles.get(entity, [])
    
    def serialize(self) -> Dict[str, Any]:
        """Serialize graph to JSON."""
        return {
            "nodes": dict(self.graph.nodes(data=True)),
            "edges": [
                {
                    "source": u,
                    "target": v,
                    "metadata": data
                }
                for u, v, data in self.graph.edges(data=True)
            ],
            "entity_to_articles": self.entity_to_articles
        }
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "KnowledgeGraph":
        """Deserialize graph from JSON."""
        kg = cls()
        
        # Restore nodes
        for node_name, attrs in data.get("nodes", {}).items():
            kg.graph.add_node(node_name, **attrs)
        
        # Restore edges
        for edge in data.get("edges", []):
            kg.graph.add_edge(
                edge["source"],
                edge["target"],
                **edge.get("metadata", {})
            )
        
        # Restore article links
        kg.entity_to_articles = data.get("entity_to_articles", {})
        
        return kg


class GraphRAGRetriever:
    """
    Dual-mode retrieval: Knowledge Graph + Vector Store.
    
    How it works:
      1. Query comes in (e.g., compliance check)
      2. Extract entity (e.g., "annual_leave")
      3. Graph lookup: find relationships and thresholds
      4. Vector search: find relevant articles
      5. Combine into formatted context
    """
    
    def __init__(self, knowledge_graph: KnowledgeGraph, vector_store=None, embedder=None):
        """
        Args:
            knowledge_graph: KnowledgeGraph instance
            vector_store: VectorStore instance (optional, for hybrid retrieval)
            embedder: TextEmbedder instance (optional)
        """
        self.kg = knowledge_graph
        self.vector_store = vector_store
        self.embedder = embedder
    
    def retrieve_for_compliance_check(
        self,
        entity: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Retrieve context for a compliance check.
        
        Args:
            entity: What are we checking? ("annual_leave", "overtime", "visa", etc.)
            context: Additional context (employee data, values being checked)
        
        Returns:
            {
                "entity": "annual_leave",
                "relationships": {...},  # from graph
                "articles": [...],       # relevant law articles
                "formatted_context": "..."  # for LLM prompt
            }
        """
        
        if context is None:
            context = {}
        
        result = {
            "entity": entity,
            "relationships": {},
            "articles": [],
            "formatted_context": ""
        }
        
        # 1. GRAPH LOOKUP: Get relationships
        if self.kg.graph.has_node(entity):
            result["relationships"] = self.kg.get_related_entities(entity)
        
        # 2. Get article references
        articles = self.kg.get_articles_for_entity(entity)
        result["articles"] = articles
        
        # 3. VECTOR SEARCH: If available, search for related law text
        if self.vector_store and self.embedder and context:
            query_text = f"Compliance check: {entity}. Context: {context}"
            query_embedding = self.embedder.embed(query_text)
            
            if query_embedding:
                vector_results = self.vector_store.search(query_embedding.vector, k=3)
                result["vector_results"] = vector_results
        
        # 4. Format for LLM prompt
        result["formatted_context"] = self._format_context(result, entity, context)
        
        return result
    
    def _format_context(self, result: Dict[str, Any], entity: str, context: Dict[str, Any]) -> str:
        """Format retrieval result into LLM-friendly text."""
        
        lines = []
        lines.append(f"📋 COMPLIANCE CHECK: {entity.upper()}")
        lines.append("=" * 60)
        
        # Add relationships from graph
        if result["relationships"]:
            lines.append("\n🔗 REQUIREMENTS (from UAE Labor Law):")
            for rel_name, rel_data in result["relationships"].items():
                target = rel_data.get("target", "")
                metadata = rel_data.get("metadata", {})
                lines.append(f"  • {rel_name}: {target}")
                for k, v in metadata.items():
                    lines.append(f"    - {k}: {v}")
        
        # Add article references
        if result["articles"]:
            lines.append(f"\n📄 LEGAL BASIS:")
            for article in result["articles"]:
                lines.append(f"  • {article}")
        
        # Add context
        if context:
            lines.append(f"\n📊 EMPLOYEE DATA:")
            for k, v in context.items():
                lines.append(f"  • {k}: {v}")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def save(self, filepath: str):
        """Save graph to JSON."""
        data = {
            "graph": self.kg.serialize()
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    @classmethod
    def load(cls, filepath: str, vector_store=None, embedder=None) -> "GraphRAGRetriever":
        """Load graph from JSON."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        kg = KnowledgeGraph.deserialize(data["graph"])
        return cls(kg, vector_store, embedder)


def build_uae_labor_law_graph() -> KnowledgeGraph:
    """
    Build the UAE labor law knowledge graph.
    
    This is manually curated for this demo. In production,
    you'd extract entities using NER and build this programmatically.
    """
    
    kg = KnowledgeGraph()
    
    # ===== ANNUAL LEAVE =====
    kg.add_entity("annual_leave", "benefit")
    kg.add_relationship("annual_leave", "minimum_days", "30", {"applies_after": "1_year_tenure"})
    kg.add_relationship("annual_leave", "first_year_accrual", "2_days_per_month", {})
    kg.add_relationship("annual_leave", "max_days", "30", {"note": "UAE max, can be exceeded by agreement"})
    kg.add_article_reference("annual_leave", "Article 78 - Federal Decree-Law 2021")
    
    # ===== LEAVE CARRY-FORWARD =====
    kg.add_entity("leave_carryforward", "benefit")
    kg.add_relationship("leave_carryforward", "max_tenure_under_3yr", "5_days", {})
    kg.add_relationship("leave_carryforward", "max_tenure_3yr_plus", "10_days", {})
    kg.add_relationship("leave_carryforward", "excess_treatment", "paid_out", {})
    kg.add_article_reference("leave_carryforward", "Article 82 - Federal Decree-Law 2021")
    
    # ===== OVERTIME =====
    kg.add_entity("overtime", "compensation")
    kg.add_relationship("overtime", "weekday_rate", "1.25x_hourly_rate", {"day_type": "weekday"})
    kg.add_relationship("overtime", "friday_rate", "1.5x_hourly_rate", {"day_type": "friday"})
    kg.add_relationship("overtime", "max_daily_hours", "10", {"note": "Cannot exceed 10 hrs/day"})
    kg.add_article_reference("overtime", "Article 96-97 - Federal Decree-Law 2021")
    
    # ===== END-OF-SERVICE GRATUITY =====
    kg.add_entity("eos_gratuity", "severance")
    kg.add_relationship("eos_gratuity", "years_1_to_5", "21_days_per_year", {})
    kg.add_relationship("eos_gratuity", "years_5_plus", "30_days_per_year", {})
    kg.add_relationship("eos_gratuity", "calculation_base", "final_monthly_salary", {"includes": "base + fixed_allowances"})
    kg.add_article_reference("eos_gratuity", "Article 83-84 - Federal Decree-Law 2021")
    
    # ===== VISA & DOCUMENTATION =====
    kg.add_entity("visa_requirement", "legal_requirement")
    kg.add_relationship("visa_requirement", "applies_to", "non_uae_nationals", {})
    kg.add_relationship("visa_requirement", "status", "must_be_valid", {"consequence": "cannot_legally_work"})
    kg.add_article_reference("visa_requirement", "MOHRE Work Visa Requirements")
    
    kg.add_entity("national_id", "documentation")
    kg.add_relationship("national_id", "requirement", "mandatory", {"applies_to": "all_employees"})
    kg.add_article_reference("national_id", "MOHRE Employment Records")
    
    # ===== PROBATION =====
    kg.add_entity("probation_period", "employment_contract")
    kg.add_relationship("probation_period", "max_standard", "6_months", {"applies_to": "general_roles"})
    kg.add_relationship("probation_period", "max_extended", "12_months", {"applies_to": "pilots_captains"})
    kg.add_article_reference("probation_period", "Article 47 - Federal Decree-Law 2021")
    
    return kg


if __name__ == "__main__":
    # Test the graph builder
    print("🔨 Building UAE Labor Law Knowledge Graph...")
    kg = build_uae_labor_law_graph()
    
    print(f"✅ Graph created with {kg.graph.number_of_nodes()} entities and {kg.graph.number_of_edges()} relationships")
    
    # Test retriever
    retriever = GraphRAGRetriever(kg)
    
    # Test compliance check retrieval
    print("\n📋 Testing: Annual Leave Compliance Check")
    print("=" * 60)
    
    result = retriever.retrieve_for_compliance_check(
        entity="annual_leave",
        context={
            "employee_name": "Ahmed Al Mansouri",
            "tenure_years": 2,
            "annual_leave_entitlement": 20
        }
    )
    
    print(result["formatted_context"])
