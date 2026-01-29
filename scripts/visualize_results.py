"""Visualization script for bug localization results"""

import json
import matplotlib.pyplot as plt
import numpy as np
import networkx as nx
from pathlib import Path


def load_results(results_file):
    with open(results_file, 'r') as f:
        return json.load(f)


def plot_scores_per_bug(results, output_dir):
    """Create bar chart showing top 5 scores for each bug"""
    
    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    axes = axes.flatten()
    
    colors = ['#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#3498db']
    
    for idx, bug in enumerate(results):
        if idx >= 7:
            break
            
        ax = axes[idx]
        bug_name = Path(bug['bug_id']).stem[:25]
        locations = bug['top_locations'][:5]
        
        names = [loc['name'].split('.')[-1][:15] for loc in locations]
        scores = [loc['score'] for loc in locations]
        
        bars = ax.barh(range(len(names)), scores, color=colors[:len(names)])
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names, fontsize=8)
        ax.invert_yaxis()
        ax.set_xlabel('Score')
        ax.set_title(bug_name, fontsize=10)
        
        for bar, score in zip(bars, scores):
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, 
                   f'{score:.0f}', va='center', fontsize=8)
    
    # Hide empty subplot
    axes[7].axis('off')
    
    plt.suptitle('Bug Localization Results - Top 5 Suspicious Classes per Bug', fontsize=14)
    plt.tight_layout()
    
    output_file = output_dir / 'scores_per_bug.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[+] Saved: {output_file}")


def plot_summary_heatmap(results, output_dir):
    """Create heatmap showing which classes appear across multiple bugs"""
    
    # Collect all classes and their scores per bug
    all_classes = {}
    bug_names = []
    
    for bug in results:
        bug_name = Path(bug['bug_id']).stem[:20]
        bug_names.append(bug_name)
        
        for loc in bug['top_locations'][:5]:
            class_name = loc['name'].split('.')[-1]
            if class_name not in all_classes:
                all_classes[class_name] = {}
            all_classes[class_name][bug_name] = loc['score']
    
    # Get top 15 most frequent classes
    class_counts = [(c, len(bugs)) for c, bugs in all_classes.items()]
    class_counts.sort(key=lambda x: -x[1])
    top_classes = [c[0] for c in class_counts[:15]]
    
    # Build matrix
    matrix = []
    for class_name in top_classes:
        row = []
        for bug_name in bug_names:
            score = all_classes[class_name].get(bug_name, 0)
            row.append(score)
        matrix.append(row)
    
    matrix = np.array(matrix)
    
    # Plot
    fig, ax = plt.subplots(figsize=(12, 8))
    
    im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto')
    
    ax.set_xticks(range(len(bug_names)))
    ax.set_xticklabels(bug_names, rotation=45, ha='right', fontsize=9)
    ax.set_yticks(range(len(top_classes)))
    ax.set_yticklabels(top_classes, fontsize=9)
    
    # Add score values
    for i in range(len(top_classes)):
        for j in range(len(bug_names)):
            if matrix[i, j] > 0:
                ax.text(j, i, f'{matrix[i, j]:.0f}', ha='center', va='center', 
                       fontsize=8, color='white' if matrix[i, j] > 20 else 'black')
    
    plt.colorbar(im, label='Score')
    ax.set_title('Class Suspicion Scores Across Bug Reports', fontsize=14)
    ax.set_xlabel('Bug Report')
    ax.set_ylabel('Class')
    
    plt.tight_layout()
    
    output_file = output_dir / 'class_heatmap.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[+] Saved: {output_file}")


def plot_score_distribution(results, output_dir):
    """Create histogram of all scores"""
    
    all_scores = []
    for bug in results:
        for loc in bug['top_locations']:
            all_scores.append(loc['score'])
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.hist(all_scores, bins=20, color='#3498db', edgecolor='white', alpha=0.8)
    ax.axvline(np.mean(all_scores), color='#e74c3c', linestyle='--', 
               label=f'Mean: {np.mean(all_scores):.1f}')
    ax.axvline(np.median(all_scores), color='#2ecc71', linestyle='--', 
               label=f'Median: {np.median(all_scores):.1f}')
    
    ax.set_xlabel('Suspicion Score')
    ax.set_ylabel('Count')
    ax.set_title('Distribution of Suspicion Scores')
    ax.legend()
    
    plt.tight_layout()
    
    output_file = output_dir / 'score_distribution.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[+] Saved: {output_file}")


def plot_top_classes_overall(results, output_dir):
    """Create bar chart of most suspicious classes overall"""
    
    class_scores = {}
    for bug in results:
        for loc in bug['top_locations']:
            class_name = loc['name'].split('.')[-1]
            if class_name not in class_scores:
                class_scores[class_name] = 0
            class_scores[class_name] += loc['score']
    
    # Sort by total score
    sorted_classes = sorted(class_scores.items(), key=lambda x: -x[1])[:15]
    
    names = [c[0] for c in sorted_classes]
    scores = [c[1] for c in sorted_classes]
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    colors = plt.cm.Reds(np.linspace(0.3, 0.9, len(names)))
    bars = ax.barh(range(len(names)), scores, color=colors)
    
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel('Total Suspicion Score (across all bugs)')
    ax.set_title('Most Suspicious Classes Overall')
    
    for bar, score in zip(bars, scores):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2, 
               f'{score:.0f}', va='center', fontsize=9)
    
    plt.tight_layout()
    
    output_file = output_dir / 'top_classes_overall.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[+] Saved: {output_file}")


def plot_network(results, output_dir):
    """Create network graph showing bugs connected to suspicious files"""
    
    G = nx.Graph()
    
    bug_nodes = []
    file_nodes = []
    class_nodes = []
    edges = []
    edge_weights = []
    edge_types = []
    
    for bug in results:
        bug_name = Path(bug['bug_id']).stem[:25]
        bug_nodes.append(bug_name)
        G.add_node(bug_name, type='bug')
        
        for loc in bug['top_locations'][:5]:
            # Get file name
            file_path = loc.get('file_path', '')
            file_name = Path(file_path).name if file_path else loc['name'].split('.')[-1] + '.java'
            
            # Get class name
            class_name = loc['name'].split('.')[-1]
            
            # Add file node
            if file_name not in file_nodes:
                file_nodes.append(file_name)
                G.add_node(file_name, type='file')
            
            # Add class node
            if class_name not in class_nodes:
                class_nodes.append(class_name)
                G.add_node(class_name, type='class')
            
            # Edge: bug -> file
            if not G.has_edge(bug_name, file_name):
                G.add_edge(bug_name, file_name, weight=loc['score'])
                edges.append((bug_name, file_name))
                edge_weights.append(loc['score'])
                edge_types.append('bug-file')
            
            # Edge: file -> class
            if not G.has_edge(file_name, class_name):
                G.add_edge(file_name, class_name, weight=loc['score'] / 2)
                edges.append((file_name, class_name))
                edge_weights.append(loc['score'] / 2)
                edge_types.append('file-class')
    
    fig, ax = plt.subplots(figsize=(20, 16))
    
    # Layout - use shell layout for better organization
    pos = nx.spring_layout(G, k=3, iterations=100, seed=42)
    
    # Draw file nodes (green, medium)
    nx.draw_networkx_nodes(G, pos, nodelist=file_nodes, 
                          node_color='#27ae60', node_size=1200, alpha=0.9, ax=ax)
    
    # Draw class nodes (red, small)
    nx.draw_networkx_nodes(G, pos, nodelist=class_nodes, 
                          node_color='#e74c3c', node_size=800, alpha=0.8, ax=ax)
    
    # Draw bug nodes (blue, large)
    nx.draw_networkx_nodes(G, pos, nodelist=bug_nodes,
                          node_color='#3498db', node_size=2500, alpha=0.9, ax=ax)
    
    # Draw edges
    max_weight = max(edge_weights) if edge_weights else 1
    
    for (u, v), weight, etype in zip(edges, edge_weights, edge_types):
        width = 1 + (weight / max_weight) * 4
        alpha = 0.4 + (weight / max_weight) * 0.4
        color = '#3498db' if etype == 'bug-file' else '#95a5a6'
        style = 'solid' if etype == 'bug-file' else 'dashed'
        nx.draw_networkx_edges(G, pos, edgelist=[(u, v)], 
                              width=width, alpha=alpha, edge_color=color, 
                              style=style, ax=ax)
    
    # Labels
    labels = {n: n[:18] for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, font_size=7, font_weight='bold', ax=ax)
    
    # Legend
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    legend = [
        Patch(facecolor='#3498db', label='Bug Report'),
        Patch(facecolor='#27ae60', label='Suspicious File'),
        Patch(facecolor='#e74c3c', label='Class'),
        Line2D([0], [0], color='#3498db', linewidth=2, label='Bug → File'),
        Line2D([0], [0], color='#95a5a6', linewidth=2, linestyle='--', label='File → Class'),
    ]
    ax.legend(handles=legend, loc='upper left', fontsize=10)
    
    ax.set_title('Bug Localization Network - Bugs → Files → Classes', fontsize=14)
    ax.axis('off')
    
    plt.tight_layout()
    
    output_file = output_dir / 'bug_class_network.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[+] Saved: {output_file}")


def main():
    project_root = Path(__file__).parent.parent
    results_file = project_root / 'outputs/json/bug_localization_results.json'
    output_dir = project_root / 'outputs/visualizations'
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not results_file.exists():
        print(f"[-] Results file not found: {results_file}")
        print("    Run main.py first to generate results")
        return
    
    print("Generating visualizations...")
    print("-" * 50)
    
    results = load_results(results_file)
    
    plot_network(results, output_dir)
    plot_scores_per_bug(results, output_dir)
    plot_summary_heatmap(results, output_dir)
    plot_score_distribution(results, output_dir)
    plot_top_classes_overall(results, output_dir)
    
    print("-" * 50)
    print(f"Done! Visualizations saved to: {output_dir}")


if __name__ == "__main__":
    main()

