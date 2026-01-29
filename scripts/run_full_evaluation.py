"""
Full System Evaluation on Defects4J
Uses the complete multi-agent pipeline: LangGraph + BM25 + Pattern Detection + Judge Agent
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from neo4j_loader import Neo4jKnowledgeGraph
from bug_localizer import BugLocalizer
from defects4j_evaluator import Defects4JLoader, Defects4JEvaluator


def run_full_evaluation(
    neo4j_uri: str,
    neo4j_user: str, 
    neo4j_password: str,
    defects4j_path: str,
    output_dir: str,
    num_bugs: int = 20,
    use_llm: bool = False,  # Set to True if LM Studio is running
    use_langgraph: bool = True
):
    """Run evaluation using the full multi-agent system."""
    
    print("=" * 70)
    print("FULL SYSTEM EVALUATION ON DEFECTS4J")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Neo4j: {neo4j_uri}")
    print(f"  Use LLM: {use_llm}")
    print(f"  Use LangGraph: {use_langgraph}")
    print(f"  Bugs to evaluate: {num_bugs}")
    
    # Step 1: Connect to Neo4j
    print("\n" + "-" * 70)
    print("STEP 1: Connecting to Neo4j Knowledge Graph")
    print("-" * 70)
    
    kg = Neo4jKnowledgeGraph(uri=neo4j_uri, user=neo4j_user, password=neo4j_password)
    
    if not kg.driver:
        print("[-] Failed to connect to Neo4j")
        return None
    
    # Verify classes exist
    with kg.driver.session() as session:
        result = session.run("MATCH (c:Class) RETURN count(c) as count")
        class_count = result.single()['count']
        print(f"[+] Found {class_count} classes in knowledge graph")
    
    if class_count == 0:
        print("[-] No classes in database. Run run_defects4j_evaluation.py first to load data.")
        kg.close()
        return None
    
    # Step 2: Initialize BugLocalizer with full system
    print("\n" + "-" * 70)
    print("STEP 2: Initializing Multi-Agent Bug Localizer")
    print("-" * 70)
    
    localizer = BugLocalizer(
        knowledge_graph=kg,
        use_llm=use_llm,
        llm_provider="lmstudio" if use_llm else "keyword",
        use_agents=True,
        use_langgraph=use_langgraph
    )
    
    # Build BM25 index
    print("\n[*] Building BM25 index from knowledge graph...")
    localizer.build_bm25_index()
    
    # Step 3: Load Defects4J bugs
    print("\n" + "-" * 70)
    print("STEP 3: Loading Defects4J Bugs")
    print("-" * 70)
    
    loader = Defects4JLoader(defects4j_path)
    bugs = loader.load_project_bugs("Lang", limit=num_bugs)
    print(f"[+] Loaded {len(bugs)} bugs from Defects4J Lang project")
    
    # Step 4: Run localization on each bug
    print("\n" + "-" * 70)
    print("STEP 4: Running Bug Localization")
    print("-" * 70)
    
    evaluator = Defects4JEvaluator()
    all_results = []
    
    for i, bug in enumerate(bugs):
        print(f"\n{'='*70}")
        print(f"BUG {i+1}/{len(bugs)}: {bug.project}-{bug.bug_id}")
        print(f"Ground Truth: {bug.modified_classes}")
        print(f"{'='*70}")
        
        # Convert bug to report text
        bug_report = bug.to_bug_report()
        
        try:
            # Run the FULL localization pipeline
            result = localizer.localize_from_text(
                bug_report=bug_report,
                bug_id=f"{bug.project}-{bug.bug_id}",
                num_top_locations=10
            )
            
            # Extract predicted class names
            predicted_classes = []
            for loc in result.get('top_locations', []):
                # Try multiple possible keys
                class_name = loc.get('name') or loc.get('class_name') or loc.get('class', '')
                if class_name:
                    # Get simple name (remove package prefix)
                    simple_name = class_name.split('.')[-1]
                    predicted_classes.append(simple_name)
                    print(f"    Found: {simple_name}")
            
            print(f"\nTop Predictions:")
            for j, cls in enumerate(predicted_classes[:5]):
                print(f"  {j+1}. {cls}")
            
            # Evaluate against ground truth
            eval_result = evaluator.evaluate_single(bug, predicted_classes)
            
            status = "HIT" if eval_result['metrics'].get('top_10_hit') else "MISS"
            rank = eval_result['metrics'].get('first_rank', -1)
            
            print(f"\nResult: {status} (Rank: {rank if rank > 0 else 'N/A'})")
            
            all_results.append({
                'bug_id': f"{bug.project}-{bug.bug_id}",
                'ground_truth': bug.modified_classes,
                'predictions': predicted_classes[:10],
                'hit': eval_result['metrics'].get('top_10_hit', False),
                'rank': rank
            })
            
        except Exception as e:
            print(f"[-] Error processing bug: {e}")
            import traceback
            traceback.print_exc()
            all_results.append({
                'bug_id': f"{bug.project}-{bug.bug_id}",
                'ground_truth': bug.modified_classes,
                'predictions': [],
                'hit': False,
                'rank': -1,
                'error': str(e)
            })
    
    # Step 5: Generate final report
    print("\n" + "=" * 70)
    print("FINAL EVALUATION REPORT")
    print("=" * 70)
    
    metrics = evaluator.compute_aggregate_metrics()
    
    report_path = os.path.join(output_dir, "full_system_evaluation_report.txt")
    report = evaluator.generate_report(report_path)
    print(report)
    
    # Save detailed results
    results_path = os.path.join(output_dir, "full_system_results.json")
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({
            'config': {
                'use_llm': use_llm,
                'use_langgraph': use_langgraph,
                'use_agents': True,
                'num_bugs': num_bugs
            },
            'metrics': metrics,
            'results': all_results
        }, f, indent=2)
    
    print(f"\n[+] Results saved to: {results_path}")
    print(f"[+] Report saved to: {report_path}")
    
    # Print summary for paper
    print("\n" + "=" * 70)
    print("RESULTS FOR PAPER")
    print("=" * 70)
    print(f"""
System: Multi-Agent Bug Localization with LangGraph Orchestration
Components:
  - BM25 Text Ranking
  - Bug Type Classifier
  - Static Pattern Detection Agent  
  - Test Failure Analysis Agent
  - Judge Agent (Score Fusion)
  - LangGraph State Machine

Dataset: Defects4J (Apache Commons Lang)
Bugs Evaluated: {metrics.get('total_bugs', 0)}

RESULTS:
  Top-1 Accuracy:  {metrics.get('top_1_accuracy', 0) * 100:.1f}%
  Top-5 Accuracy:  {metrics.get('top_5_accuracy', 0) * 100:.1f}%
  Top-10 Accuracy: {metrics.get('top_10_accuracy', 0) * 100:.1f}%
  MRR:             {metrics.get('mrr', 0):.3f}
  Mean Rank:       {metrics.get('mean_rank', 'N/A')}
""")
    
    kg.close()
    return metrics


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    output_dir = project_root / "outputs" / "defects4j_evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get password from command line
    password = sys.argv[1] if len(sys.argv) > 1 else "12345678"
    
    # Check if LM Studio should be used
    use_llm = "--llm" in sys.argv
    
    metrics = run_full_evaluation(
        neo4j_uri="bolt://127.0.0.1:7687",
        neo4j_user="neo4j",
        neo4j_password=password,
        defects4j_path=str(project_root / "defects4j"),
        output_dir=str(output_dir),
        num_bugs=20,
        use_llm=use_llm,
        use_langgraph=True
    )
    
    if metrics:
        print("\n[+] Evaluation complete!")
    else:
        print("\n[-] Evaluation failed")


if __name__ == "__main__":
    main()
