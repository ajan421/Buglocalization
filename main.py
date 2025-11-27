"""
Main Script for Bug Localization System
Orchestrates the entire pipeline: parsing code, building knowledge graph, and localizing bugs
"""

import sys
import os
import json
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd

from code_parser import CodeParser
from neo4j_loader import Neo4jKnowledgeGraph
from bug_localizer import BugLocalizer

# Load environment variables
load_dotenv()


def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def step_parse_code(source_dirs, output_file: str = "code_structure.json") -> bool:
    """
    Step 1: Parse Java source code and extract structure.
    
    Extracts classes, methods, fields, and relationships from Java source files.
    
    Args:
        source_dirs: Single directory or list of directories to parse
        output_file: Output JSON file for parsed data
        
    Returns:
        True if successful, False otherwise
    """
    print_header("STEP 1: PARSING SOURCE CODE")
    
    # Handle both single directory (string) and multiple directories (list)
    if isinstance(source_dirs, str):
        source_dirs = [source_dirs]
    
    all_parsed_data = {
        'files': [],
        'total_classes': 0,
        'total_methods': 0,
        'total_fields': 0
    }
    
    # Parse each directory
    for source_dir in source_dirs:
        if not Path(source_dir).exists():
            print(f"⚠ Skipping {source_dir} (not found)")
            continue
        
        print(f"\n--- Parsing {source_dir} ---")
        parser = CodeParser(source_dir)
        parsed_data = parser.parse_directory()
        
        # Merge results
        all_parsed_data['files'].extend(parsed_data['files'])
        all_parsed_data['total_classes'] += parsed_data['total_classes']
        all_parsed_data['total_methods'] += parsed_data['total_methods']
        all_parsed_data['total_fields'] += parsed_data['total_fields']
    
    print(f"\n{'='*80}")
    print("OVERALL STATISTICS:")
    print(f"Total classes: {all_parsed_data['total_classes']}")
    print(f"Total methods: {all_parsed_data['total_methods']}")
    print(f"Total fields: {all_parsed_data['total_fields']}")
    print('='*80)
    
    # Save parsed data
    with open(output_file, 'w') as f:
        json.dump(all_parsed_data, f, indent=2)
    
    print(f"\n✓ Parsed data saved to {output_file}")
    return True


def step_build_knowledge_graph(parsed_file: str = "code_structure.json") -> Neo4jKnowledgeGraph:
    """
    Step 2: Build Neo4j knowledge graph from parsed code.
    
    Creates nodes and relationships in Neo4j representing the code structure.
    
    Args:
        parsed_file: Path to parsed code JSON file
        
    Returns:
        Neo4jKnowledgeGraph instance or None if failed
    """
    print_header("STEP 2: BUILDING KNOWLEDGE GRAPH IN NEO4J")
    
    if not Path(parsed_file).exists():
        print(f"✗ Parsed data file not found: {parsed_file}")
        return None
    
    # Load parsed data
    with open(parsed_file, 'r') as f:
        parsed_data = json.load(f)
    
    # Initialize Neo4j connection
    knowledge_graph = Neo4jKnowledgeGraph()
    
    if not knowledge_graph.driver:
        print("\n✗ Cannot build knowledge graph without Neo4j connection")
        print("\nTo set up Neo4j:")
        print("1. Download: https://neo4j.com/download/")
        print("2. Install and create a database")
        print("3. Set password to 'password' (or update neo4j_loader.py)")
        print("4. Start the database")
        return None
    
    # Clear existing data and rebuild
    print("Clearing existing database...")
    knowledge_graph.clear_database()
    
    print("Creating performance indexes...")
    knowledge_graph.create_indexes()
    
    print("Loading parsed code structure into Neo4j...")
    knowledge_graph.load_parsed_data(parsed_data)
    
    print("\n✓ Knowledge graph built successfully!")
    return knowledge_graph


def step_localize_bugs(knowledge_graph: Neo4jKnowledgeGraph, bug_reports_dir: str = "bug_reports", num_top_locations: int = 5):
    """
    Step 3: Localize bugs from bug report files.
    
    Processes all bug report .txt files and identifies potential buggy locations.
    
    Args:
        knowledge_graph: Neo4j knowledge graph instance
        bug_reports_dir: Directory containing bug report files
        num_top_locations: Number of top locations to return per bug (default: 5)
    """
    print_header(f"STEP 3: LOCALIZING BUGS (TOP-{num_top_locations} RANKING)")
    
    if not knowledge_graph or not knowledge_graph.driver:
        print("✗ Cannot localize bugs without knowledge graph")
        return
    
    bug_reports_path = Path(bug_reports_dir)
    if not bug_reports_path.exists():
        print(f"✗ Bug reports directory not found: {bug_reports_dir}")
        return
    
    bug_files = list(bug_reports_path.glob('*.txt'))
    if not bug_files:
        print(f"✗ No bug report files found in {bug_reports_dir}")
        return
    
    print(f"Found {len(bug_files)} bug report(s)")
    
    # Initialize bug localizer
    # Set use_llm=True to use Gemini for better understanding (if API key available)
    # Set use_llm=False to use only keyword matching (faster, no API needed)
    use_gemini = os.getenv('GEMINI_API_KEY') is not None
    localizer = BugLocalizer(knowledge_graph, use_llm=use_gemini)
    
    if use_gemini:
        print("✓ Using Gemini LLM for enhanced bug analysis")
    else:
        print("⚠ Using keyword matching (add GEMINI_API_KEY to .env for LLM enhancement)")
    
    # Process each bug report
    results = []
    for i, bug_file in enumerate(bug_files, 1):
        print(f"\n{'#'*80}")
        print(f"Processing bug report {i}/{len(bug_files)}: {bug_file.name}")
        print('#'*80)
        
        result = localizer.localize_from_file(str(bug_file), num_top_locations=num_top_locations)
        results.append(result)
        print("\n" + "-" * 80 + "\n")
    
    # Save results with better naming
    output_file = "bug_localization_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n{'='*80}")
    print(f"✓ Successfully localized {len(results)} bug reports")
    print(f"✓ Results saved to: {output_file}")
    print(f"✓ Top {num_top_locations} locations identified per bug")
    print('='*80)


def step_localize_bugs_from_parquet(knowledge_graph: Neo4jKnowledgeGraph, parquet_file: str, max_bugs: int = 100, num_top_locations: int = 10):
    """
    Step 3: Localize bugs from Parquet file (for large-scale evaluation).
    
    Args:
        knowledge_graph: Neo4j knowledge graph instance
        parquet_file: Path to parquet file with bug data
        max_bugs: Maximum number of bugs to process
        num_top_locations: Number of top locations per bug
    """
    print_header("STEP 3: LOCALIZING BUGS FROM PARQUET FILE")
    
    if not knowledge_graph or not knowledge_graph.driver:
        print("✗ Cannot localize bugs without knowledge graph")
        return
    
    # Load parquet
    print(f"\nLoading bugs from {parquet_file}...")
    df = pd.read_parquet(parquet_file)
    print(f"✓ Loaded {len(df)} total bug reports")
    
    # Filter for weaver-related bugs
    weaver_keywords = ['weaver', 'weaving', 'aspect', 'bcel', 'World', 'BcelWeaver']
    
    def is_weaver_bug(row):
        text = ' '.join([str(v) for v in row.values if pd.notna(v)]).lower()
        if 'updated_files' in row and pd.notna(row['updated_files']):
            files = str(row['updated_files']).lower()
            if 'weaver' in files or 'bcel' in files:
                return True
        return any(kw.lower() in text for kw in weaver_keywords)
    
    print("\nFiltering for weaver-related bugs...")
    df['is_weaver'] = df.apply(is_weaver_bug, axis=1)
    weaver_bugs = df[df['is_weaver']].head(max_bugs)
    print(f"✓ Selected {len(weaver_bugs)} weaver-related bugs")
    
    # Initialize localizer (disable LLM for large-scale processing)
    localizer = BugLocalizer(knowledge_graph, use_llm=False)
    
    # Process bugs
    results = []
    for idx, row in weaver_bugs.iterrows():
        bug_text = f"Title: {row.get('title', '')}\nBody: {row.get('body', '')}"
        bug_id = f"bug_{row.get('issue_id', idx)}"
        
        print(f"\n{'#'*80}")
        print(f"Processing: {bug_id}")
        print('#'*80)
        
        try:
            result = localizer.localize_from_text(bug_text, bug_id, num_top_locations=num_top_locations)
            result['ground_truth'] = eval(row['updated_files']) if 'updated_files' in row and pd.notna(row['updated_files']) else []
            results.append(result)
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    # Save results
    output_file = "bug_localization_results_parquet.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n✓ Processed {len(results)} bugs, saved to {output_file}")


def main():
    """
    Main execution flow for automated bug localization pipeline.
    
    Pipeline steps:
    1. Parse Java source code
    2. Build Neo4j knowledge graph
    3. Identify suspicious files from bug reports
    """
    print("""
    ╔══════════════════════════════════════════════════════════════════════════╗
    ║            AUTOMATED BUG LOCALIZATION SYSTEM                             ║
    ║          Identifying Suspicious Files - Top-5 Ranking                    ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    """)
    
    # ═══════════════════════════════════════════════════════════════
    # CONFIGURATION
    # ═══════════════════════════════════════════════════════════════
    
    # Source directories to parse (AspectJ modules)
    source_dirs = [
        "aspectj/weaver/src",
        "aspectj/runtime/src",
        "aspectj/ajde/src",
        "aspectj/ajde.core/src",
        "aspectj/org.aspectj.ajdt.core/src",
        "aspectj/bridge/src",
        "aspectj/bcel-builder/src",
        "aspectj/asm/src"
    ]
    
    # Output files
    code_structure_file = "code_structure.json"  # Parsed code structure
    bug_reports_dir = "bug_reports"             # Bug report directory
    
    # Ranking configuration
    num_top_locations = 5  # Number of top buggy locations to identify per bug
    
    # ═══════════════════════════════════════════════════════════════
    # PIPELINE EXECUTION
    # ═══════════════════════════════════════════════════════════════
    
    # Check if parsed data already exists
    if Path(code_structure_file).exists():
        print(f"\n✓ Found existing code structure: {code_structure_file}")
        response = input("  Re-parse the code? (y/n): ").strip().lower()
        if response == 'y':
            if not step_parse_code(source_dirs, code_structure_file):
                print("\n✗ Failed to parse code. Exiting.")
                return
    else:
        # Step 1: Parse source code
        if not step_parse_code(source_dirs, code_structure_file):
            print("\n✗ Failed to parse code. Exiting.")
            return
    
    # Step 2: Build knowledge graph
    knowledge_graph = step_build_knowledge_graph(code_structure_file)
    
    if not knowledge_graph:
        print("\n⚠ Knowledge graph not available. Exiting.")
        print("  Please set up Neo4j and try again.")
        return
    
    # Step 3: Localize bugs from text files
    step_localize_bugs(knowledge_graph, bug_reports_dir, num_top_locations)
    
    # Cleanup
    knowledge_graph.close()
    
    print_header("PIPELINE COMPLETE")
    print("✓ Bug localization pipeline completed successfully!")
    print(f"\n📊 Results Summary:")
    print(f"  ├─ Code structure: {code_structure_file}")
    print(f"  ├─ Bug reports processed: {bug_reports_dir}/*.txt")
    print(f"  ├─ Localization results: bug_localization_results.json")
    print(f"  └─ Top locations per bug: {num_top_locations}")
    print(f"\n✅ All suspicious files and locations identified!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

