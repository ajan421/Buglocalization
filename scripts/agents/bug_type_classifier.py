"""
Bug Type Classifier Agent

Classifies bugs into categories and determines dynamic weights for scoring.
Categories: NPE, ClassCastException, ConcurrentModification, ArrayIndex, 
            IllegalArgument, IllegalState, IO, Generic
"""

import re
from typing import Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class BugClassification:
    """Result of bug classification"""
    bug_type: str
    confidence: float
    weights: Dict[str, float]
    indicators: list


class BugTypeClassifier:
    """
    Classifies bug reports into categories and provides dynamic weights.
    
    Bug Types:
    - NPE: NullPointerException
    - CCE: ClassCastException  
    - CME: ConcurrentModificationException
    - AIOBE: ArrayIndexOutOfBoundsException
    - IAE: IllegalArgumentException
    - ISE: IllegalStateException
    - IOE: IOException
    - GENERIC: Unknown/Other
    """
    
    # Bug type patterns for classification
    BUG_PATTERNS = {
        'NPE': [
            r'NullPointerException',
            r'NPE',
            r'null\s+pointer',
            r'is\s+null',
            r'was\s+null',
            r'returns?\s+null',
            r'\.get\w*\(\)\s+returns?\s+null',
            r'dereferenc',
        ],
        'CCE': [
            r'ClassCastException',
            r'cannot\s+be\s+cast',
            r'incompatible\s+types?',
            r'type\s+mismatch',
            r'wrong\s+type',
            r'cast\s+fail',
        ],
        'CME': [
            r'ConcurrentModificationException',
            r'concurrent\s+modification',
            r'modified\s+while\s+iterating',
            r'iterator.*invalid',
            r'collection.*changed',
        ],
        'AIOBE': [
            r'ArrayIndexOutOfBoundsException',
            r'IndexOutOfBoundsException',
            r'index\s+out\s+of\s+bounds',
            r'array\s+index',
            r'invalid\s+index',
        ],
        'IAE': [
            r'IllegalArgumentException',
            r'illegal\s+argument',
            r'invalid\s+argument',
            r'bad\s+argument',
            r'argument.*invalid',
        ],
        'ISE': [
            r'IllegalStateException',
            r'illegal\s+state',
            r'invalid\s+state',
            r'wrong\s+state',
            r'state.*invalid',
        ],
        'IOE': [
            r'IOException',
            r'FileNotFoundException',
            r'file\s+not\s+found',
            r'cannot\s+read',
            r'cannot\s+write',
            r'stream.*closed',
        ],
    }
    
    # Dynamic weights for each bug type
    # Format: {bug_type: {signal: weight}}
    # Signals: stack_trace, bm25, pattern, test
    WEIGHT_PROFILES = {
        'NPE': {
            'stack_trace': 0.35,
            'bm25': 0.25,
            'pattern': 0.25,  # High - null check patterns important
            'test': 0.15,
        },
        'CCE': {
            'stack_trace': 0.30,
            'bm25': 0.30,
            'pattern': 0.25,  # Type checking patterns
            'test': 0.15,
        },
        'CME': {
            'stack_trace': 0.35,
            'bm25': 0.20,
            'pattern': 0.30,  # High - sync patterns critical
            'test': 0.15,
        },
        'AIOBE': {
            'stack_trace': 0.40,  # Stack trace very reliable
            'bm25': 0.25,
            'pattern': 0.20,
            'test': 0.15,
        },
        'IAE': {
            'stack_trace': 0.30,
            'bm25': 0.30,
            'pattern': 0.20,
            'test': 0.20,  # Tests often reveal argument issues
        },
        'ISE': {
            'stack_trace': 0.30,
            'bm25': 0.25,
            'pattern': 0.25,
            'test': 0.20,
        },
        'IOE': {
            'stack_trace': 0.35,
            'bm25': 0.30,
            'pattern': 0.15,
            'test': 0.20,
        },
        'GENERIC': {
            'stack_trace': 0.35,
            'bm25': 0.30,
            'pattern': 0.20,
            'test': 0.15,
        },
    }
    
    def __init__(self):
        # Compile patterns for efficiency
        self._compiled_patterns = {}
        for bug_type, patterns in self.BUG_PATTERNS.items():
            self._compiled_patterns[bug_type] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
    
    def classify(self, bug_report: str) -> BugClassification:
        """
        Classify a bug report into a bug type category.
        
        Args:
            bug_report: The bug report text
            
        Returns:
            BugClassification with type, confidence, weights, and indicators
        """
        scores = {}
        indicators = {}
        
        # Score each bug type
        for bug_type, patterns in self._compiled_patterns.items():
            type_score = 0
            type_indicators = []
            
            for pattern in patterns:
                matches = pattern.findall(bug_report)
                if matches:
                    type_score += len(matches)
                    type_indicators.extend(matches[:3])  # Keep top 3 matches
            
            scores[bug_type] = type_score
            indicators[bug_type] = type_indicators
        
        # Find best match
        if not any(scores.values()):
            # No patterns matched
            return BugClassification(
                bug_type='GENERIC',
                confidence=0.5,
                weights=self.WEIGHT_PROFILES['GENERIC'],
                indicators=[]
            )
        
        # Get top bug type
        best_type = max(scores, key=scores.get)
        total_score = sum(scores.values())
        confidence = scores[best_type] / total_score if total_score > 0 else 0.5
        
        return BugClassification(
            bug_type=best_type,
            confidence=min(confidence, 1.0),
            weights=self.WEIGHT_PROFILES[best_type],
            indicators=indicators[best_type]
        )
    
    def get_weights(self, bug_type: str) -> Dict[str, float]:
        """Get weight profile for a bug type"""
        return self.WEIGHT_PROFILES.get(bug_type, self.WEIGHT_PROFILES['GENERIC'])
    
    def adjust_weights(self, base_weights: Dict[str, float], 
                       confidence: float) -> Dict[str, float]:
        """
        Adjust weights based on classification confidence.
        Lower confidence = more balanced weights.
        """
        if confidence >= 0.8:
            return base_weights
        
        # Blend with generic weights based on confidence
        generic = self.WEIGHT_PROFILES['GENERIC']
        adjusted = {}
        
        for signal in base_weights:
            adjusted[signal] = (
                confidence * base_weights[signal] + 
                (1 - confidence) * generic[signal]
            )
        
        return adjusted


# Standalone usage
if __name__ == "__main__":
    classifier = BugTypeClassifier()
    
    test_reports = [
        "NullPointerException in WildAnnotationTypePattern.resolveAnnotationValues()",
        "ClassCastException: Cannot cast String to Integer in TypeConverter",
        "ConcurrentModificationException when iterating over collection",
        "ArrayIndexOutOfBoundsException: Index 5 out of bounds for length 3",
        "Some generic error occurred in the system",
    ]
    
    for report in test_reports:
        result = classifier.classify(report)
        print(f"\nReport: {report[:50]}...")
        print(f"  Type: {result.bug_type}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Weights: {result.weights}")
