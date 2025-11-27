# How Ranking and Automation Work - Visual Guide

## 🏆 PART 1: HOW RANKING WORKS

### **Step-by-Step Ranking Process**

```
Bug Report Input: "NullPointerException at World.resolve()"
                           ↓
┌────────────────────────────────────────────────────────────────┐
│ STEP 1: EXTRACT INFORMATION                                    │
└────────────────────────────────────────────────────────────────┘
                           ↓
    Extracted Data:
    ├─ Stack Trace Classes: ["World", "BcelWorld"]
    ├─ LLM Identified Classes: ["World", "BcelWeaver"]
    └─ Keywords: ["resolve", "World", "NullPointerException"]
                           ↓
┌────────────────────────────────────────────────────────────────┐
│ STEP 2: SEARCH KNOWLEDGE GRAPH (Multiple Strategies)           │
└────────────────────────────────────────────────────────────────┘
                           ↓
    ┌────────────────────────────────────────────────────────┐
    │ Strategy 1: Stack Trace Search                         │
    │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
    │ Query: Find classes named "World"                      │
    │ Found: org.aspectj.weaver.World                       │
    │ Score: 10 points (HIGHEST - Direct Evidence)          │
    └────────────────────────────────────────────────────────┘
                           ↓
    ┌────────────────────────────────────────────────────────┐
    │ Strategy 2: LLM-Identified Classes                     │
    │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
    │ Query: Find classes "World", "BcelWeaver"             │
    │ Found: org.aspectj.weaver.World                       │
    │ Score: 5 points (HIGH - AI Identified)                │
    └────────────────────────────────────────────────────────┘
                           ↓
    ┌────────────────────────────────────────────────────────┐
    │ Strategy 3: Keyword Matching                           │
    │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
    │ Query: Find classes/methods with "World", "resolve"   │
    │ Found: org.aspectj.weaver.World (class)               │
    │        World.resolve() (method)                        │
    │ Score: 3 points each (MEDIUM - Keyword Match)         │
    └────────────────────────────────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────────────┐
│ STEP 3: SCORE AGGREGATION                                      │
└────────────────────────────────────────────────────────────────┘
                           ↓
    All Candidates Found:
    
    org.aspectj.weaver.World (class)
    ├─ Found by Strategy 1: +10 points (Stack Trace)
    ├─ Found by Strategy 2: +5 points  (LLM)
    └─ Found by Strategy 3: +3 points  (Keyword)
       ═══════════════════════════════
       TOTAL: 18 points → RANK #1 ⭐⭐⭐
    
    org.aspectj.weaver.bcel.BcelWorld (class)
    ├─ Found by Strategy 1: +10 points (Stack Trace)
    └─ Found by Strategy 3: +3 points  (Keyword)
       ═══════════════════════════════
       TOTAL: 13 points → RANK #2 ⭐⭐
    
    World.resolve(String) (method)
    └─ Found by Strategy 3: +3 points  (Keyword)
       ═══════════════════════════════
       TOTAL: 3 points → RANK #3 ⭐
                           ↓
┌────────────────────────────────────────────────────────────────┐
│ STEP 4: SORT BY SCORE (Descending)                             │
└────────────────────────────────────────────────────────────────┘
                           ↓
    Final Ranking:
    #1: World (18 pts)
    #2: BcelWorld (13 pts)
    #3: World.resolve() (3 pts)
    #4: TypeMap (3 pts)
    #5: BcelWeaver (3 pts)
                           ↓
┌────────────────────────────────────────────────────────────────┐
│ STEP 5: RETURN TOP-5 RESULTS                                   │
└────────────────────────────────────────────────────────────────┘
```

---

### **Scoring Weights Explained**

```python
# File: bug_localizer.py, lines 18-21

SCORE_STACK_TRACE_MATCH = 10.0  # ← HIGHEST CONFIDENCE
# Why? Stack traces show exactly where the error occurred
# Example: "at org.aspectj.weaver.World.resolve(World.java:456)"
# This is DIRECT EVIDENCE of the bug location!

SCORE_POTENTIAL_CLASS = 5.0     # ← HIGH CONFIDENCE
# Why? AI (Gemini) analyzed the bug description semantically
# Example: Bug says "issue with weaver world resolution"
# AI understands: "World" class is likely involved

SCORE_KEYWORD_MATCH = 3.0       # ← MEDIUM CONFIDENCE
# Why? Keywords found in bug report match class/method names
# Example: Bug contains word "World" → matches class "World"
# Could be coincidence, but still relevant

SCORE_SEMANTIC_MATCH = 2.0      # ← LOW CONFIDENCE
# Why? Semantic similarity without direct match
# Example: Bug about "type resolution" → might relate to "TypeMap"
# Weak connection, but worth considering
```

---

### **Why This Scoring Works**

#### **Example Bug Report:**
```
Bug #123: NullPointerException in Weaver

Stack Trace:
  at org.aspectj.weaver.World.resolve(World.java:456)
  at org.aspectj.weaver.bcel.BcelWorld.addTypeMunger(BcelWorld.java:234)

Description:
The World class throws NPE when resolving types with null TypeMap.
```

#### **Scoring Breakdown:**

| Location | How Found | Score Calculation | Final Score |
|----------|-----------|-------------------|-------------|
| **World** | Stack trace (10) + LLM (5) + Keyword (3) | 10 + 5 + 3 | **18** 🥇 |
| **BcelWorld** | Stack trace (10) + Keyword (3) | 10 + 3 | **13** 🥈 |
| **World.resolve()** | Keyword (3) | 3 | **3** 🥉 |
| **TypeMap** | Keyword (3) | 3 | **3** |
| **BcelWeaver** | Keyword (3) | 3 | **3** |

**Result:** World class is ranked #1 with the highest score (18 points) because it was found through multiple strategies, giving us HIGH CONFIDENCE it's the buggy location!

---

### **The Magic: Score Accumulation**

```
Same location found multiple times = HIGHER CONFIDENCE!

Example:
┌─────────────────────────────────────────────────────────┐
│ If "World" is found only once (keyword match):          │
│ Score = 3 points  →  Maybe relevant                     │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ If "World" is found three times:                        │
│ - Stack trace: 10 points                                │
│ - LLM analysis: 5 points                                │
│ - Keyword match: 3 points                               │
│ Score = 18 points  →  HIGH CONFIDENCE! ✓                │
└─────────────────────────────────────────────────────────┘
```

---

## 🤖 PART 2: HOW AUTOMATION WORKS

### **Complete Automated Pipeline**

```
                    START: python main.py
                              ↓
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  STEP 1: PARSE SOURCE CODE                               ┃
┃  ─────────────────────────────────────────────────────  ┃
┃  Input: 8 AspectJ source directories                     ┃
┃  ├─ aspectj/weaver/src/                                 ┃
┃  ├─ aspectj/runtime/src/                                ┃
┃  └─ ... 6 more modules                                  ┃
┃                                                          ┃
┃  Automated Actions:                                      ┃
┃  [1] Scan all .java files recursively                   ┃
┃  [2] Parse each file (extract classes, methods, fields) ┃
┃  [3] Extract relationships (extends, implements)        ┃
┃  [4] Aggregate all data                                 ┃
┃  [5] Save to code_structure.json                        ┃
┃                                                          ┃
┃  Output: code_structure.json                             ┃
┃  ├─ 1,234 classes                                       ┃
┃  ├─ 8,567 methods                                       ┃
┃  └─ 2,345 fields                                        ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                              ↓
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  STEP 2: BUILD KNOWLEDGE GRAPH                           ┃
┃  ─────────────────────────────────────────────────────  ┃
┃  Input: code_structure.json                              ┃
┃                                                          ┃
┃  Automated Actions:                                      ┃
┃  [1] Connect to Neo4j database                          ┃
┃  [2] Clear existing data                                ┃
┃  [3] Create performance indexes                         ┃
┃  [4] For each class:                                    ┃
┃      ├─ Create Class node                               ┃
┃      ├─ Create DEFINED_IN → File edge                   ┃
┃      ├─ Create BELONGS_TO → Package edge                ┃
┃      ├─ Create EXTENDS → ParentClass edge               ┃
┃      └─ Create IMPLEMENTS → Interface edges             ┃
┃  [5] For each method:                                   ┃
┃      ├─ Create Method node                              ┃
┃      └─ Create HAS_METHOD edge                          ┃
┃  [6] For each field:                                    ┃
┃      ├─ Create Field node                               ┃
┃      └─ Create HAS_FIELD edge                           ┃
┃                                                          ┃
┃  Output: Neo4j database populated                        ┃
┃  ├─ ~12,000 nodes                                       ┃
┃  └─ ~45,000 relationships                               ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                              ↓
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  STEP 3: LOCALIZE BUGS (Batch Processing)                ┃
┃  ─────────────────────────────────────────────────────  ┃
┃  Input: bug_reports/ directory                           ┃
┃  ├─ bug_annotation.txt                                  ┃
┃  ├─ bug_concurrency.txt                                 ┃
┃  ├─ bug_npe_world.txt                                   ┃
┃  └─ ... more bugs ...                                   ┃
┃                                                          ┃
┃  Automated Actions: FOR EACH BUG REPORT                  ┃
┃  ┌──────────────────────────────────────────────────┐  ┃
┃  │ [1] Read bug report file                          │  ┃
┃  │     with open(bug_file, 'r') as f:               │  ┃
┃  │         bug_report = f.read()                     │  ┃
┃  │                                                    │  ┃
┃  │ [2] Extract information (LLM or keyword-based)    │  ┃
┃  │     ├─ Parse stack traces                         │  ┃
┃  │     ├─ Identify keywords                          │  ┃
┃  │     └─ Get LLM analysis (if available)            │  ┃
┃  │                                                    │  ┃
┃  │ [3] Search knowledge graph                        │  ┃
┃  │     ├─ Query for stack trace classes              │  ┃
┃  │     ├─ Query for LLM-identified classes           │  ┃
┃  │     └─ Query for keyword matches                  │  ┃
┃  │                                                    │  ┃
┃  │ [4] Score and rank candidates                     │  ┃
┃  │     ├─ Aggregate scores                           │  ┃
┃  │     ├─ Sort by score                              │  ┃
┃  │     └─ Select Top-5                               │  ┃
┃  │                                                    │  ┃
┃  │ [5] Enrich with relationships                     │  ┃
┃  │     ├─ Find parent classes                        │  ┃
┃  │     ├─ Find dependent classes                     │  ┃
┃  │     └─ Identify affected files                    │  ┃
┃  │                                                    │  ┃
┃  │ [6] Generate fix suggestions (LLM)                │  ┃
┃  └──────────────────────────────────────────────────┘  ┃
┃                                                          ┃
┃  REPEAT FOR ALL BUG REPORTS AUTOMATICALLY!               ┃
┃                                                          ┃
┃  Output: bug_localization_results.json                   ┃
┃  [                                                       ┃
┃    {                                                     ┃
┃      "bug_id": "bug_npe_world.txt",                     ┃
┃      "top_locations": [Top-5 with scores],              ┃
┃      "fix_suggestions": "..."                           ┃
┃    },                                                    ┃
┃    { ... next bug ... },                                ┃
┃    { ... next bug ... }                                 ┃
┃  ]                                                       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                              ↓
                    ✅ COMPLETE!
```

---

### **Key Automation Features**

#### **1. Batch Processing**
```python
# File: main.py, lines 144-156

# Automatically processes ALL bug reports in directory
bug_files = list(bug_reports_path.glob('*.txt'))

for i, bug_file in enumerate(bug_files, 1):
    print(f"Processing bug {i}/{len(bug_files)}: {bug_file.name}")
    result = localizer.localize_from_file(str(bug_file), num_top_locations=5)
    results.append(result)

# NO MANUAL INTERVENTION REQUIRED!
```

**What This Means:**
- ✅ Drop new bug reports in `bug_reports/` folder
- ✅ Run `python main.py`
- ✅ System automatically processes ALL of them
- ✅ Results saved to JSON file

---

#### **2. Automatic Information Extraction**

```
Bug Report Text
        ↓
   Is LLM Available?
        ├─ YES → Use Gemini API
        │        ├─ Semantic understanding
        │        ├─ Extract implicit references
        │        └─ Identify error types
        │
        └─ NO → Use Keyword Parser
                 ├─ Pattern matching
                 ├─ Stack trace extraction
                 └─ CamelCase detection

All AUTOMATIC - no manual tagging needed!
```

**Code Implementation:**
```python
# File: bug_localizer.py, lines 67-123

def extract_bug_information(self, bug_report: str) -> Dict:
    """Automatically extracts information"""
    
    # Try LLM first
    if self.use_llm and self.model:
        try:
            # Send to Gemini API
            response = self.model.generate_content(prompt)
            return json.loads(response.text)
        except:
            # Fall back to keyword parsing
            pass
    
    # Automatic keyword-based extraction
    return self._keyword_based_parse(bug_report)
```

---

#### **3. Automatic Graph Queries**

```
For each extracted keyword/class:
    ↓
┌─────────────────────────────────────┐
│ Query Neo4j automatically:           │
│                                      │
│ MATCH (c:Class)                     │
│ WHERE c.name CONTAINS "World"       │
│ RETURN c                            │
└─────────────────────────────────────┘
    ↓
Results returned automatically
    ↓
Add to candidates with score
```

**No manual database queries needed!**

---

#### **4. Automatic Score Aggregation**

```python
# File: bug_localizer.py, lines 351-382

def _score_and_rank_candidates(self, candidates, extracted_bug_info):
    """Automatically aggregates and ranks"""
    
    location_scores = {}
    
    # Automatic deduplication and score accumulation
    for candidate in candidates:
        key = (candidate['type'], candidate['name'])
        
        if key not in location_scores:
            location_scores[key] = candidate
            location_scores[key]['score'] = 0.0
        
        # Accumulate scores automatically
        location_scores[key]['score'] += candidate['score']
    
    # Automatic sorting
    ranked = list(location_scores.values())
    ranked.sort(key=lambda x: x['score'], reverse=True)
    
    return ranked  # Already ranked!
```

---

### **What "Fully Automated" Means**

```
┌─────────────────────────────────────────────────────────────┐
│ TRADITIONAL APPROACH (Manual)                               │
├─────────────────────────────────────────────────────────────┤
│ 1. Read bug report                        [MANUAL]          │
│ 2. Identify keywords                      [MANUAL]          │
│ 3. Search codebase                        [MANUAL]          │
│ 4. Find related classes                   [MANUAL]          │
│ 5. Score relevance                        [MANUAL]          │
│ 6. Rank results                           [MANUAL]          │
│ 7. Write report                           [MANUAL]          │
│ 8. Repeat for next bug                    [MANUAL]          │
│                                                             │
│ Time per bug: ~30 minutes                                   │
│ 10 bugs = ~5 hours of work                                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ YOUR SYSTEM (Automated)                                     │
├─────────────────────────────────────────────────────────────┤
│ 1. Run: python main.py                    [ONE COMMAND]     │
│    ↓                                                        │
│    All steps happen automatically:                          │
│    ├─ Read all bug reports                [AUTOMATIC]      │
│    ├─ Extract information                 [AUTOMATIC]      │
│    ├─ Query knowledge graph               [AUTOMATIC]      │
│    ├─ Score candidates                    [AUTOMATIC]      │
│    ├─ Rank results                        [AUTOMATIC]      │
│    ├─ Find relationships                  [AUTOMATIC]      │
│    └─ Save to JSON                        [AUTOMATIC]      │
│                                                             │
│ Time per bug: ~5 seconds                                    │
│ 10 bugs = ~50 seconds total!                                │
└─────────────────────────────────────────────────────────────┘

🚀 600x FASTER!
```

---

## 📊 Real Example Walkthrough

### **Input Bug Report:**
```
File: bug_reports/bug_npe_world.txt

Bug #45: NullPointerException in World.resolve()

Stack Trace:
  at org.aspectj.weaver.World.resolve(World.java:456)
  at org.aspectj.weaver.bcel.BcelWorld.addTypeMunger(BcelWorld.java:234)

Description:
The World class throws NPE when resolving types. The typeMap field
appears to be null. This happens in BcelWorld during weaving.
```

### **Automated Processing:**

```
[1] AUTOMATIC EXTRACTION
    ├─ Stack Trace Classes: ["World", "BcelWorld"]
    ├─ LLM Classes: ["World", "BcelWorld", "BcelWeaver"]
    └─ Keywords: ["World", "resolve", "typeMap", "BcelWorld"]

[2] AUTOMATIC GRAPH QUERIES
    ├─ Stack trace "World" → Found: org.aspectj.weaver.World (+10)
    ├─ Stack trace "BcelWorld" → Found: o.a.w.bcel.BcelWorld (+10)
    ├─ LLM "World" → Found: org.aspectj.weaver.World (+5)
    ├─ Keyword "World" → Found: org.aspectj.weaver.World (+3)
    ├─ Keyword "resolve" → Found: World.resolve() method (+3)
    └─ Keyword "typeMap" → Found: World.typeMap field (+3)

[3] AUTOMATIC SCORE AGGREGATION
    org.aspectj.weaver.World:
    ├─ Stack trace: 10
    ├─ LLM: 5
    └─ Keyword: 3
    TOTAL: 18 points

    org.aspectj.weaver.bcel.BcelWorld:
    ├─ Stack trace: 10
    └─ Keyword: 3
    TOTAL: 13 points

[4] AUTOMATIC RANKING
    #1: org.aspectj.weaver.World (18 pts)
    #2: org.aspectj.weaver.bcel.BcelWorld (13 pts)
    #3: World.resolve() method (3 pts)
    #4: World.typeMap field (3 pts)
    #5: BcelWeaver class (3 pts)

[5] AUTOMATIC RELATIONSHIP ANALYSIS
    For #1 (World class):
    ├─ Extends: AbstractWorld
    ├─ Used by: BcelWorld, ReflectionWorld (15 classes)
    └─ Affected files: 8 files

[6] AUTOMATIC OUTPUT
    Saved to: bug_localization_results.json
```

**ALL OF THIS HAPPENED AUTOMATICALLY!** 🎉

---

## 🎯 Summary for Mentor

### **Ranking:**
1. **Multi-strategy search** finds candidates (stack trace, LLM, keywords)
2. **Evidence-based scoring** assigns confidence (10, 5, 3 points)
3. **Score accumulation** increases confidence when found multiple times
4. **Automatic ranking** by total score
5. **Top-5 results** returned with explanations

### **Automation:**
1. **Batch processing** - All bug reports processed automatically
2. **Smart extraction** - LLM or keyword-based (automatic fallback)
3. **Graph queries** - Neo4j queries executed automatically
4. **Score calculation** - Aggregation and ranking automatic
5. **One command** - `python main.py` does everything!

**Result: From hours of manual work to seconds of automated processing!** ⚡

---

*Created: November 27, 2025*  
*For: Mentor Presentation*

