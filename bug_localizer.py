"""
LLM-Based Bug Localization System
Uses Google Gemini to match bug reports to relevant code locations
with intelligent scoring and ranking algorithms
"""

import os
import json
import time
from typing import List, Dict, Tuple
from neo4j_loader import Neo4jKnowledgeGraph
import google.generativeai as genai
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Rate limiting configuration
GEMINI_DELAY = 2.0  # Seconds between API calls to avoid rate limits

# Scoring weights for different match types
SCORE_STACK_TRACE_MATCH = 10.0      # Highest: Direct stack trace evidence
SCORE_POTENTIAL_CLASS = 5.0          # High: LLM identified as potential class
SCORE_KEYWORD_MATCH = 3.0            # Medium: Keyword found in class/method
SCORE_SEMANTIC_MATCH = 2.0           # Low: Semantic similarity


class BugLocalizer:
    """
    Intelligent bug localization using LLM and knowledge graph.
    
    Identifies buggy code locations by:
    1. Parsing bug reports with LLM or keyword extraction
    2. Querying knowledge graph for candidate locations
    3. Scoring and ranking candidates by relevance
    4. Analyzing code relationships and affected files
    """
    
    def __init__(self, knowledge_graph: Neo4jKnowledgeGraph, use_llm: bool = True):
        """
        Initialize bug localizer
        
        Args:
            knowledge_graph: Neo4j knowledge graph instance
            use_llm: Whether to use Gemini API (requires GEMINI_API_KEY env var)
        """
        self.knowledge_graph = knowledge_graph
        self.use_llm = use_llm
        self.model = None
        self.last_api_call = 0  # Track last API call time for rate limiting
        
        if use_llm:
            api_key = os.getenv('GEMINI_API_KEY')
            if api_key:
                try:
                    genai.configure(api_key=api_key)
                    self.model = genai.GenerativeModel('gemini-pro')
                    print("✓ Google Gemini API configured")
                except Exception as e:
                    print(f"✗ Error configuring Gemini: {e}")
                    print("  Falling back to keyword-based matching")
                    self.use_llm = False
            else:
                print("⚠ GEMINI_API_KEY not found")
                print("  Using keyword-based matching (still works!)")
                print("  For better results, add API key to .env file")
                self.use_llm = False
    
    def _rate_limit_api_call(self):
        """Enforce rate limiting between API calls"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call
        
        if time_since_last_call < GEMINI_DELAY:
            sleep_time = GEMINI_DELAY - time_since_last_call
            print(f"  [Rate limiting: waiting {sleep_time:.1f}s...]")
            time.sleep(sleep_time)
        
        self.last_api_call = time.time()
    
    def extract_bug_information(self, bug_report: str) -> Dict:
        """
        Extract key information from bug report using LLM or keyword-based parsing.
        
        Args:
            bug_report: Raw bug report text
            
        Returns:
            Dictionary with extracted information including:
            - summary: Brief description
            - error_type: Type of error
            - keywords: Technical terms identified
            - potential_classes: Candidate class names
            - potential_methods: Candidate method names
            - stack_trace_classes: Classes from stack traces
        """
        if not self.use_llm or not self.model:
            return self._keyword_based_parse(bug_report)
        
        try:
            # Rate limit API calls
            self._rate_limit_api_call()
            
            prompt = f"""You are a bug report analyzer. Extract key information from the bug report below and return ONLY a JSON object with these fields:
- summary: Brief summary of the bug
- error_type: Type of error (NullPointerException, compilation, runtime, or anytype )
- keywords: List of relevant technical keywords
- potential_classes: List of class names that might be related
- potential_methods: List of method names that might be related
- stack_trace_classes: Classes mentioned in stack trace (if any)

Bug Report:
{bug_report}

Return only the JSON object, no other text:"""
            
            response = self.model.generate_content(prompt)
            result = response.text.strip()
            
            # Try to parse JSON from response
            try:
                # Remove markdown code blocks if present
                if result.startswith('```'):
                    result = result.split('```')[1]
                    if result.startswith('json'):
                        result = result[4:]
                    result = result.strip()
                
                return json.loads(result)
            except:
                # If not valid JSON, use keyword-based parsing
                print("  ⚠ Could not parse LLM response, using keyword matching")
                return self._keyword_based_parse(bug_report)
                
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower():
                print(f"  ⚠ Gemini API rate limit hit - switching to keyword mode")
                self.use_llm = False  # Disable for rest of session
            else:
                print(f"  ⚠ Gemini error: {error_msg[:100]}")
            return self._keyword_based_parse(bug_report)
    
    def _keyword_based_parse(self, bug_report: str) -> Dict:
        """
        Keyword-based parsing without LLM.
        
        Extracts information using pattern matching and heuristics:
        - CamelCase words as potential class names
        - Stack traces for direct class references
        - First line as summary
        
        Args:
            bug_report: Raw bug report text
            
        Returns:
            Dictionary with extracted information
        """
        lines = bug_report.split('\n')
        
        # Extract keywords (Java-related terms)
        keywords = []
        for word in bug_report.split():
            # Look for camelCase or class names
            if word[0].isupper() and any(c.islower() for c in word):
                keywords.append(word.strip('.,():;'))
        
        # Look for stack traces
        stack_trace_classes = []
        for line in lines:
            if 'at ' in line and '(' in line:
                # Extract class name from stack trace
                parts = line.split('at ')
                if len(parts) > 1:
                    class_part = parts[1].split('(')[0].strip()
                    if '.' in class_part:
                        class_name = class_part.rsplit('.', 1)[0]
                        stack_trace_classes.append(class_name)
        
        return {
            'summary': lines[0] if lines else '',
            'error_type': 'Unknown',
            'keywords': list(set(keywords)),
            'potential_classes': [],
            'potential_methods': [],
            'stack_trace_classes': stack_trace_classes
        }
    
    def _get_relationships_and_affected_files(self, location: Dict) -> Dict:
        """
        Get relationships and affected files for a code location.
        
        Queries the knowledge graph to find:
        - Parent classes (extends)
        - Implemented interfaces
        - Dependent classes (used_by)
        - Dependencies (uses)
        - All affected files
        
        Args:
            location: Dictionary with type and name of location
            
        Returns:
            Dictionary with relationship information
        """
        relationships = {
            'extends': [],
            'implements': [],
            'used_by': [],
            'uses': [],
            'affected_files': []
        }
        
        if not self.knowledge_graph.driver:
            return relationships
        
        # Extract class name from location
        class_name = None
        if location['type'] == 'class':
            class_name = location['name']
        elif location['type'] == 'method':
            # Extract class from method signature
            class_name = location['name'].rsplit('.', 1)[0] if '.' in location['name'] else None
        
        if not class_name:
            return relationships
        
        try:
            with self.knowledge_graph.driver.session() as session:
                # Get inheritance relationships
                result = session.run("""
                    MATCH (c:Class {full_name: $class_name})-[:EXTENDS]->(parent:Class)
                    RETURN parent.full_name as parent, parent.file_path as file_path
                    LIMIT 5
                """, class_name=class_name)
                
                for record in result:
                    relationships['extends'].append({
                        'class': record['parent'],
                        'file': record['file_path']
                    })
                
                # Get interface implementations
                result = session.run("""
                    MATCH (c:Class {full_name: $class_name})-[:IMPLEMENTS]->(interface:Class)
                    RETURN interface.full_name as interface, interface.file_path as file_path
                    LIMIT 5
                """, class_name=class_name)
                
                for record in result:
                    relationships['implements'].append({
                        'class': record['interface'],
                        'file': record['file_path']
                    })
                
                # Get classes that depend on this class (used by)
                result = session.run("""
                    MATCH (other:Class)-[:EXTENDS|IMPLEMENTS]->(c:Class {full_name: $class_name})
                    RETURN DISTINCT other.full_name as other, other.file_path as file_path
                    LIMIT 10
                """, class_name=class_name)
                
                affected_files = set()
                for record in result:
                    relationships['used_by'].append({
                        'class': record['other'],
                        'file': record['file_path']
                    })
                    affected_files.add(record['file_path'])
                
                # Get classes this depends on (uses)
                result = session.run("""
                    MATCH (c:Class {full_name: $class_name})-[:EXTENDS|IMPLEMENTS]->(other:Class)
                    RETURN DISTINCT other.full_name as other, other.file_path as file_path
                    LIMIT 5
                """, class_name=class_name)
                
                for record in result:
                    relationships['uses'].append({
                        'class': record['other'],
                        'file': record['file_path']
                    })
                    affected_files.add(record['file_path'])
                
                relationships['affected_files'] = list(affected_files)
                
        except Exception as e:
            print(f"  ⚠ Could not fetch relationships: {e}")
        
        return relationships
    
    def identify_buggy_locations(self, bug_report: str, num_top_locations: int = 5) -> List[Dict]:
        """
        Identify potential buggy code locations from a bug report.
        
        Uses multi-strategy approach:
        1. Extract information from bug report (LLM or keyword-based)
        2. Query knowledge graph for candidate locations
        3. Score and rank candidates by relevance
        4. Enrich with relationship and dependency information
        
        Args:
            bug_report: Bug report text
            num_top_locations: Number of top candidates to return (default: 5)
            
        Returns:
            List of candidate locations with scores, sorted by relevance
        """
        print("\n" + "="*80)
        print("BUG LOCALIZATION - IDENTIFYING SUSPICIOUS FILES")
        print("="*80)
        
        # Step 1: Extract information from bug report
        print("\n[1/5] Extracting information from bug report...")
        extracted_bug_info = self.extract_bug_information(bug_report)
        print(f"   Summary: {extracted_bug_info['summary']}")
        print(f"   Keywords: {', '.join(extracted_bug_info['keywords'][:5])}")
        
        # Step 2: Search knowledge graph for candidates
        print("\n[2/5] Searching knowledge graph for candidate locations...")
        candidates = []
        
        # Strategy 1: Search by stack trace classes (highest priority)
        stack_trace_classes = extracted_bug_info.get('stack_trace_classes', [])
        if stack_trace_classes:
            print(f"   - Found {len(stack_trace_classes)} stack trace classes")
        for class_name in stack_trace_classes:
            results = self.knowledge_graph.query_classes_by_name(class_name.split('.')[-1])
            for result in results:
                candidates.append({
                    'type': 'class',
                    'name': result['full_name'],
                    'file_path': result['file_path'],
                    'score': SCORE_STACK_TRACE_MATCH,
                    'reason': 'Found in stack trace (highest confidence)'
                })
        
        # Strategy 2: Search by potential class names (LLM-identified)
        potential_classes = extracted_bug_info.get('potential_classes', [])
        if potential_classes:
            print(f"   - Found {len(potential_classes)} potential classes")
        for class_name in potential_classes:
            results = self.knowledge_graph.query_classes_by_name(class_name)
            for result in results:
                candidates.append({
                    'type': 'class',
                    'name': result['full_name'],
                    'file_path': result['file_path'],
                    'score': SCORE_POTENTIAL_CLASS,
                    'reason': 'LLM-identified potential class'
                })
        
        # Strategy 3: Search by keywords
        keywords = extracted_bug_info.get('keywords', [])[:10]
        if keywords:
            print(f"   - Processing {len(keywords)} keywords")
        for keyword in keywords:
            # Try as class name
            class_results = self.knowledge_graph.query_classes_by_name(keyword)
            for result in class_results:
                candidates.append({
                    'type': 'class',
                    'name': result['full_name'],
                    'file_path': result['file_path'],
                    'score': SCORE_KEYWORD_MATCH,
                    'reason': f'Keyword match: {keyword}'
                })
            
            # Try as method name
            method_results = self.knowledge_graph.query_methods_by_name(keyword)
            for result in method_results:
                candidates.append({
                    'type': 'method',
                    'name': result['signature'],
                    'file_path': result['file_path'],
                    'score': SCORE_KEYWORD_MATCH,
                    'reason': f'Method keyword match: {keyword}'
                })
        
        print(f"   ✓ Found {len(candidates)} total candidate locations")
        
        # Step 3: Score and rank candidates
        print("\n[3/5] Scoring and ranking candidates...")
        ranked_candidates = self._score_and_rank_candidates(candidates, extracted_bug_info)
        
        print(f"   ✓ Ranked {len(ranked_candidates)} unique locations")
        
        # Step 4: Enrich with relationships and affected files
        print(f"\n[4/5] Analyzing relationships and affected files for top {num_top_locations}...")
        for candidate in ranked_candidates[:num_top_locations]:
            relationships = self._get_relationships_and_affected_files(candidate)
            candidate['relationships'] = relationships
            candidate['affected_files'] = relationships['affected_files']
        print(f"   ✓ Enriched top candidates with relationship data")
        
        # Step 5: Display results
        print(f"\n[5/5] TOP {num_top_locations} MOST SUSPICIOUS LOCATIONS:")
        print("-" * 80)
        for rank, candidate in enumerate(ranked_candidates[:num_top_locations], 1):
            print(f"\n#{rank} {candidate['type'].upper()}: {candidate['name']}")
            print(f"   📁 File: {candidate['file_path']}")
            print(f"   🎯 Suspicion Score: {candidate['score']:.2f}")
            print(f"   💡 Reason: {candidate['reason']}")
            
            rels = candidate.get('relationships', {})
            if rels.get('extends'):
                print(f"   ↗️  Extends: {', '.join([r['class'] for r in rels['extends'][:3]])}")
            if rels.get('implements'):
                print(f"   🔌 Implements: {', '.join([r['class'] for r in rels['implements'][:3]])}")
            if rels.get('used_by'):
                print(f"   👥 Used by {len(rels['used_by'])} classes")
            if candidate.get('affected_files'):
                print(f"   ⚠️  May affect {len(candidate['affected_files'])} related files")
        
        print("\n" + "=" * 80)
        return ranked_candidates[:num_top_locations]
    
    def _score_and_rank_candidates(self, candidates: List[Dict], extracted_bug_info: Dict) -> List[Dict]:
        """
        Score, deduplicate, and rank candidate locations.
        
        Scoring strategy:
        - Aggregates scores for duplicate locations (same type + name)
        - Sorts by total score in descending order
        - Higher scores indicate stronger evidence of bug location
        
        Scoring weights:
        - Stack trace match: 10.0 (highest)
        - LLM-identified class: 5.0
        - Keyword match: 3.0
        - Semantic match: 2.0
        
        Args:
            candidates: List of candidate locations with initial scores
            extracted_bug_info: Extracted information from bug report
            
        Returns:
            Sorted list of unique candidate locations
        """
        # Aggregate scores for duplicate locations
        location_scores = {}
        for candidate in candidates:
            # Use (type, name) as unique key
            key = (candidate['type'], candidate['name'])
            
            if key not in location_scores:
                location_scores[key] = candidate
                location_scores[key]['score'] = 0.0
            
            # Accumulate scores (same location found multiple times = higher confidence)
            location_scores[key]['score'] += candidate['score']
        
        # Convert to list and sort by score (descending)
        ranked = list(location_scores.values())
        ranked.sort(key=lambda x: x['score'], reverse=True)
        
        return ranked
    
    def generate_investigation_suggestions(self, bug_report: str, 
                                          top_locations: List[Dict]) -> str:
        """
        Generate investigation suggestions for suspicious locations using LLM
        
        Args:
            bug_report: Original bug report
            top_locations: Top candidate locations from localization
            
        Returns:
            String with investigation suggestions
        """
        if not self.use_llm or not self.model or not top_locations:
            # Provide basic investigation points even without LLM
            suggestions = "Investigation Points (Keyword-based analysis):\n\n"
            for i, loc in enumerate(top_locations[:3], 1):
                suggestions += f"{i}. Investigate {loc['type']} '{loc['name']}'\n"
                suggestions += f"   File: {loc['file_path']}\n"
                suggestions += f"   Reason: {loc['reason']}\n\n"
            return suggestions
        
        try:
            # Rate limit API calls
            self._rate_limit_api_call()
            
            locations_text = "\n".join([
                f"- {loc['type']}: {loc['name']} in {loc['file_path']}"
                for loc in top_locations[:3]
            ])
            
            prompt = f"""You are an expert Java developer helping to localize bugs in the AspectJ weaver codebase.

Bug Report:
{bug_report}

Suspicious Locations Identified:
{locations_text}

Please provide:
1. What to investigate in these suspicious locations
2. Why these locations are likely related to the bug
3. What patterns or issues to look for in these files

Be specific and focus on investigation points, not fixes."""
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower():
                print(f"  ⚠ Rate limit hit - providing basic investigation points")
                self.use_llm = False
            
            # Provide basic investigation points as fallback
            suggestions = "Investigation Points (API limit reached):\n\n"
            for i, loc in enumerate(top_locations[:3], 1):
                suggestions += f"{i}. Investigate {loc['type']} '{loc['name']}'\n"
                suggestions += f"   File: {loc['file_path']}\n"
                suggestions += f"   Suspicion Score: {loc['score']}\n\n"
            return suggestions
    
    def localize_from_text(self, bug_report: str, bug_id: str = "unknown", num_top_locations: int = 5) -> Dict:
        """
        Localize bug from bug report text with full analysis.
        
        Args:
            bug_report: Bug report text
            bug_id: Identifier for the bug report
            num_top_locations: Number of top candidates to return (default: 5)
            
        Returns:
            Dictionary with:
            - bug_id: Bug identifier
            - top_locations: List of top N buggy locations with scores
            - fix_suggestions: AI-generated fix suggestions
        """
        print(f"\n{'='*80}")
        print(f"PROCESSING BUG REPORT: {bug_id}")
        print("="*80)
        print(bug_report[:300] + "..." if len(bug_report) > 300 else bug_report)
        
        # Identify buggy locations
        top_locations = self.identify_buggy_locations(bug_report, num_top_locations)
        
        # Generate investigation suggestions
        print("\n[6/6] Generating investigation suggestions...")
        print("-" * 80)
        investigation_suggestions = self.generate_investigation_suggestions(bug_report, top_locations)
        print(investigation_suggestions)
        
        return {
            'bug_id': bug_id,
            'top_locations': top_locations,
            'investigation_suggestions': investigation_suggestions
        }
    
    def localize_from_file(self, bug_report_file: str, num_top_locations: int = 5) -> Dict:
        """
        Localize bug from a bug report file.
        
        Args:
            bug_report_file: Path to bug report file (.txt)
            num_top_locations: Number of top candidates to return (default: 5)
            
        Returns:
            Dictionary with localization results
        """
        with open(bug_report_file, 'r', encoding='utf-8') as f:
            bug_report = f.read()
        
        return self.localize_from_text(bug_report, bug_report_file, num_top_locations)


def main():
    """Main function for bug localization"""
    # Initialize knowledge graph
    knowledge_graph = Neo4jKnowledgeGraph()
    
    if not knowledge_graph.driver:
        print("\n✗ Cannot proceed without Neo4j connection")
        print("Please start Neo4j and try again")
        return
    
    # Initialize bug localizer
    localizer = BugLocalizer(knowledge_graph, use_llm=True)  # Set to False to disable LLM
    
    # Process bug reports
    bug_reports_dir = Path('bug_reports')
    if bug_reports_dir.exists():
        bug_files = list(bug_reports_dir.glob('*.txt'))
        
        if bug_files:
            results = []
            for bug_file in bug_files:
                result = localizer.localize_from_file(str(bug_file))
                results.append(result)
                print("\n" + "="*80 + "\n")
            
            # Save results
            output_file = 'bug_localization_results.json'
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n✓ Saved results to {output_file}")
        else:
            print(f"\n✗ No bug reports found in {bug_reports_dir}")
    else:
        print(f"\n✗ Bug reports directory not found: {bug_reports_dir}")
        print("  Create it and add bug report files")
    
    knowledge_graph.close()


if __name__ == "__main__":
    main()

