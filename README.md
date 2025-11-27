# Automated Bug Localization System

**Production-ready bug localization system** for AspectJ Java codebase using Neo4j knowledge graphs and Google Gemini LLM.

## 🎯 Overview

Automatically identifies the **Top-5 most likely buggy code locations** from bug reports using:

1. **🔍 Code Parsing** - Extracts classes, methods, fields from Java source
2. **📊 Knowledge Graph** - Builds Neo4j graph with code structure and relationships  
3. **🎯 Intelligent Ranking** - Multi-strategy scoring with LLM + keyword matching
4. **🔗 Relationship Analysis** - Identifies affected files and dependencies

### ✨ Key Features

✅ **Fully Automated Pipeline** - One command execution  
✅ **Top-5 Ranking** - Configurable to any number (3, 5, 10, etc.)  
✅ **LLM-Enhanced** - Google Gemini for semantic understanding  
✅ **Production Ready** - Professional naming, error handling, comprehensive docs  
✅ **Graph-Powered** - Leverages code relationships for better accuracy

## 📋 Prerequisites

### Required
- **Python 3.8+**
- **Neo4j Database** (Download from [neo4j.com/download](https://neo4j.com/download/))
  - Recommended: Neo4j Desktop for easy setup
  - Default credentials: username=`neo4j`, password=`password`
- **AspectJ Source Code** (already included in `aspectj/` directory)

### Optional
- **Google Gemini API Key** (for enhanced LLM-based analysis)
  - Get from: [Google AI Studio](https://makersuite.google.com/app/apikey)
  - **Recommended:** Use `.env` file (see Setup below)
  - Alternative: Set environment variable `GEMINI_API_KEY`
  - Without it, the system uses basic keyword matching

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Neo4j

#### Using Neo4j Desktop (Recommended):
1. Download and install [Neo4j Desktop](https://neo4j.com/download/)
2. Create a new database
3. Set password to `password` (or update `neo4j_loader.py` with your password)
4. Start the database

#### Using Docker:
```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

### 3. Configure Gemini API (Optional but Recommended)

#### Easy Setup:
```bash
python setup_env.py
```
This will prompt you for your API key and create a `.env` file.

#### Manual Setup:
1. Copy the example file:
   ```bash
   copy env.example .env       # Windows
   cp env.example .env         # Linux/Mac
   ```

2. Edit `.env` and add your API key:
   ```
   GEMINI_API_KEY=your-actual-api-key-here
   ```

#### Test It:
```bash
python test_gemini.py
```

### 4. Run the System

```bash
python main.py
```

This will:
- Parse the AspectJ Weaver source code
- Build a knowledge graph in Neo4j
- Process bug reports from `bug_reports/` directory
- Generate localization results

## 📁 Project Structure

```
buglocalisation/
├── aspectj/                    # AspectJ source code
│   └── weaver/                 # Weaver module (focus area)
│       └── src/                # Java source files
├── bug_reports/                # Bug report files (.txt)
│   ├── bug_report_1.txt
│   ├── bug_report_2.txt
│   └── bug_report_3.txt
├── code_parser.py              # Java code parser
├── neo4j_loader.py             # Neo4j knowledge graph builder
├── bug_localizer.py            # LLM-based bug localization
├── main.py                     # Main pipeline orchestrator
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── parsed_code.json            # Generated: Parsed code structure
└── localization_results.json   # Generated: Bug localization results
```

## 🔧 Usage

### Basic Usage

Run the complete pipeline:
```bash
python main.py
```

### Individual Components

#### 1. Parse Code Only
```bash
python code_parser.py
```
Output: `parsed_code.json`

#### 2. Build Knowledge Graph Only
```bash
python neo4j_loader.py
```
Requires: `parsed_code.json`

#### 3. Localize Bugs Only
```bash
python bug_localizer.py
```
Requires: Neo4j database loaded with code data

### Adding New Bug Reports

1. Create a `.txt` file in `bug_reports/` directory
2. Include bug details:
   - Summary
   - Stack traces (if available)
   - Error messages
   - Related classes/methods
3. Run `python main.py` or `python bug_localizer.py`

Example bug report format:
```
Bug Report #X: Brief Title

Summary: One-line description

Description:
Detailed description of the bug...

Error Message:
java.lang.NullPointerException
    at org.aspectj.weaver.World.resolve(World.java:456)
    ...

Steps to Reproduce:
1. ...
2. ...
```

## 🔍 How It Works

### 1. Code Parsing
- Uses `javalang` library to parse Java source files
- Extracts classes, methods, fields, and relationships
- Handles inheritance, interfaces, and method signatures
- Fallback regex-based parsing for complex files

### 2. Knowledge Graph
Neo4j nodes and relationships:

**Nodes:**
- `Class` - Java classes and interfaces
- `Method` - Methods with signatures
- `Field` - Class fields
- `Package` - Java packages
- `File` - Source files

**Relationships:**
- `DEFINED_IN` - Class defined in file
- `BELONGS_TO` - Class belongs to package
- `HAS_METHOD` - Class has method
- `HAS_FIELD` - Class has field
- `EXTENDS` - Class extends parent
- `IMPLEMENTS` - Class implements interface

### 3. Bug Localization

The system uses a multi-strategy approach:

1. **Stack Trace Analysis** (Highest Priority)
   - Extracts class names from stack traces
   - Directly queries knowledge graph

2. **Keyword Matching**
   - Identifies technical terms (class names, method names)
   - Searches graph for matches

3. **Semantic Analysis** (with OpenAI)
   - Parses bug report to extract relevant info
   - Generates fix suggestions

4. **Scoring & Ranking**
   - Aggregates matches from all strategies
   - Ranks candidates by relevance score

## 📊 Example Output

```
BUG LOCALIZATION
================================================================================

1. Parsing bug report...
   Summary: NullPointerException in Weaver
   Keywords: World, BcelWeaver, BcelWorld

2. Searching knowledge graph...
   Found 12 candidate locations

3. Ranking candidates...

4. Top candidates:
--------------------------------------------------------------------------------
1. CLASS: org.aspectj.weaver.World
   File: main/java/org/aspectj/weaver/World.java
   Score: 10.00
   Reason: Found in stack trace

2. CLASS: org.aspectj.weaver.bcel.BcelWeaver
   File: main/java/org/aspectj/weaver/bcel/BcelWeaver.java
   Score: 10.00
   Reason: Found in stack trace
...
```

## 🎛️ Configuration

### Neo4j Connection
Edit `neo4j_loader.py`:
```python
kg = Neo4jKnowledgeGraph(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="your-password"
)
```

### Gemini API Integration

#### Setup with .env file (Recommended):
```bash
python setup_env.py
```

Or manually create `.env`:
```
GEMINI_API_KEY=your-api-key-here
```

#### Alternative - Environment Variable:
```bash
# Windows
$env:GEMINI_API_KEY='your-api-key-here'

# Linux/Mac
export GEMINI_API_KEY='your-api-key-here'
```

The system will automatically use Gemini if the API key is set. To disable:
```python
localizer = BugLocalizer(kg, use_llm=False)
```

### Code Source Directory
Edit `main.py`:
```python
source_dir = "aspectj/weaver/src"  # Change to your module
```

## 🧪 Testing

Sample bug reports are provided in `bug_reports/`:
- `bug_report_1.txt` - NullPointerException in Weaver
- `bug_report_2.txt` - ClassCastException in Shadow Matching
- `bug_report_3.txt` - Memory Leak in Type Resolution

## 📈 Extending the System

### Add More Modules

To analyze additional AspectJ modules (e.g., `ajde`, `runtime`):
```python
# In main.py
source_dirs = [
    "aspectj/weaver/src",
    "aspectj/runtime/src",
    "aspectj/ajde/src"
]
```

### Custom Queries

Access Neo4j directly for custom queries:
```python
from neo4j_loader import Neo4jKnowledgeGraph

kg = Neo4jKnowledgeGraph()
results = kg.query_classes_by_name("World")
```

### Enhance Localization

Add custom scoring strategies in `bug_localizer.py`:
```python
def _rank_candidates(self, candidates, parsed_bug):
    # Add your custom ranking logic
    pass
```

## 🐛 Troubleshooting

### "Could not connect to Neo4j"
- Ensure Neo4j is running: Check Neo4j Desktop or `docker ps`
- Verify connection details in `neo4j_loader.py`
- Test connection: Open browser at `http://localhost:7474`

### "javalang parse error"
- Some complex Java files may fail to parse
- The system has fallback regex parsing
- Errors are logged but don't stop processing

### "No bug reports found"
- Check `bug_reports/` directory exists
- Ensure files have `.txt` extension
- Verify file permissions

## 📚 References

- [AspectJ Project](https://www.eclipse.org/aspectj/)
- [Neo4j Documentation](https://neo4j.com/docs/)
- [javalang Library](https://github.com/c2nes/javalang)

## 📝 License

This tool is for research and educational purposes. AspectJ source code is subject to its own license (Eclipse Public License).

## 🤝 Contributing

To improve the system:
1. Add more sophisticated parsing for AspectJ-specific syntax
2. Enhance bug report parsing with better NLP
3. Implement machine learning-based ranking
4. Add support for more languages (not just Java)

---

## 📚 Documentation

**Comprehensive documentation available:**

- **`SYSTEM_DOCUMENTATION.md`** - Complete technical documentation
  - Graph schema details
  - Ranking algorithm explanation
  - Pipeline architecture
  - Configuration guide
  - Performance metrics

- **`MENTOR_PRESENTATION_GUIDE.md`** - Quick reference for presentations
  - At-a-glance summaries
  - Demo talking points
  - Anticipated Q&A
  - Suggested demo flow

---

## 🎉 Recent Improvements (v2.0)

✅ **Professional Naming** - All variables, functions, and files renamed for clarity  
✅ **Enhanced Documentation** - Comprehensive docs with examples and diagrams  
✅ **Improved Ranking** - Better scoring algorithm with configurable weights  
✅ **Better Output** - Clear console output with emojis and progress tracking  
✅ **Production Ready** - Error handling, fallbacks, and scalability improvements  

---

**Made with ❤️ for better bug localization**

*Version 2.0 - Production Ready | November 2025*

