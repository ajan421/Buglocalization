"""
Test Failure Agent

Analyzes test files and coverage to identify classes that are:
1. Tested together (co-occurrence in test files)
2. Referenced in failing test methods
3. Part of test fixtures and setups
"""

import re
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict


@dataclass
class TestCoverage:
    """Test coverage information for a class"""
    class_name: str
    test_files: List[str] = field(default_factory=list)
    co_tested_classes: Set[str] = field(default_factory=set)
    test_methods: List[str] = field(default_factory=list)
    coverage_score: float = 0.0


@dataclass
class TestAnalysis:
    """Result of test analysis"""
    candidates: Dict[str, TestCoverage]
    co_occurrence_matrix: Dict[str, Set[str]]
    test_file_count: int


class TestFailureAgent:
    """
    Analyzes test files to understand:
    1. Which classes are tested together
    2. Test coverage patterns
    3. Relationships between tested classes
    
    This helps identify:
    - Related classes that should be checked together
    - Classes with high test coupling (likely to fail together)
    """
    
    # Patterns to extract class references from test files
    TEST_PATTERNS = {
        'instantiation': r'new\s+(\w+)\s*\(',
        'static_call': r'(\w+)\s*\.\s*\w+\s*\(',
        'type_declaration': r'(\w+)\s+\w+\s*[=;]',
        'annotation': r'@\w+\s*\(\s*(\w+)\.class\s*\)',
        'import': r'import\s+[\w.]+\.(\w+);',
        'extends': r'extends\s+(\w+)',
        'implements': r'implements\s+([\w,\s]+)',
    }
    
    def __init__(self, test_dirs: List[str] = None, code_structure: Dict = None):
        """
        Initialize the Test Failure Agent.
        
        Args:
            test_dirs: Directories containing test files
            code_structure: Parsed code structure from CodeParser
        """
        self.test_dirs = test_dirs or []
        self.code_structure = code_structure or {}
        self._test_files_cache: Dict[str, str] = {}
        self._class_to_tests: Dict[str, List[str]] = defaultdict(list)
        self._co_occurrence: Dict[str, Set[str]] = defaultdict(set)
        
        # Build index if we have code structure
        if code_structure:
            self._build_index()
    
    def _build_index(self):
        """Build index of test files and class relationships"""
        for file_info in self.code_structure.get('files', []):
            file_path = file_info.get('file_path', '')
            
            # Check if this is a test file
            if self._is_test_file(file_path):
                classes_in_test = set()
                
                for cls in file_info.get('classes', []):
                    # Get classes referenced in test methods
                    for method in cls.get('methods', []):
                        if self._is_test_method(method.get('name', '')):
                            # Add tested class relationships
                            tested_class = self._extract_tested_class(cls.get('name', ''))
                            if tested_class:
                                classes_in_test.add(tested_class)
                                self._class_to_tests[tested_class].append(file_path)
                
                # Build co-occurrence
                for cls1 in classes_in_test:
                    for cls2 in classes_in_test:
                        if cls1 != cls2:
                            self._co_occurrence[cls1].add(cls2)
    
    def _is_test_file(self, file_path: str) -> bool:
        """Check if a file is a test file"""
        path_lower = file_path.lower()
        return (
            'test' in path_lower or 
            file_path.endswith('Test.java') or
            file_path.endswith('Tests.java') or
            '/test/' in file_path or
            '\\test\\' in file_path
        )
    
    def _is_test_method(self, method_name: str) -> bool:
        """Check if a method is a test method"""
        return (
            method_name.startswith('test') or
            method_name.startswith('should') or
            method_name.endswith('Test')
        )
    
    def _extract_tested_class(self, test_class_name: str) -> Optional[str]:
        """Extract the class being tested from a test class name"""
        # TestFoo -> Foo
        if test_class_name.startswith('Test'):
            return test_class_name[4:]
        # FooTest -> Foo
        if test_class_name.endswith('Test'):
            return test_class_name[:-4]
        # FooTests -> Foo
        if test_class_name.endswith('Tests'):
            return test_class_name[:-5]
        return None
    
    def analyze_for_bug(self, bug_report: str, candidates: List[str]) -> Dict[str, TestCoverage]:
        """
        Analyze test coverage relevant to bug candidates.
        
        Args:
            bug_report: The bug report text
            candidates: List of candidate class names
            
        Returns:
            Dict mapping class names to TestCoverage
        """
        results = {}
        
        # Extract test-related mentions from bug report
        test_classes = self._extract_test_mentions(bug_report)
        
        for class_name in candidates:
            simple_name = class_name.split('.')[-1]
            coverage = TestCoverage(class_name=class_name)
            
            # Check if class has test files
            if simple_name in self._class_to_tests:
                coverage.test_files = self._class_to_tests[simple_name]
            
            # Check co-occurrence with other candidates
            if simple_name in self._co_occurrence:
                coverage.co_tested_classes = self._co_occurrence[simple_name]
            
            # Calculate coverage score
            coverage.coverage_score = self._calculate_coverage_score(
                class_name, candidates, test_classes
            )
            
            results[class_name] = coverage
        
        return results
    
    def _extract_test_mentions(self, bug_report: str) -> Set[str]:
        """Extract test class/method mentions from bug report"""
        test_mentions = set()
        
        # Look for test class patterns
        patterns = [
            r'Test\w+',
            r'\w+Test(?:s)?',
            r'test\w+\(\)',
            r'@Test',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, bug_report)
            test_mentions.update(matches)
        
        return test_mentions
    
    def _calculate_coverage_score(self, class_name: str, 
                                   candidates: List[str],
                                   test_mentions: Set[str]) -> float:
        """
        Calculate test coverage score for a class.
        
        Factors:
        1. Has dedicated test file
        2. Co-tested with other candidates
        3. Mentioned in test names from bug report
        """
        simple_name = class_name.split('.')[-1]
        score = 0.0
        
        # Factor 1: Has test file (0.3)
        if simple_name in self._class_to_tests:
            score += 0.3
        
        # Factor 2: Co-tested with other candidates (0.4)
        co_tested = self._co_occurrence.get(simple_name, set())
        candidate_simple_names = {c.split('.')[-1] for c in candidates}
        overlap = co_tested & candidate_simple_names
        if overlap:
            score += 0.4 * (len(overlap) / len(candidates))
        
        # Factor 3: Mentioned in test names (0.3)
        for test_mention in test_mentions:
            if simple_name.lower() in test_mention.lower():
                score += 0.3
                break
        
        return min(score, 1.0)
    
    def get_co_tested_classes(self, class_name: str) -> Set[str]:
        """Get classes that are tested together with the given class"""
        simple_name = class_name.split('.')[-1]
        return self._co_occurrence.get(simple_name, set())
    
    def expand_candidates(self, candidates: List[str], 
                          max_expansion: int = 5) -> List[str]:
        """
        Expand candidate list with co-tested classes.
        
        Args:
            candidates: Initial candidate list
            max_expansion: Maximum classes to add
            
        Returns:
            Expanded candidate list
        """
        expanded = set(candidates)
        co_tested_counts = defaultdict(int)
        
        # Count co-occurrence with candidates
        for class_name in candidates:
            simple_name = class_name.split('.')[-1]
            for co_class in self._co_occurrence.get(simple_name, set()):
                if co_class not in expanded:
                    co_tested_counts[co_class] += 1
        
        # Add top co-tested classes
        sorted_co_tested = sorted(
            co_tested_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        for co_class, count in sorted_co_tested[:max_expansion]:
            expanded.add(co_class)
        
        return list(expanded)
    
    def get_test_scores(self, candidates: List[str], 
                        bug_report: str = "") -> Dict[str, float]:
        """
        Get test-based scores for candidates (simplified interface for Judge Agent).
        
        Args:
            candidates: List of class names
            bug_report: The bug report text
            
        Returns:
            Dict mapping class names to test scores (0 to 1)
        """
        coverages = self.analyze_for_bug(bug_report, candidates)
        return {name: cov.coverage_score for name, cov in coverages.items()}


# Standalone test
if __name__ == "__main__":
    agent = TestFailureAgent()
    
    # Simulate some test relationships
    agent._class_to_tests = {
        'World': ['WorldTest.java', 'WorldIntegrationTest.java'],
        'BcelWorld': ['BcelWorldTest.java'],
        'Shadow': ['ShadowTest.java', 'WorldTest.java'],
    }
    
    agent._co_occurrence = {
        'World': {'BcelWorld', 'Shadow', 'TypeX'},
        'BcelWorld': {'World', 'BcelObjectType'},
        'Shadow': {'World', 'Advice'},
    }
    
    candidates = ['World', 'BcelWorld', 'Shadow', 'Advice']
    bug_report = "NPE in WorldTest when resolving types"
    
    results = agent.analyze_for_bug(bug_report, candidates)
    
    for name, coverage in results.items():
        print(f"\n{name}:")
        print(f"  Test files: {coverage.test_files}")
        print(f"  Co-tested: {coverage.co_tested_classes}")
        print(f"  Score: {coverage.coverage_score:.2f}")
