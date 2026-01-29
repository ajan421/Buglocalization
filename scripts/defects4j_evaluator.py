"""
Defects4J Evaluation Script
Evaluates bug localization system on real bugs from Defects4J benchmark.
"""

import os
import json
import csv
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import re


@dataclass
class Defects4JBug:
    """Represents a bug from Defects4J dataset."""
    bug_id: int
    project: str
    report_id: str
    report_url: str
    modified_classes: List[str]  # Ground truth
    trigger_tests: List[str]
    stack_trace: str
    exception_type: str = ""
    exception_message: str = ""
    
    def to_bug_report(self) -> str:
        """Convert to bug report format for our system."""
        lines = [
            f"Bug Report: {self.project}-{self.bug_id} ({self.report_id})",
            f"",
            f"Issue: {self.report_url}",
            f"",
        ]
        
        if self.exception_type:
            lines.append(f"Exception: {self.exception_type}")
            if self.exception_message:
                lines.append(f"Message: {self.exception_message}")
            lines.append("")
        
        if self.trigger_tests:
            lines.append("Failing Tests:")
            for test in self.trigger_tests[:3]:  # Limit to 3 tests
                lines.append(f"  - {test}")
            lines.append("")
        
        if self.stack_trace:
            lines.append("Stack Trace:")
            # Extract relevant stack trace lines (project-specific)
            for line in self.stack_trace.split('\n'):
                if 'org.apache.commons' in line or 'org.joda' in line:
                    lines.append(f"  {line.strip()}")
            lines.append("")
        
        # Add class hints from stack trace
        classes_in_trace = self._extract_classes_from_trace()
        if classes_in_trace:
            lines.append("Classes mentioned in trace:")
            for cls in classes_in_trace[:5]:
                lines.append(f"  - {cls}")
        
        return '\n'.join(lines)
    
    def _extract_classes_from_trace(self) -> List[str]:
        """Extract class names from stack trace."""
        classes = set()
        pattern = r'at\s+([\w.]+)\.\w+\('
        for match in re.finditer(pattern, self.stack_trace):
            full_class = match.group(1)
            if 'org.apache.commons' in full_class or 'org.joda' in full_class:
                # Get simple class name
                simple_name = full_class.split('.')[-1]
                if not simple_name.endswith('Test'):
                    classes.add(simple_name)
        return list(classes)


class Defects4JLoader:
    """Loads bugs from Defects4J dataset."""
    
    def __init__(self, defects4j_path: str):
        self.defects4j_path = Path(defects4j_path)
        self.projects_path = self.defects4j_path / "framework" / "projects"
    
    def get_available_projects(self) -> List[str]:
        """Get list of available projects."""
        projects = []
        for item in self.projects_path.iterdir():
            if item.is_dir() and (item / "active-bugs.csv").exists():
                projects.append(item.name)
        return sorted(projects)
    
    def load_project_bugs(self, project: str, limit: Optional[int] = None) -> List[Defects4JBug]:
        """Load all bugs for a project."""
        project_path = self.projects_path / project
        
        if not project_path.exists():
            raise ValueError(f"Project {project} not found")
        
        bugs = []
        
        # Read active-bugs.csv for bug metadata
        bugs_csv = project_path / "active-bugs.csv"
        with open(bugs_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                bug_id = int(row['bug.id'])
                
                # Read ground truth (modified classes)
                modified_file = project_path / "modified_classes" / f"{bug_id}.src"
                modified_classes = []
                if modified_file.exists():
                    with open(modified_file, 'r', encoding='utf-8') as mf:
                        modified_classes = [line.strip() for line in mf if line.strip()]
                
                # Read trigger tests and stack trace
                trigger_file = project_path / "trigger_tests" / str(bug_id)
                stack_trace = ""
                trigger_tests = []
                exception_type = ""
                exception_message = ""
                
                if trigger_file.exists():
                    with open(trigger_file, 'r', encoding='utf-8') as tf:
                        content = tf.read()
                        stack_trace = content
                        
                        # Parse test names
                        for line in content.split('\n'):
                            if line.startswith('--- '):
                                test_name = line[4:].strip()
                                trigger_tests.append(test_name)
                            elif 'Exception' in line or 'Error' in line:
                                # First exception line
                                if not exception_type:
                                    parts = line.split(':')
                                    exception_type = parts[0].strip()
                                    if len(parts) > 1:
                                        exception_message = ':'.join(parts[1:]).strip()
                
                bug = Defects4JBug(
                    bug_id=bug_id,
                    project=project,
                    report_id=row.get('report.id', ''),
                    report_url=row.get('report.url', ''),
                    modified_classes=modified_classes,
                    trigger_tests=trigger_tests,
                    stack_trace=stack_trace,
                    exception_type=exception_type,
                    exception_message=exception_message
                )
                bugs.append(bug)
                
                if limit and len(bugs) >= limit:
                    break
        
        return bugs


class Defects4JEvaluator:
    """Evaluates bug localization results against Defects4J ground truth."""
    
    def __init__(self):
        self.results = []
    
    def evaluate_single(
        self, 
        bug: Defects4JBug, 
        predicted_classes: List[str],
        k_values: List[int] = [1, 5, 10]
    ) -> Dict:
        """Evaluate a single bug prediction."""
        # Normalize ground truth class names (get simple names)
        ground_truth = set()
        for cls in bug.modified_classes:
            simple_name = cls.split('.')[-1]
            ground_truth.add(simple_name)
            ground_truth.add(cls)  # Also add full name
        
        # Normalize predictions
        predicted_simple = [p.split('.')[-1] for p in predicted_classes]
        
        result = {
            'bug_id': bug.bug_id,
            'project': bug.project,
            'ground_truth': list(ground_truth),
            'predicted': predicted_classes[:10],
            'metrics': {}
        }
        
        # Calculate Top-K hit
        for k in k_values:
            top_k_preds = set(predicted_simple[:k])
            hit = bool(top_k_preds & ground_truth)
            result['metrics'][f'top_{k}_hit'] = hit
        
        # Calculate rank of first correct prediction
        first_rank = -1
        for i, pred in enumerate(predicted_simple):
            if pred in ground_truth:
                first_rank = i + 1
                break
        result['metrics']['first_rank'] = first_rank
        
        # Mean Reciprocal Rank contribution
        result['metrics']['mrr'] = 1.0 / first_rank if first_rank > 0 else 0.0
        
        self.results.append(result)
        return result
    
    def compute_aggregate_metrics(self) -> Dict:
        """Compute aggregate metrics across all evaluated bugs."""
        if not self.results:
            return {}
        
        n = len(self.results)
        
        metrics = {
            'total_bugs': n,
            'top_1_accuracy': sum(1 for r in self.results if r['metrics'].get('top_1_hit')) / n,
            'top_5_accuracy': sum(1 for r in self.results if r['metrics'].get('top_5_hit')) / n,
            'top_10_accuracy': sum(1 for r in self.results if r['metrics'].get('top_10_hit')) / n,
            'mrr': sum(r['metrics'].get('mrr', 0) for r in self.results) / n,
            'bugs_found': sum(1 for r in self.results if r['metrics'].get('first_rank', -1) > 0),
        }
        
        # Rank distribution
        ranks = [r['metrics']['first_rank'] for r in self.results if r['metrics']['first_rank'] > 0]
        if ranks:
            metrics['mean_rank'] = sum(ranks) / len(ranks)
            metrics['median_rank'] = sorted(ranks)[len(ranks) // 2]
        
        return metrics
    
    def generate_report(self, output_path: str) -> str:
        """Generate evaluation report."""
        metrics = self.compute_aggregate_metrics()
        
        report_lines = [
            "=" * 60,
            "DEFECTS4J EVALUATION REPORT",
            "=" * 60,
            "",
            f"Total Bugs Evaluated: {metrics.get('total_bugs', 0)}",
            f"Bugs Successfully Localized: {metrics.get('bugs_found', 0)}",
            "",
            "ACCURACY METRICS:",
            "-" * 40,
            f"  Top-1 Accuracy:  {metrics.get('top_1_accuracy', 0) * 100:.1f}%",
            f"  Top-5 Accuracy:  {metrics.get('top_5_accuracy', 0) * 100:.1f}%",
            f"  Top-10 Accuracy: {metrics.get('top_10_accuracy', 0) * 100:.1f}%",
            "",
            f"  Mean Reciprocal Rank (MRR): {metrics.get('mrr', 0):.3f}",
            "",
        ]
        
        if 'mean_rank' in metrics:
            report_lines.extend([
                "RANK STATISTICS:",
                "-" * 40,
                f"  Mean Rank:   {metrics.get('mean_rank', 0):.1f}",
                f"  Median Rank: {metrics.get('median_rank', 0)}",
                "",
            ])
        
        report_lines.extend([
            "DETAILED RESULTS:",
            "-" * 40,
        ])
        
        for r in self.results[:20]:  # Show first 20
            status = "HIT" if r['metrics'].get('top_10_hit') else "MISS"
            rank = r['metrics'].get('first_rank', -1)
            rank_str = str(rank) if rank > 0 else "N/A"
            report_lines.append(
                f"  {r['project']}-{r['bug_id']:2d}: {status:4s} | Rank: {rank_str:3s} | "
                f"Ground Truth: {r['ground_truth'][0] if r['ground_truth'] else 'N/A'}"
            )
        
        if len(self.results) > 20:
            report_lines.append(f"  ... and {len(self.results) - 20} more bugs")
        
        report_lines.extend(["", "=" * 60])
        
        report = '\n'.join(report_lines)
        
        # Save report
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        # Also save JSON results
        json_path = output_path.replace('.txt', '.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'metrics': metrics,
                'results': self.results
            }, f, indent=2)
        
        return report


def main():
    """Run Defects4J evaluation."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    from bug_localizer import BugLocalizer
    
    # Paths
    project_root = Path(__file__).parent.parent
    defects4j_path = project_root / "defects4j"
    output_dir = project_root / "outputs" / "defects4j_evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("DEFECTS4J EVALUATION")
    print("=" * 60)
    
    # Load bugs
    loader = Defects4JLoader(str(defects4j_path))
    
    available_projects = loader.get_available_projects()
    print(f"\nAvailable projects: {', '.join(available_projects)}")
    
    # Load Lang bugs (start with 20 for testing)
    print("\nLoading Lang bugs...")
    bugs = loader.load_project_bugs("Lang", limit=20)
    print(f"Loaded {len(bugs)} bugs")
    
    # Show sample bug report
    print("\n" + "-" * 40)
    print("SAMPLE BUG REPORT (Lang-1):")
    print("-" * 40)
    print(bugs[0].to_bug_report())
    print("-" * 40)
    print(f"Ground Truth: {bugs[0].modified_classes}")
    print("-" * 40)
    
    # Save bug reports for manual inspection
    bug_reports_dir = output_dir / "bug_reports"
    bug_reports_dir.mkdir(exist_ok=True)
    
    for bug in bugs:
        report_path = bug_reports_dir / f"{bug.project}_{bug.bug_id}.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(bug.to_bug_report())
            f.write(f"\n\n---\nGROUND TRUTH: {', '.join(bug.modified_classes)}\n")
    
    print(f"\nBug reports saved to: {bug_reports_dir}")
    
    # Create ground truth file
    ground_truth = {}
    for bug in bugs:
        ground_truth[f"{bug.project}-{bug.bug_id}"] = {
            'modified_classes': bug.modified_classes,
            'simple_names': [c.split('.')[-1] for c in bug.modified_classes]
        }
    
    gt_path = output_dir / "ground_truth.json"
    with open(gt_path, 'w', encoding='utf-8') as f:
        json.dump(ground_truth, f, indent=2)
    
    print(f"Ground truth saved to: {gt_path}")
    
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("""
1. Parse commons-lang codebase:
   python code_parser.py --source ../commons-lang/src/main/java --project Lang

2. Load into Neo4j:
   python neo4j_loader.py --project Lang

3. Run evaluation:
   python defects4j_evaluator.py --run-evaluation

This will give you REAL accuracy metrics!
""")


if __name__ == "__main__":
    main()
