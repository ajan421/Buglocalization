"""
Automated Bug Localization Evaluation System
Compares predictions with ground truth from parquet dataset
"""

import json
import pandas as pd
from pathlib import Path
from typing import List, Set, Dict
import ast


class BugLocalizationEvaluator:
    """Evaluate bug localization results against ground truth"""
    
    def __init__(self, results_file: str = "bug_localization_results.json"):
        """
        Args:
            results_file: JSON file with localization results
        """
        self.results_file = results_file
        
    def normalize_file_path(self, file_path: str) -> str:
        """
        Normalize file path for comparison.
        Handles different path formats and separators.
        """
        # Convert to forward slashes
        normalized = file_path.replace('\\', '/')
        
        # Remove common prefixes
        for prefix in ['src/', 'main/java/', 'test/java/', 'src/main/java/', 'src/test/java/']:
            if prefix in normalized:
                normalized = normalized.split(prefix, 1)[1]
        
        return normalized.lower()
    
    def files_match(self, predicted: str, ground_truth: str) -> bool:
        """
        Check if predicted file matches ground truth file.
        Uses flexible matching to handle path differences.
        """
        pred_norm = self.normalize_file_path(predicted)
        gt_norm = self.normalize_file_path(ground_truth)
        
        # Extract just the filename
        pred_name = Path(pred_norm).name
        gt_name = Path(gt_norm).name
        
        # Check if filenames match
        if pred_name == gt_name:
            return True
        
        # Check if one path ends with the other
        if pred_norm.endswith(gt_norm) or gt_norm.endswith(pred_norm):
            return True
        
        # Check if ground truth path is contained in prediction
        if gt_norm in pred_norm or pred_norm in gt_norm:
            return True
        
        return False
    
    def check_top_n_hit(self, predictions: List[str], ground_truth: List[str], n: int) -> tuple:
        """
        Check if any ground truth file appears in Top-N predictions.
        
        Args:
            predictions: List of predicted file paths (ranked)
            ground_truth: List of actual buggy files
            n: Check top N predictions
            
        Returns:
            (hit: bool, rank: int or None, matched_file: str or None)
        """
        top_n = predictions[:n]
        
        for rank, pred_file in enumerate(top_n, 1):
            for gt_file in ground_truth:
                if self.files_match(pred_file, gt_file):
                    return (True, rank, gt_file)
        
        return (False, None, None)
    
    def evaluate_results(self) -> Dict:
        """
        Evaluate bug localization results.
        
        Returns:
            Dictionary with evaluation metrics
        """
        # Load results
        print("Loading localization results...")
        with open(self.results_file, 'r') as f:
            results = json.load(f)
        
        print(f"Found {len(results)} bug localization results")
        
        metrics = {
            'total_bugs': 0,
            'bugs_with_ground_truth': 0,
            'top_1_hits': 0,
            'top_3_hits': 0,
            'top_5_hits': 0,
            'top_10_hits': 0,
            'details': []
        }
        
        for result in results:
            bug_id = result.get('bug_id', 'unknown')
            
            # Check if ground truth exists
            if 'ground_truth' not in result or not result['ground_truth']:
                continue
            
            # Parse ground truth
            ground_truth = result['ground_truth']
            if isinstance(ground_truth, str):
                try:
                    ground_truth = ast.literal_eval(ground_truth)
                except:
                    ground_truth = [ground_truth]
            
            if not ground_truth or ground_truth == [''] or ground_truth == []:
                continue
            
            metrics['bugs_with_ground_truth'] += 1
            
            # Get predictions
            predicted_files = [loc['file_path'] for loc in result.get('top_locations', [])]
            
            if not predicted_files:
                continue
            
            metrics['total_bugs'] += 1
            
            # Check Top-N hits
            top_1_hit, top_1_rank, top_1_file = self.check_top_n_hit(predicted_files, ground_truth, 1)
            top_3_hit, top_3_rank, top_3_file = self.check_top_n_hit(predicted_files, ground_truth, 3)
            top_5_hit, top_5_rank, top_5_file = self.check_top_n_hit(predicted_files, ground_truth, 5)
            top_10_hit, top_10_rank, top_10_file = self.check_top_n_hit(predicted_files, ground_truth, 10)
            
            if top_1_hit:
                metrics['top_1_hits'] += 1
            if top_3_hit:
                metrics['top_3_hits'] += 1
            if top_5_hit:
                metrics['top_5_hits'] += 1
            if top_10_hit:
                metrics['top_10_hits'] += 1
            
            # Store details
            detail = {
                'bug_id': bug_id,
                'ground_truth': ground_truth[:3],  # Show first 3
                'predicted_top_5': predicted_files[:5],
                'top_1_hit': top_1_hit,
                'top_3_hit': top_3_hit,
                'top_5_hit': top_5_hit,
                'top_10_hit': top_10_hit,
                'hit_rank': top_5_rank if top_5_hit else None,
                'matched_file': top_5_file if top_5_hit else None
            }
            metrics['details'].append(detail)
        
        # Calculate percentages
        if metrics['total_bugs'] > 0:
            metrics['top_1_accuracy'] = (metrics['top_1_hits'] / metrics['total_bugs']) * 100
            metrics['top_3_accuracy'] = (metrics['top_3_hits'] / metrics['total_bugs']) * 100
            metrics['top_5_accuracy'] = (metrics['top_5_hits'] / metrics['total_bugs']) * 100
            metrics['top_10_accuracy'] = (metrics['top_10_hits'] / metrics['total_bugs']) * 100
        else:
            metrics['top_1_accuracy'] = 0
            metrics['top_3_accuracy'] = 0
            metrics['top_5_accuracy'] = 0
            metrics['top_10_accuracy'] = 0
        
        return metrics
    
    def generate_report(self, metrics: Dict, output_file: str = "evaluation_report.txt"):
        """Generate comprehensive evaluation report"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("BUG LOCALIZATION EVALUATION REPORT\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"Results File: {self.results_file}\n")
            f.write(f"Total Results: {metrics['bugs_with_ground_truth']}\n")
            f.write(f"Evaluated Bugs: {metrics['total_bugs']}\n\n")
            
            f.write("ACCURACY METRICS:\n")
            f.write("-"*80 + "\n")
            f.write(f"Top-1 Accuracy:  {metrics['top_1_accuracy']:.2f}% ")
            f.write(f"({metrics['top_1_hits']}/{metrics['total_bugs']} bugs)\n")
            
            f.write(f"Top-3 Accuracy:  {metrics['top_3_accuracy']:.2f}% ")
            f.write(f"({metrics['top_3_hits']}/{metrics['total_bugs']} bugs)\n")
            
            f.write(f"Top-5 Accuracy:  {metrics['top_5_accuracy']:.2f}% ")
            f.write(f"({metrics['top_5_hits']}/{metrics['total_bugs']} bugs)\n")
            
            f.write(f"Top-10 Accuracy: {metrics['top_10_accuracy']:.2f}% ")
            f.write(f"({metrics['top_10_hits']}/{metrics['total_bugs']} bugs)\n\n")
            
            # Show hit distribution
            f.write("HIT DISTRIBUTION:\n")
            f.write("-"*80 + "\n")
            hit_ranks = [d['hit_rank'] for d in metrics['details'] if d['hit_rank'] is not None]
            if hit_ranks:
                from collections import Counter
                rank_counts = Counter(hit_ranks)
                for rank in sorted(rank_counts.keys()):
                    f.write(f"Rank #{rank}: {rank_counts[rank]} bugs\n")
            f.write("\n")
            
            # Show detailed results
            f.write("DETAILED RESULTS:\n")
            f.write("-"*80 + "\n\n")
            
            # Show correct predictions
            correct = [d for d in metrics['details'] if d['top_5_hit']]
            f.write(f"CORRECT PREDICTIONS (Top-5 Hits): {len(correct)}\n")
            f.write("-"*80 + "\n")
            for i, detail in enumerate(correct[:20], 1):  # Show first 20
                f.write(f"\n{i}. Bug: {detail['bug_id']}\n")
                f.write(f"   Ground Truth: {detail['ground_truth'][0]}\n")
                f.write(f"   Predicted at Rank #{detail['hit_rank']}: {detail['matched_file']}\n")
                f.write(f"   Status: [OK]\n")
            
            if len(correct) > 20:
                f.write(f"\n... and {len(correct)-20} more correct predictions\n")
            
            # Show missed predictions
            missed = [d for d in metrics['details'] if not d['top_5_hit']]
            if missed:
                f.write(f"\n\nMISSED PREDICTIONS (Not in Top-5): {len(missed)}\n")
                f.write("-"*80 + "\n")
                for i, detail in enumerate(missed[:10], 1):  # Show first 10
                    f.write(f"\n{i}. Bug: {detail['bug_id']}\n")
                    f.write(f"   Ground Truth: {detail['ground_truth'][0]}\n")
                    f.write(f"   Predicted #1: {detail['predicted_top_5'][0] if detail['predicted_top_5'] else 'None'}\n")
                    f.write(f"   Status: [MISS]\n")
                
                if len(missed) > 10:
                    f.write(f"\n... and {len(missed)-10} more missed predictions\n")
            
            f.write("\n" + "="*80 + "\n")
            f.write("[COMPLETE] Evaluation report generated\n")
            f.write("="*80 + "\n")
        
        print(f"\n[OK] Detailed report saved to: {output_file}")
    
    def print_summary(self, metrics: Dict):
        """Print summary to console"""
        print("\n" + "="*80)
        print("AUTOMATED EVALUATION SUMMARY")
        print("="*80)
        print(f"Total Bugs Evaluated: {metrics['total_bugs']}")
        print(f"\nAccuracy Metrics:")
        print(f"  Top-1:  {metrics['top_1_accuracy']:.1f}% ({metrics['top_1_hits']}/{metrics['total_bugs']})")
        print(f"  Top-3:  {metrics['top_3_accuracy']:.1f}% ({metrics['top_3_hits']}/{metrics['total_bugs']})")
        print(f"  Top-5:  {metrics['top_5_accuracy']:.1f}% ({metrics['top_5_hits']}/{metrics['total_bugs']})")
        print(f"  Top-10: {metrics['top_10_accuracy']:.1f}% ({metrics['top_10_hits']}/{metrics['total_bugs']})")
        print("="*80)


def main():
    """Main evaluation function"""
    print("="*80)
    print("AUTOMATED BUG LOCALIZATION EVALUATION")
    print("="*80)
    
    # Initialize evaluator
    evaluator = BugLocalizationEvaluator("bug_localization_results.json")
    
    # Run evaluation
    print("\nRunning evaluation...")
    metrics = evaluator.evaluate_results()
    
    # Generate report
    print("\nGenerating detailed report...")
    evaluator.generate_report(metrics, "evaluation_report.txt")
    
    # Print summary
    evaluator.print_summary(metrics)
    
    # Save metrics as JSON
    with open('evaluation_metrics.json', 'w') as f:
        # Remove details for cleaner JSON
        summary_metrics = {k: v for k, v in metrics.items() if k != 'details'}
        json.dump(summary_metrics, f, indent=2)
    print(f"\n[OK] Metrics saved to: evaluation_metrics.json")
    
    print("\n[COMPLETE] Automated evaluation finished!")
    print("="*80)


if __name__ == "__main__":
    main()



