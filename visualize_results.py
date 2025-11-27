"""
Visualize bug localization results as network graph using NetworkX
"""

import json
import networkx as nx
import matplotlib.pyplot as plt
from pathlib import Path


def load_results(json_file: str = "result.json"):
    """Load bug localization results"""
    with open(json_file, 'r') as f:
        return json.load(f)


def create_bug_network(results, max_bugs: int = 5, max_locations: int = 5):
    """
    Create NetworkX graph from bug localization results
    
    Args:
        results: List of bug localization results
        max_bugs: Maximum number of bugs to include
        max_locations: Maximum locations per bug
    
    Returns:
        NetworkX DiGraph
    """
    G = nx.DiGraph()
    
    # Process each bug
    for bug_result in results[:max_bugs]:
        bug_id = bug_result['bug_id']
        
        # Add bug node
        G.add_node(bug_id, node_type='bug', color='red', size=3000)
        
        # Add top suspicious locations
        for loc in bug_result['top_locations'][:max_locations]:
            file_path = loc['file_path']
            file_name = Path(file_path).name
            score = loc['score']
            
            # Add file node
            if not G.has_node(file_name):
                G.add_node(file_name, 
                          node_type='file',
                          path=file_path,
                          color='lightblue',
                          size=2000)
            
            # Add edge from bug to suspicious file
            G.add_edge(bug_id, file_name, 
                      weight=score,
                      reason=loc['reason'],
                      edge_type='suspicious')
            
            # Add relationships (affected files)
            relationships = loc.get('relationships', {})
            
            # Add extends relationships
            for ext in relationships.get('extends', []):
                if ext.get('file'):  # Check if file exists
                    parent_file = Path(ext['file']).name
                    if not G.has_node(parent_file):
                        G.add_node(parent_file,
                                  node_type='related',
                                  path=ext['file'],
                                  color='lightgreen',
                                  size=1500)
                    G.add_edge(file_name, parent_file,
                              edge_type='extends',
                              weight=2)
            
            # Add implements relationships
            for impl in relationships.get('implements', []):
                if impl.get('file'):  # Check if file exists
                    interface_file = Path(impl['file']).name
                    if not G.has_node(interface_file):
                        G.add_node(interface_file,
                                  node_type='related',
                                  path=impl['file'],
                                  color='lightyellow',
                                  size=1500)
                    G.add_edge(file_name, interface_file,
                              edge_type='implements',
                              weight=2)
            
            # Add "used by" relationships
            for used in relationships.get('used_by', [])[:3]:  # Limit to 3
                if used.get('file'):  # Check if file exists
                    dependent_file = Path(used['file']).name
                    if not G.has_node(dependent_file):
                        G.add_node(dependent_file,
                                  node_type='affected',
                                  path=used['file'],
                                  color='orange',
                                  size=1000)
                    G.add_edge(dependent_file, file_name,
                              edge_type='depends_on',
                              weight=1)
    
    return G


def visualize_graph(G, output_file: str = "bug_network.png"):
    """
    Visualize the bug network graph
    
    Args:
        G: NetworkX graph
        output_file: Output image file name
    """
    plt.figure(figsize=(16, 12))
    
    # Get node attributes
    node_colors = [G.nodes[node].get('color', 'gray') for node in G.nodes()]
    node_sizes = [G.nodes[node].get('size', 1000) for node in G.nodes()]
    
    # Use spring layout for better visualization
    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
    
    # Draw nodes
    nx.draw_networkx_nodes(G, pos,
                          node_color=node_colors,
                          node_size=node_sizes,
                          alpha=0.8)
    
    # Draw labels
    nx.draw_networkx_labels(G, pos,
                           font_size=8,
                           font_weight='bold')
    
    # Separate edges by type
    suspicious_edges = [(u, v) for u, v, d in G.edges(data=True) 
                        if d.get('edge_type') == 'suspicious']
    extends_edges = [(u, v) for u, v, d in G.edges(data=True) 
                     if d.get('edge_type') == 'extends']
    implements_edges = [(u, v) for u, v, d in G.edges(data=True) 
                        if d.get('edge_type') == 'implements']
    depends_edges = [(u, v) for u, v, d in G.edges(data=True) 
                     if d.get('edge_type') == 'depends_on']
    
    # Draw suspicious edges (thick red solid)
    if suspicious_edges:
        nx.draw_networkx_edges(G, pos,
                              edgelist=suspicious_edges,
                              edge_color='#FF0000',  # Red
                              width=4,
                              alpha=0.8,
                              arrows=True,
                              arrowsize=25,
                              style='solid',
                              connectionstyle='arc3,rad=0.1')
    
    # Draw extends relationships (green dashed)
    if extends_edges:
        nx.draw_networkx_edges(G, pos,
                              edgelist=extends_edges,
                              edge_color='#00AA00',  # Green
                              width=2,
                              alpha=0.6,
                              arrows=True,
                              arrowsize=18,
                              style='dashed',
                              connectionstyle='arc3,rad=0.2')
    
    # Draw implements relationships (yellow dotted)
    if implements_edges:
        nx.draw_networkx_edges(G, pos,
                              edgelist=implements_edges,
                              edge_color='#FFD700',  # Gold
                              width=2,
                              alpha=0.6,
                              arrows=True,
                              arrowsize=18,
                              style='dotted',
                              connectionstyle='arc3,rad=0.15')
    
    # Draw depends_on relationships (orange dashdot)
    if depends_edges:
        nx.draw_networkx_edges(G, pos,
                              edgelist=depends_edges,
                              edge_color='#FF8C00',  # Dark orange
                              width=1.5,
                              alpha=0.5,
                              arrows=True,
                              arrowsize=15,
                              style='dashdot',
                              connectionstyle='arc3,rad=0.25')
    
    # Create legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='#FF0000', linewidth=4, label='Bug → Suspicious File', linestyle='solid'),
        Line2D([0], [0], color='#00AA00', linewidth=2, label='Extends Parent', linestyle='dashed'),
        Line2D([0], [0], color='#FFD700', linewidth=2, label='Implements Interface', linestyle='dotted'),
        Line2D([0], [0], color='#FF8C00', linewidth=1.5, label='Depends On', linestyle='dashdot')
    ]
    plt.legend(handles=legend_elements, loc='upper left', fontsize=10, framealpha=0.9)
    
    plt.title("Bug Localization Network\nRed nodes=Bugs | Blue=Suspicious files | Green=Parents | Yellow=Interfaces | Orange=Affected",
             fontsize=14, pad=20)
    plt.axis('off')
    plt.tight_layout()
    
    # Save
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n✓ Graph saved to {output_file}")
    
    # Show
    plt.show()


def print_graph_stats(G):
    """Print graph statistics"""
    print("\n" + "="*80)
    print("GRAPH STATISTICS")
    print("="*80)
    
    # Count node types
    bugs = [n for n, d in G.nodes(data=True) if d.get('node_type') == 'bug']
    files = [n for n, d in G.nodes(data=True) if d.get('node_type') == 'file']
    related = [n for n, d in G.nodes(data=True) if d.get('node_type') == 'related']
    affected = [n for n, d in G.nodes(data=True) if d.get('node_type') == 'affected']
    
    print(f"\nNodes:")
    print(f"  Bugs: {len(bugs)}")
    print(f"  Suspicious Files: {len(files)}")
    print(f"  Related Files: {len(related)}")
    print(f"  Affected Files: {len(affected)}")
    print(f"  Total: {G.number_of_nodes()}")
    
    print(f"\nEdges:")
    print(f"  Total: {G.number_of_edges()}")
    
    # Most connected files
    print(f"\nMost Connected Files:")
    degree_centrality = nx.degree_centrality(G)
    top_files = sorted(degree_centrality.items(), key=lambda x: x[1], reverse=True)[:5]
    for file, centrality in top_files:
        if G.nodes[file].get('node_type') != 'bug':
            print(f"  {file}: {centrality:.3f}")


def main():
    """Main execution"""
    import sys
    
    print("""
    ╔══════════════════════════════════════════════════════════════════════════╗
    ║           BUG LOCALIZATION NETWORK VISUALIZATION                         ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Load results
    results_file = "result.json"
    if not Path(results_file).exists():
        print(f"✗ {results_file} not found!")
        print("  Run: python main.py first")
        return
    
    print(f"Loading {results_file}...")
    results = load_results(results_file)
    print(f"✓ Loaded {len(results)} bug localization results")
    
    # Let user choose which bug to visualize
    bug_index = None
    
    if len(sys.argv) > 1:
        # Bug number provided as argument
        try:
            bug_index = int(sys.argv[1]) - 1
            if bug_index < 0 or bug_index >= len(results):
                print(f"✗ Invalid bug number. Choose 1-{len(results)}")
                return
        except ValueError:
            print("✗ Please provide a valid bug number")
            return
    
    if bug_index is None:
        # Show menu
        print("\nAvailable bug reports:")
        print("-" * 80)
        for i, result in enumerate(results, 1):
            bug_id = result['bug_id']
            num_locs = len(result.get('top_locations', []))
            print(f"  {i}. {bug_id} ({num_locs} suspicious locations)")
        print("-" * 80)
        
        choice = input(f"\nSelect bug to visualize (1-{len(results)}): ").strip()
        
        if choice.isdigit() and 1 <= int(choice) <= len(results):
            bug_index = int(choice) - 1
        else:
            print("✗ Invalid choice")
            return
    
    # Create network for selected bug
    selected_results = [results[bug_index]]
    bug_id = results[bug_index]['bug_id']
    
    # Clean bug_id for filename (remove path separators)
    clean_id = bug_id.replace('/', '_').replace('\\', '_').replace(':', '_')
    output_file = f"bug_network_{clean_id}.png"
    
    print(f"\nCreating network for {bug_id}...")
    
    G = create_bug_network(selected_results, max_bugs=1, max_locations=10)
    
    # Print stats
    print_graph_stats(G)
    
    # Visualize
    print("\nGenerating visualization...")
    visualize_graph(G, output_file)
    
    print("\n" + "="*80)
    print("✓ COMPLETE!")
    print("="*80)
    print(f"\nVisualization saved to: {output_file}")
    print("\nYou can now:")
    print(f"  1. View {output_file}")
    print("  2. Analyze the graph structure")
    print("\nUsage:")
    print("  python visualize_results.py        - Interactive menu (choose one bug)")
    print("  python visualize_results.py 1      - Visualize bug #1")
    print("  python visualize_results.py 3      - Visualize bug #3")
    print("\nLegend:")
    print("  🔴 Red nodes = Bug reports")
    print("  🔵 Blue nodes = Suspicious files")
    print("  🟢 Green nodes = Parent classes")
    print("  🟡 Yellow nodes = Interfaces")
    print("  🟠 Orange nodes = Affected/dependent files")
    print("\nEdge types:")
    print("  ━━━ Thick red solid = Bug → Suspicious file")
    print("  ╍╍╍ Green dashed = Extends parent class")
    print("  ┄┄┄ Yellow dotted = Implements interface")
    print("  ┉┉┉ Orange dashdot = Depends on relationship")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

