"""
LangGraph-based Multi-Agent Orchestrator for Bug Localization

This module uses LangGraph to orchestrate multiple specialized agents:
1. Bug Type Classifier - Classifies the bug and sets dynamic weights
2. Pattern Detection Agent - Analyzes code patterns
3. Test Failure Agent - Analyzes test relationships
4. Judge Agent - Fuses all scores and makes final decision

The agents communicate through a shared state and the graph defines
the workflow between them.
"""

from typing import TypedDict, List, Dict, Annotated, Sequence, Optional
from dataclasses import dataclass, field
import operator
import json

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

# Import our specialized agents
from .bug_type_classifier import BugTypeClassifier, BugClassification
from .pattern_detection_agent import PatternDetectionAgent
from .test_failure_agent import TestFailureAgent
from .judge_agent import JudgeAgent


# ============================================================================
# STATE DEFINITION
# ============================================================================

class AgentState(TypedDict):
    """
    Shared state passed between all agents in the graph.
    
    This represents the complete context of a bug localization task.
    """
    # Input
    bug_report: str
    
    # Extracted information
    keywords: List[str]
    stack_trace_classes: List[str]
    potential_classes: List[str]
    
    # Classification
    bug_type: str
    bug_confidence: float
    dynamic_weights: Dict[str, float]
    
    # Candidate scores from each agent
    candidate_names: List[str]
    bm25_scores: Dict[str, float]
    stack_trace_scores: Dict[str, float]
    pattern_scores: Dict[str, float]
    test_scores: Dict[str, float]
    
    # Final results
    final_rankings: List[Dict]
    consensus_rate: float
    
    # Execution trace (for explainability)
    agent_trace: Annotated[List[str], operator.add]
    
    # Error handling
    error: Optional[str]


# ============================================================================
# AGENT NODES
# ============================================================================

class BugLocalizationGraph:
    """
    LangGraph-based orchestrator for multi-agent bug localization.
    
    Graph Structure:
        start
          |
          v
        extract_info --> classify_bug --> get_candidates
                                              |
                          +-------------------+-------------------+
                          |                   |                   |
                          v                   v                   v
                    compute_bm25      detect_patterns      analyze_tests
                          |                   |                   |
                          +-------------------+-------------------+
                                              |
                                              v
                                        judge_fusion
                                              |
                                              v
                                            END
    """
    
    def __init__(self, knowledge_graph=None, bm25_ranker=None):
        """
        Initialize the LangGraph orchestrator.
        
        Args:
            knowledge_graph: Neo4j knowledge graph instance
            bm25_ranker: Pre-built BM25 index
        """
        self.knowledge_graph = knowledge_graph
        self.bm25_ranker = bm25_ranker
        
        # Initialize specialized agents
        self.bug_classifier = BugTypeClassifier()
        self.pattern_agent = PatternDetectionAgent()
        self.test_agent = TestFailureAgent()
        self.judge_agent = JudgeAgent()
        
        # Build the graph
        self.graph = self._build_graph()
        self.app = self.graph.compile()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        # Create the state graph
        workflow = StateGraph(AgentState)
        
        # Add nodes (each node is an agent)
        workflow.add_node("extract_info", self._extract_info_node)
        workflow.add_node("classify_bug", self._classify_bug_node)
        workflow.add_node("get_candidates", self._get_candidates_node)
        workflow.add_node("compute_bm25", self._compute_bm25_node)
        workflow.add_node("detect_patterns", self._detect_patterns_node)
        workflow.add_node("analyze_tests", self._analyze_tests_node)
        workflow.add_node("judge_fusion", self._judge_fusion_node)
        
        # Define edges (sequential workflow)
        # LangGraph works better with sequential flow
        workflow.set_entry_point("extract_info")
        
        workflow.add_edge("extract_info", "classify_bug")
        workflow.add_edge("classify_bug", "get_candidates")
        workflow.add_edge("get_candidates", "compute_bm25")
        workflow.add_edge("compute_bm25", "detect_patterns")
        workflow.add_edge("detect_patterns", "analyze_tests")
        workflow.add_edge("analyze_tests", "judge_fusion")
        workflow.add_edge("judge_fusion", END)
        
        return workflow
    
    # ========================================================================
    # NODE IMPLEMENTATIONS
    # ========================================================================
    
    def _extract_info_node(self, state: AgentState) -> dict:
        """Extract keywords, stack trace, and potential classes from bug report"""
        bug_report = state["bug_report"]
        
        # Use keyword parsing (could be enhanced with LLM)
        import re
        
        # Extract keywords (CamelCase words)
        keywords = []
        for word in bug_report.split():
            cleaned = word.strip('.,():;[]{}"\'-')
            if cleaned and cleaned[0].isupper() and any(c.islower() for c in cleaned):
                keywords.append(cleaned)
        
        # Extract stack trace classes
        stack_trace_classes = []
        for line in bug_report.split('\n'):
            if 'at ' in line and '(' in line:
                parts = line.split('at ')
                if len(parts) > 1:
                    class_part = parts[1].split('(')[0].strip()
                    if '.' in class_part:
                        full_class = class_part.rsplit('.', 1)[0]
                        stack_trace_classes.append(full_class)
        
        # Extract potential classes
        potential_classes = list(set(keywords))
        
        return {
            "keywords": list(set(keywords))[:20],
            "stack_trace_classes": stack_trace_classes,
            "potential_classes": potential_classes[:15],
            "agent_trace": ["[1] ExtractInfo: Parsed bug report"]
        }
    
    def _classify_bug_node(self, state: AgentState) -> dict:
        """Classify bug type and determine dynamic weights"""
        bug_report = state["bug_report"]
        
        # Use Bug Type Classifier
        classification = self.bug_classifier.classify(bug_report)
        
        return {
            "bug_type": classification.bug_type,
            "bug_confidence": classification.confidence,
            "dynamic_weights": classification.weights,
            "agent_trace": [f"[2] BugClassifier: {classification.bug_type} "
                          f"(confidence: {classification.confidence:.2f})"]
        }
    
    def _get_candidates_node(self, state: AgentState) -> dict:
        """Get candidate classes from knowledge graph"""
        candidates = []
        
        # Get candidates from BM25 index
        if self.bm25_ranker:
            query = f"{' '.join(state['keywords'])} {' '.join(state['potential_classes'])}"
            bm25_results = self.bm25_ranker.rank(query, top_k=100)
            candidates = [doc_id for doc_id, _ in bm25_results]
        
        # Also add stack trace classes
        for st_class in state["stack_trace_classes"]:
            simple_name = st_class.split('.')[-1]
            if simple_name not in candidates:
                candidates.append(simple_name)
        
        return {
            "candidate_names": candidates[:100],
            "agent_trace": [f"[3] GetCandidates: Found {len(candidates)} candidates"]
        }
    
    def _compute_bm25_node(self, state: AgentState) -> dict:
        """Compute BM25 scores for candidates"""
        bm25_scores = {}
        
        if self.bm25_ranker:
            query = f"{' '.join(state['keywords'])} {' '.join(state['potential_classes'])}"
            
            # Get scores for all candidates
            for doc_id in state["candidate_names"]:
                score = self.bm25_ranker.score(query, doc_id)
                bm25_scores[doc_id] = score
            
            # Normalize to [0, 1]
            max_score = max(bm25_scores.values()) if bm25_scores else 1.0
            if max_score > 0:
                bm25_scores = {k: v/max_score for k, v in bm25_scores.items()}
        
        return {
            "bm25_scores": bm25_scores,
            "agent_trace": [f"[4a] BM25Agent: Scored {len(bm25_scores)} candidates"]
        }
    
    def _detect_patterns_node(self, state: AgentState) -> dict:
        """Detect code patterns related to bug type"""
        bug_type = state["bug_type"]
        candidates = state["candidate_names"]
        
        # Use Pattern Detection Agent
        pattern_scores = self.pattern_agent.get_pattern_scores(candidates, bug_type)
        
        patterns_found = sum(1 for s in pattern_scores.values() if s > 0)
        
        return {
            "pattern_scores": pattern_scores,
            "agent_trace": [f"[4b] PatternAgent: Found patterns in {patterns_found} classes"]
        }
    
    def _analyze_tests_node(self, state: AgentState) -> dict:
        """Analyze test coverage and relationships"""
        candidates = state["candidate_names"]
        bug_report = state["bug_report"]
        
        # Use Test Failure Agent
        test_scores = self.test_agent.get_test_scores(candidates, bug_report)
        
        tests_found = sum(1 for s in test_scores.values() if s > 0)
        
        return {
            "test_scores": test_scores,
            "agent_trace": [f"[4c] TestAgent: Found test relations for {tests_found} classes"]
        }
    
    def _judge_fusion_node(self, state: AgentState) -> dict:
        """Fuse all scores using Judge Agent"""
        
        # Set dynamic weights from classifier
        self.judge_agent.set_weights(state["dynamic_weights"])
        
        # Compute stack trace scores
        stack_trace_scores = {}
        st_classes = set()
        for st in state["stack_trace_classes"]:
            st_classes.add(st.split('.')[-1])
        
        for candidate in state["candidate_names"]:
            simple_name = candidate.split('.')[-1]
            stack_trace_scores[candidate] = 1.0 if simple_name in st_classes else 0.0
        
        # Run Judge Agent
        judgment = self.judge_agent.judge(
            candidates=state["candidate_names"],
            stack_trace_scores=stack_trace_scores,
            bm25_scores=state.get("bm25_scores", {}),
            pattern_scores=state.get("pattern_scores", {}),
            test_scores=state.get("test_scores", {}),
            bug_type=state["bug_type"]
        )
        
        # Build final rankings
        final_rankings = []
        for j in judgment.candidates[:20]:
            final_rankings.append({
                "rank": j.rank,
                "class_name": j.class_name,
                "score": j.final_score,
                "consensus": j.consensus,
                "explanation": j.explanation,
                "stack_trace": stack_trace_scores.get(j.class_name, 0) > 0,
                "bm25_score": state.get("bm25_scores", {}).get(j.class_name, 0),
                "pattern_score": state.get("pattern_scores", {}).get(j.class_name, 0),
                "test_score": state.get("test_scores", {}).get(j.class_name, 0),
            })
        
        return {
            "stack_trace_scores": stack_trace_scores,
            "final_rankings": final_rankings,
            "consensus_rate": judgment.consensus_rate,
            "agent_trace": [f"[5] JudgeAgent: Fused scores, consensus={judgment.consensus_rate:.1%}"]
        }
    
    # ========================================================================
    # PUBLIC API
    # ========================================================================
    
    def localize(self, bug_report: str, top_k: int = 10) -> Dict:
        """
        Run the full multi-agent bug localization pipeline.
        
        Args:
            bug_report: The bug report text
            top_k: Number of top results to return
            
        Returns:
            Dict with rankings, trace, and metadata
        """
        # Initialize state
        initial_state: AgentState = {
            "bug_report": bug_report,
            "keywords": [],
            "stack_trace_classes": [],
            "potential_classes": [],
            "bug_type": "GENERIC",
            "bug_confidence": 0.0,
            "dynamic_weights": {},
            "candidate_names": [],
            "bm25_scores": {},
            "stack_trace_scores": {},
            "pattern_scores": {},
            "test_scores": {},
            "final_rankings": [],
            "consensus_rate": 0.0,
            "agent_trace": [],
            "error": None,
        }
        
        # Run the graph
        final_state = self.app.invoke(initial_state)
        
        # Return results
        return {
            "top_k": final_state["final_rankings"][:top_k],
            "bug_type": final_state["bug_type"],
            "bug_confidence": final_state["bug_confidence"],
            "weights_used": final_state["dynamic_weights"],
            "consensus_rate": final_state["consensus_rate"],
            "agent_trace": final_state["agent_trace"],
            "total_candidates": len(final_state["candidate_names"]),
        }
    
    def print_trace(self, result: Dict):
        """Print the agent execution trace"""
        print("\n" + "="*60)
        print("AGENT EXECUTION TRACE")
        print("="*60)
        for step in result["agent_trace"]:
            print(f"  {step}")
        print("="*60)


# ============================================================================
# STANDALONE TEST
# ============================================================================

if __name__ == "__main__":
    print("Testing LangGraph Orchestrator...")
    
    # Create orchestrator (without Neo4j for testing)
    orchestrator = BugLocalizationGraph()
    
    # Test bug report
    test_report = """
    NullPointerException in WildAnnotationTypePattern
    
    When matching annotations with array values, the pattern throws NPE.
    
    Stack trace:
    at org.aspectj.weaver.patterns.WildAnnotationTypePattern.resolveAnnotationValues(WildAnnotationTypePattern.java:123)
    at org.aspectj.weaver.patterns.SignaturePattern.match(SignaturePattern.java:456)
    """
    
    # Run localization
    result = orchestrator.localize(test_report, top_k=5)
    
    # Print trace
    orchestrator.print_trace(result)
    
    # Print results
    print(f"\nBug Type: {result['bug_type']} (confidence: {result['bug_confidence']:.2f})")
    print(f"Consensus Rate: {result['consensus_rate']:.1%}")
    print(f"\nTop-5 Rankings:")
    for r in result["top_k"]:
        print(f"  {r['rank']}. {r['class_name']}: {r['score']:.3f}")
