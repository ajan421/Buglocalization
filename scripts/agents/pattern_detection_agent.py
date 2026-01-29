"""
Pattern Detection Agent

Analyzes code to detect patterns related to specific bug types.
Provides pattern-based scoring for bug localization.
"""

import re
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PatternMatch:
    """A detected pattern in code"""
    pattern_type: str
    location: str  # class or method name
    line_hint: Optional[str]
    severity: float  # 0.0 to 1.0
    description: str


@dataclass
class PatternAnalysis:
    """Result of pattern analysis for a class"""
    class_name: str
    matches: List[PatternMatch] = field(default_factory=list)
    score: float = 0.0
    risk_factors: List[str] = field(default_factory=list)


class PatternDetectionAgent:
    """
    Detects code patterns that correlate with specific bug types.
    
    Pattern Categories:
    - NULL_PATTERNS: Missing null checks, nullable returns
    - TYPE_PATTERNS: Unsafe casts, type checks
    - SYNC_PATTERNS: Missing synchronization, iterator issues
    - BOUNDS_PATTERNS: Array/collection access without bounds check
    - STATE_PATTERNS: State machine violations
    """
    
    # Patterns that indicate potential NULL issues
    NULL_PATTERNS = {
        'return_null': {
            'regex': r'return\s+null\s*;',
            'severity': 0.7,
            'description': 'Method returns null directly',
        },
        'no_null_check_before_call': {
            'regex': r'(\w+)\s*\.\s*\w+\s*\([^)]*\)',  # method call without null check
            'severity': 0.3,
            'description': 'Method call without null check',
        },
        'nullable_field': {
            'regex': r'(private|protected|public)\s+\w+\s+\w+\s*;(?!\s*//\s*@NotNull)',
            'severity': 0.2,
            'description': 'Field without non-null annotation',
        },
        'get_or_null': {
            'regex': r'\.\s*(get|find|lookup|resolve)\w*\s*\([^)]*\)',
            'severity': 0.5,
            'description': 'Method that may return null',
        },
    }
    
    # Patterns that indicate potential TYPE issues
    TYPE_PATTERNS = {
        'unsafe_cast': {
            'regex': r'\(\s*\w+\s*\)\s*\w+',  # (Type)var cast
            'severity': 0.6,
            'description': 'Direct cast without instanceof check',
        },
        'instanceof_without_cast': {
            'regex': r'instanceof\s+\w+',
            'severity': 0.1,  # Low - this is actually good
            'description': 'Type check present',
        },
        'generic_raw_type': {
            'regex': r'(List|Set|Map|Collection)\s+\w+\s*[=;]',
            'severity': 0.4,
            'description': 'Raw generic type usage',
        },
    }
    
    # Patterns that indicate potential SYNC issues
    SYNC_PATTERNS = {
        'iterator_without_sync': {
            'regex': r'\.iterator\(\)|for\s*\(\s*\w+\s+\w+\s*:\s*\w+\s*\)',
            'severity': 0.5,
            'description': 'Iterator usage (potential CME)',
        },
        'collection_modify_in_loop': {
            'regex': r'(\.add\(|\.remove\(|\.clear\(\))',
            'severity': 0.4,
            'description': 'Collection modification',
        },
        'missing_synchronized': {
            'regex': r'(private|protected|public)\s+(?!synchronized)\w+\s+\w+\s*\([^)]*\)\s*\{',
            'severity': 0.2,
            'description': 'Method without synchronized keyword',
        },
        'shared_mutable': {
            'regex': r'(static\s+(?!final)\w+\s+\w+|volatile\s+\w+)',
            'severity': 0.5,
            'description': 'Shared mutable state',
        },
    }
    
    # Patterns that indicate potential BOUNDS issues
    BOUNDS_PATTERNS = {
        'array_access': {
            'regex': r'\w+\s*\[\s*\w+\s*\]',
            'severity': 0.4,
            'description': 'Array index access',
        },
        'get_by_index': {
            'regex': r'\.get\s*\(\s*\d+\s*\)|\.get\s*\(\s*\w+\s*\)',
            'severity': 0.4,
            'description': 'Collection get by index',
        },
        'substring': {
            'regex': r'\.substring\s*\(',
            'severity': 0.5,
            'description': 'String substring operation',
        },
    }
    
    # Map bug types to pattern sets
    BUG_TYPE_PATTERNS = {
        'NPE': NULL_PATTERNS,
        'CCE': TYPE_PATTERNS,
        'CME': SYNC_PATTERNS,
        'AIOBE': BOUNDS_PATTERNS,
        'IAE': {},  # Checked at runtime
        'ISE': {},  # State-dependent
        'GENERIC': {},
    }
    
    def __init__(self, code_structure: Dict = None):
        """
        Initialize with parsed code structure.
        
        Args:
            code_structure: Dict containing parsed Java files and classes
        """
        self.code_structure = code_structure or {}
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for efficiency"""
        self._compiled = {}
        for pattern_set in [self.NULL_PATTERNS, self.TYPE_PATTERNS, 
                           self.SYNC_PATTERNS, self.BOUNDS_PATTERNS]:
            for name, info in pattern_set.items():
                self._compiled[name] = {
                    'regex': re.compile(info['regex']),
                    'severity': info['severity'],
                    'description': info['description'],
                }
    
    def analyze_class(self, class_name: str, bug_type: str = 'GENERIC',
                      source_code: str = None) -> PatternAnalysis:
        """
        Analyze a class for patterns related to a bug type.
        
        Args:
            class_name: Name of the class to analyze
            bug_type: The classified bug type (NPE, CCE, etc.)
            source_code: Optional source code if available
            
        Returns:
            PatternAnalysis with detected patterns and score
        """
        analysis = PatternAnalysis(class_name=class_name)
        
        # Get source code from structure or use provided
        if source_code is None:
            source_code = self._get_class_source(class_name)
        
        if not source_code:
            return analysis
        
        # Get patterns for this bug type + generic patterns
        patterns_to_check = {}
        if bug_type in self.BUG_TYPE_PATTERNS:
            patterns_to_check.update(self.BUG_TYPE_PATTERNS[bug_type])
        
        # Also check NULL_PATTERNS as they're common
        patterns_to_check.update(self.NULL_PATTERNS)
        
        # Run pattern detection
        total_severity = 0
        for pattern_name, pattern_info in patterns_to_check.items():
            if pattern_name not in self._compiled:
                continue
                
            compiled = self._compiled[pattern_name]
            matches = compiled['regex'].findall(source_code)
            
            if matches:
                # Create match record
                match = PatternMatch(
                    pattern_type=pattern_name,
                    location=class_name,
                    line_hint=matches[0] if matches else None,
                    severity=compiled['severity'],
                    description=compiled['description'],
                )
                analysis.matches.append(match)
                total_severity += compiled['severity'] * len(matches)
                
                # Add risk factor
                if compiled['severity'] >= 0.5:
                    analysis.risk_factors.append(
                        f"{pattern_name}: {compiled['description']}"
                    )
        
        # Calculate normalized score (0 to 1)
        max_possible = sum(p['severity'] * 3 for p in patterns_to_check.values())
        if max_possible > 0:
            analysis.score = min(total_severity / max_possible, 1.0)
        
        return analysis
    
    def analyze_candidates(self, candidates: List[str], bug_type: str = 'GENERIC',
                           source_codes: Dict[str, str] = None) -> Dict[str, PatternAnalysis]:
        """
        Analyze multiple candidate classes.
        
        Args:
            candidates: List of class names
            bug_type: The classified bug type
            source_codes: Optional dict mapping class names to source code
            
        Returns:
            Dict mapping class names to PatternAnalysis
        """
        results = {}
        source_codes = source_codes or {}
        
        for class_name in candidates:
            source = source_codes.get(class_name)
            results[class_name] = self.analyze_class(class_name, bug_type, source)
        
        return results
    
    def _get_class_source(self, class_name: str) -> Optional[str]:
        """
        Get source code for a class from the code structure.
        
        Args:
            class_name: Class name (simple or fully qualified)
            
        Returns:
            Source code string or None
        """
        if not self.code_structure:
            return None
        
        # Try to find in files
        simple_name = class_name.split('.')[-1]
        
        for file_info in self.code_structure.get('files', []):
            for cls in file_info.get('classes', []):
                if cls.get('name') == simple_name or cls.get('full_name') == class_name:
                    # Try to read the actual file
                    file_path = file_info.get('file_path')
                    if file_path:
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                return f.read()
                        except:
                            pass
        
        return None
    
    def get_pattern_scores(self, candidates: List[str], bug_type: str) -> Dict[str, float]:
        """
        Get pattern scores for candidates (simplified interface for Judge Agent).
        
        Args:
            candidates: List of class names
            bug_type: The classified bug type
            
        Returns:
            Dict mapping class names to pattern scores (0 to 1)
        """
        analyses = self.analyze_candidates(candidates, bug_type)
        return {name: analysis.score for name, analysis in analyses.items()}


# Standalone test
if __name__ == "__main__":
    # Test with sample code
    agent = PatternDetectionAgent()
    
    sample_code = '''
    public class TestClass {
        private String name;
        
        public String getName() {
            return null;  // return_null pattern
        }
        
        public void process(Object obj) {
            String s = (String) obj;  // unsafe_cast pattern
            for (Item item : items) {  // iterator pattern
                items.remove(item);  // collection_modify_in_loop
            }
        }
    }
    '''
    
    analysis = agent.analyze_class('TestClass', 'NPE', sample_code)
    print(f"Class: {analysis.class_name}")
    print(f"Score: {analysis.score:.2f}")
    print(f"Risk Factors: {analysis.risk_factors}")
    for match in analysis.matches:
        print(f"  - {match.pattern_type}: {match.description}")
