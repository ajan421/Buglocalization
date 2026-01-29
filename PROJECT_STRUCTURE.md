# Project Structure

## 📁 Essential Files Kept

### Core Scripts (`scripts/`)
- `bug_localizer.py` - Main bug localization logic with multi-agent system
- `main.py` - Entry point for running the system
- `neo4j_loader.py` - Neo4j knowledge graph integration
- `code_parser.py` - Java code parsing and AST analysis
- `defects4j_evaluator.py` - Defects4J evaluation utilities
- `run_full_evaluation.py` - Full system evaluation script
- `visualize_results.py` - Results visualization

### Agent System (`scripts/agents/`)
- `__init__.py` - Package initialization
- `bug_type_classifier.py` - Bug type classification agent
- `judge_agent.py` - Score fusion and ranking agent
- `langgraph_orchestrator.py` - LangGraph workflow orchestration
- `pattern_detection_agent.py` - Code pattern detection agent
- `test_failure_agent.py` - Test coverage analysis agent

### Configuration
- `requirements.txt` - Python dependencies
- `README.md` - Project documentation
- `RANKING_AUTOMATION_EXPLAINED.md` - Ranking methodology explanation
- `SYSTEM_OVERVIEW.md` - System overview documentation

### Evaluation Results (`outputs/`)
- `combined_evaluation/combined_results.json` - **Main evaluation results** (100 bugs)
- `defects4j_evaluation/Ground Truth.json` - Ground truth data
- `defects4j_evaluation/bug_reports/*.txt` - Bug reports used for evaluation
- `visualizations/*.png` - Visualization charts

---

## 🗑️ Removed Files

### Unnecessary Scripts
- ❌ `run_defects4j_evaluation.py` - Duplicate evaluation script
- ❌ `automated_evaluation.py` - Unused parquet-based evaluation
- ❌ `check_parquet.py` - Utility script

### Test/Demo Files
- ❌ `Bug_Localization_Demo.ipynb` - Jupyter notebook demo
- ❌ `bug_reports/Sample_NPE_Bug.txt` - Test bug report
- ❌ `bug_reports/ClassCast_Type_Error.txt` - Test bug report

### Source Code Repositories (Can be regenerated)
- ❌ `aspectj/` - AspectJ source code (~10,000+ files)
- ❌ `commons-lang/` - Apache Commons Lang source code
- ❌ `commons-math3/` - Apache Commons Math source code
- ❌ `defects4j/` - Defects4J framework

### Duplicate Output Files
- ❌ Multiple evaluation report files (kept only combined_results.json)
- ❌ Old parsed JSON files (can be regenerated)
- ❌ Empty directories (`outputs/json/`, `outputs/results/`)

### Cache Directories
- ❌ `__pycache__/` - Python bytecode cache (all instances)

### Data Files
- ❌ `data/` - Parquet data files

---

## 📊 Project Size Reduction

**Before**: ~50,000+ files (including source code repositories)  
**After**: ~50 essential files

**Space Saved**: Several GB (source code repositories removed)

---

## 🔄 How to Regenerate Removed Files

### Source Code Repositories
If needed for evaluation, clone from:
- **Apache Commons Lang**: `git clone https://github.com/apache/commons-lang.git`
- **Apache Commons Math**: `git clone https://github.com/apache/commons-math.git`
- **Defects4J**: Follow Defects4J installation guide

### Parsed Data
Run `code_parser.py` to regenerate parsed JSON files:
```bash
python scripts/code_parser.py <source_directory>
```

### Cache Files
Python will automatically regenerate `__pycache__/` when scripts are run.

---

## ✅ What Remains

The project now contains **only essential files**:
1. Core bug localization system code
2. Multi-agent implementation
3. Evaluation scripts
4. Final evaluation results
5. Documentation

All unnecessary files, duplicates, and regenerable data have been removed.
