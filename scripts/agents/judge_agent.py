"""
Judge Agent

The central orchestrator that:
1. Receives scores from all agents (BM25, Stack Trace, Pattern, Test)
2. Applies dynamic weights based on bug type
3. Checks for consensus/conflicts between agents
4. Performs final score fusion
5. Provides explanations for rankings
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import math


@dataclass
class AgentScore:
    """Score from a single agent"""
    agent_name: str
    score: float
    confidence: float
    evidence: List[str] = field(default_factory=list)


@dataclass
class CandidateJudgment:
    """Final judgment for a candidate"""
    class_name: str
    final_score: float
    agent_scores: Dict[str, AgentScore]
    consensus: bool  # Did agents agree?
    conflict_resolved: bool  # Was there a conflict?
    explanation: str
    rank: int = 0


@dataclass
class JudgmentResult:
    """Complete judgment result"""
    candidates: List[CandidateJudgment]
    bug_type: str
    weights_used: Dict[str, float]
    consensus_rate: float  # Percentage of candidates with consensus


class JudgeAgent:
    """
    The Judge Agent orchestrates multi-agent scoring.
    
    Scoring Formula:
        Final = W1*StackTrace + W2*BM25 + W3*Pattern + W4*Test + ConsensusBonus
    
    Consensus Handling:
        - If 3+ agents agree (top candidate same): +10% bonus
        - If agents disagree: weighted voting with confidence adjustment
    
    Conflict Resolution:
        - Stack trace gets priority for exact matches
        - BM25 gets priority for keyword-heavy bugs
        - Pattern gets priority for type-specific bugs (NPE, CCE)
    """
    
    # Default weights (overridden by BugTypeClassifier)
    DEFAULT_WEIGHTS = {
        'stack_trace': 0.35,
        'bm25': 0.30,
        'pattern': 0.20,
        'test': 0.15,
    }
    
    # Consensus bonus
    CONSENSUS_BONUS = 0.10
    
    # Minimum agreement threshold for consensus
    CONSENSUS_THRESHOLD = 0.6
    
    def __init__(self, weights: Dict[str, float] = None):
        """
        Initialize Judge Agent with optional custom weights.
        
        Args:
            weights: Custom weights for each signal
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self._normalize_weights()
    
    def _normalize_weights(self):
        """Ensure weights sum to 1.0"""
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v/total for k, v in self.weights.items()}
    
    def set_weights(self, weights: Dict[str, float]):
        """Update weights (called by BugTypeClassifier)"""
        self.weights = weights.copy()
        self._normalize_weights()
    
    def judge(self, 
              candidates: List[str],
              stack_trace_scores: Dict[str, float],
              bm25_scores: Dict[str, float],
              pattern_scores: Dict[str, float],
              test_scores: Dict[str, float],
              bug_type: str = 'GENERIC') -> JudgmentResult:
        """
        Perform final judgment on candidates.
        
        Args:
            candidates: List of candidate class names
            stack_trace_scores: Scores from stack trace analysis
            bm25_scores: Scores from BM25 ranking
            pattern_scores: Scores from PatternDetectionAgent
            test_scores: Scores from TestFailureAgent
            bug_type: Classified bug type
            
        Returns:
            JudgmentResult with ranked candidates and explanations
        """
        judgments = []
        consensus_count = 0
        
        for class_name in candidates:
            # Gather scores from all agents
            agent_scores = {
                'stack_trace': AgentScore(
                    agent_name='StackTraceAgent',
                    score=stack_trace_scores.get(class_name, 0.0),
                    confidence=1.0 if class_name in stack_trace_scores else 0.5,
                    evidence=['Found in stack trace'] if stack_trace_scores.get(class_name, 0) > 0 else []
                ),
                'bm25': AgentScore(
                    agent_name='BM25Agent',
                    score=bm25_scores.get(class_name, 0.0),
                    confidence=0.8,  # BM25 is generally reliable
                    evidence=[f'BM25 score: {bm25_scores.get(class_name, 0.0):.3f}']
                ),
                'pattern': AgentScore(
                    agent_name='PatternAgent',
                    score=pattern_scores.get(class_name, 0.0),
                    confidence=0.7,  # Pattern detection is heuristic
                    evidence=[f'Pattern score: {pattern_scores.get(class_name, 0.0):.3f}']
                ),
                'test': AgentScore(
                    agent_name='TestAgent',
                    score=test_scores.get(class_name, 0.0),
                    confidence=0.6,  # Test coverage may be incomplete
                    evidence=[f'Test coverage score: {test_scores.get(class_name, 0.0):.3f}']
                ),
            }
            
            # Check consensus
            consensus, conflict_resolved = self._check_consensus(agent_scores)
            if consensus:
                consensus_count += 1
            
            # Calculate final score
            final_score = self._calculate_final_score(
                agent_scores, consensus, conflict_resolved
            )
            
            # Generate explanation
            explanation = self._generate_explanation(
                class_name, agent_scores, consensus, final_score, bug_type
            )
            
            judgment = CandidateJudgment(
                class_name=class_name,
                final_score=final_score,
                agent_scores=agent_scores,
                consensus=consensus,
                conflict_resolved=conflict_resolved,
                explanation=explanation,
            )
            judgments.append(judgment)
        
        # Sort by final score (descending)
        judgments.sort(key=lambda x: x.final_score, reverse=True)
        
        # Assign ranks
        for i, judgment in enumerate(judgments):
            judgment.rank = i + 1
        
        # Calculate consensus rate
        consensus_rate = consensus_count / len(candidates) if candidates else 0.0
        
        return JudgmentResult(
            candidates=judgments,
            bug_type=bug_type,
            weights_used=self.weights.copy(),
            consensus_rate=consensus_rate,
        )
    
    def _check_consensus(self, agent_scores: Dict[str, AgentScore]) -> Tuple[bool, bool]:
        """
        Check if agents agree on this candidate.
        
        Returns:
            (consensus, conflict_resolved)
        """
        scores = [s.score for s in agent_scores.values() if s.score > 0]
        
        if not scores:
            return False, False
        
        # Check if scores are consistent
        mean_score = sum(scores) / len(scores)
        variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
        std_dev = math.sqrt(variance) if variance > 0 else 0
        
        # Low variance = consensus
        if std_dev < 0.2:
            return True, False
        
        # High variance = conflict
        # Check if we need to resolve
        if std_dev > 0.4:
            return False, True
        
        return False, False
    
    def _calculate_final_score(self, 
                                agent_scores: Dict[str, AgentScore],
                                consensus: bool,
                                conflict_resolved: bool) -> float:
        """
        Calculate final fused score.
        
        Formula: Final = Σ(Wi * Si * Ci) + ConsensusBonus
        Where Wi = weight, Si = score, Ci = confidence
        """
        weighted_sum = 0.0
        
        for signal, score_obj in agent_scores.items():
            weight = self.weights.get(signal, 0.0)
            weighted_sum += weight * score_obj.score * score_obj.confidence
        
        # Apply consensus bonus
        if consensus:
            weighted_sum *= (1 + self.CONSENSUS_BONUS)
        
        # Penalize if conflict had to be resolved
        if conflict_resolved:
            weighted_sum *= 0.95  # Small penalty for uncertainty
        
        return min(weighted_sum, 1.0)
    
    def _generate_explanation(self,
                               class_name: str,
                               agent_scores: Dict[str, AgentScore],
                               consensus: bool,
                               final_score: float,
                               bug_type: str) -> str:
        """Generate human-readable explanation for the ranking"""
        parts = []
        
        # Top signals
        sorted_signals = sorted(
            agent_scores.items(),
            key=lambda x: x[1].score * self.weights.get(x[0], 0),
            reverse=True
        )
        
        top_signal = sorted_signals[0] if sorted_signals else None
        if top_signal and top_signal[1].score > 0:
            parts.append(f"Primary signal: {top_signal[0]} ({top_signal[1].score:.2f})")
        
        # Consensus status
        if consensus:
            parts.append("Agents agree on this candidate")
        
        # Bug type relevance
        if bug_type != 'GENERIC':
            parts.append(f"Bug type: {bug_type}")
        
        # Stack trace mention
        if agent_scores['stack_trace'].score > 0.5:
            parts.append("Directly mentioned in stack trace")
        
        return "; ".join(parts) if parts else "Low confidence candidate"
    
    def get_top_k(self, result: JudgmentResult, k: int = 10) -> List[CandidateJudgment]:
        """Get top-K candidates from judgment result"""
        return result.candidates[:k]
    
    def explain_ranking(self, result: JudgmentResult) -> str:
        """Generate detailed explanation of the ranking"""
        lines = [
            f"Bug Type: {result.bug_type}",
            f"Consensus Rate: {result.consensus_rate:.1%}",
            f"Weights: {result.weights_used}",
            "",
            "Top Candidates:",
        ]
        
        for judgment in result.candidates[:10]:
            lines.append(
                f"  {judgment.rank}. {judgment.class_name} "
                f"(score: {judgment.final_score:.3f}) - {judgment.explanation}"
            )
        
        return "\n".join(lines)


# Standalone test
if __name__ == "__main__":
    judge = JudgeAgent()
    
    # Simulate agent scores
    candidates = ['World', 'BcelWorld', 'Shadow', 'Advice']
    
    stack_trace_scores = {'World': 0.8, 'BcelWorld': 0.6, 'Shadow': 0.0, 'Advice': 0.0}
    bm25_scores = {'World': 0.7, 'BcelWorld': 0.5, 'Shadow': 0.3, 'Advice': 0.2}
    pattern_scores = {'World': 0.6, 'BcelWorld': 0.7, 'Shadow': 0.4, 'Advice': 0.3}
    test_scores = {'World': 0.5, 'BcelWorld': 0.4, 'Shadow': 0.6, 'Advice': 0.2}
    
    result = judge.judge(
        candidates,
        stack_trace_scores,
        bm25_scores,
        pattern_scores,
        test_scores,
        bug_type='NPE'
    )
    
    print(judge.explain_ranking(result))
