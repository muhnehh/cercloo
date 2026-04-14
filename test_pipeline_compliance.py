#!/usr/bin/env python3
"""
Test script: Verify pipeline + compliance integration works
"""

from src.pipeline import RAGMappingPipeline

print('\n✅ Testing Pipeline with Compliance Integration')
print('=' * 80)

pipeline = RAGMappingPipeline(
    data_dir='datasets',
    use_rag=False,  # Disable RAG (requires FAISS)
    check_compliance=True,  
    jurisdiction='UAE'
)

print('\n🚀 Running 6-step pipeline (RAG disabled, compliance enabled)...\n')

results = pipeline.run()

print('\n' + '=' * 80)
print('FINAL REPORT')
print('=' * 80)
print(f'✅ Compliance integration working: {results["compliance"] is not None}')
if results["compliance"]:
    print(f'✅ Compliance jurisdiction: {results["compliance"]["jurisdiction"]}')
    print(f'✅ Compliance status: {results["compliance"]["status"]}')
print(f'📊 Total columns profiled: {results["statistics"]["total_columns"]}')
print(f'📊 Total rows profiled: {results["statistics"]["total_rows"]}')
print(f'🗺️  Column mappings generated (without RAG): {results["statistics"]["successful_mappings"]}')
print('\n✨ Pipeline complete - Ready for next phase (Streamlit UI)')
