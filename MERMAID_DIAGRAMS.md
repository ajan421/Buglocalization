# Mermaid Diagrams for Bug Localization System

All diagrams can be rendered in:
- GitHub (paste in .md files)
- Mermaid Live Editor: https://mermaid.live/
- Documentation tools (GitBook, MkDocs, etc.)

---

## 1. Complete Pipeline Flow

```mermaid
flowchart TD
    Start([Start: python main.py]) --> Step1
    
    subgraph Step1[" STEP 1: PARSE SOURCE CODE "]
        A1[Load 8 AspectJ Modules] --> A2[Parse Java Files]
        A2 --> A3[Extract Classes]
        A2 --> A4[Extract Methods]
        A2 --> A5[Extract Fields]
        A3 --> A6[Extract Relationships]
        A4 --> A6
        A5 --> A6
        A6 --> A7[Save to code_structure.json]
    end
    
    Step1 --> Step2
    
    subgraph Step2[" STEP 2: BUILD KNOWLEDGE GRAPH "]
        B1[Load code_structure.json] --> B2[Connect to Neo4j]
        B2 --> B3[Clear Existing Data]
        B3 --> B4[Create Indexes]
        B4 --> B5[Create Nodes]
        B5 --> B51[Class Nodes]
        B5 --> B52[Method Nodes]
        B5 --> B53[Field Nodes]
        B5 --> B54[Package Nodes]
        B5 --> B55[File Nodes]
        B51 --> B6[Create Relationships]
        B52 --> B6
        B53 --> B6
        B54 --> B6
        B55 --> B6
        B6 --> B7[Graph Built: 12K+ Nodes, 45K+ Edges]
    end
    
    Step2 --> Step3
    
    subgraph Step3[" STEP 3: LOCALIZE BUGS "]
        C1[Load Bug Reports/*.txt] --> C2{For Each Bug}
        C2 --> C3[Extract Information]
        C3 --> C4[Search Knowledge Graph]
        C4 --> C5[Score Candidates]
        C5 --> C6[Rank by Score]
        C6 --> C7[Select Top-5]
        C7 --> C8[Enrich with Relationships]
        C8 --> C9{More Bugs?}
        C9 -->|Yes| C2
        C9 -->|No| C10[Save bug_localization_results.json]
    end
    
    Step3 --> End([Complete!])
    
    style Start fill:#4CAF50,stroke:#2E7D32,color:#fff
    style End fill:#4CAF50,stroke:#2E7D32,color:#fff
    style Step1 fill:#E3F2FD,stroke:#1976D2
    style Step2 fill:#FFF3E0,stroke:#F57C00
    style Step3 fill:#F3E5F5,stroke:#7B1FA2
```

---

## 2. Detailed Ranking Algorithm

```mermaid
flowchart TB
    Start([Bug Report Input]) --> Extract
    
    subgraph Extract[" INFORMATION EXTRACTION "]
        E1{LLM Available?}
        E1 -->|Yes| E2[Gemini API Analysis]
        E1 -->|No| E3[Keyword-Based Parser]
        E2 --> E4[Extracted Data]
        E3 --> E4
        E4 --> E5[Stack Trace Classes]
        E4 --> E6[LLM Classes]
        E4 --> E7[Keywords]
    end
    
    Extract --> Search
    
    subgraph Search[" MULTI-STRATEGY SEARCH "]
        S1[Strategy 1: Stack Trace<br/>Score: 10 points]
        S2[Strategy 2: LLM Classes<br/>Score: 5 points]
        S3[Strategy 3: Keywords<br/>Score: 3 points]
        
        S1 --> S4[(Neo4j<br/>Knowledge Graph)]
        S2 --> S4
        S3 --> S4
        
        S4 --> S5[Query Results]
    end
    
    Search --> Score
    
    subgraph Score[" SCORE AGGREGATION "]
        SC1[Collect All Candidates]
        SC2[Group by Location<br/>type, name]
        SC3[Sum Scores for Duplicates]
        SC4[Example: World class<br/>10 + 5 + 3 = 18 pts]
        
        SC1 --> SC2
        SC2 --> SC3
        SC3 --> SC4
    end
    
    Score --> Rank
    
    subgraph Rank[" RANKING "]
        R1[Sort by Score DESC]
        R2[Select Top-5]
        R3[#1: World 18pts]
        R4[#2: BcelWorld 13pts]
        R5[#3: resolve 3pts]
        R6[#4: TypeMap 3pts]
        R7[#5: BcelWeaver 3pts]
        
        R1 --> R2
        R2 --> R3
        R2 --> R4
        R2 --> R5
        R2 --> R6
        R2 --> R7
    end
    
    Rank --> End([Top-5 Results])
    
    style Start fill:#4CAF50,stroke:#2E7D32,color:#fff
    style End fill:#4CAF50,stroke:#2E7D32,color:#fff
    style Extract fill:#E3F2FD,stroke:#1976D2
    style Search fill:#FFF3E0,stroke:#F57C00
    style Score fill:#F3E5F5,stroke:#7B1FA2
    style Rank fill:#E8F5E9,stroke:#388E3C
```

---

## 3. Scoring System Details

```mermaid
graph LR
    Bug[Bug Report: NPE at World.resolve] --> Strategies
    
    subgraph Strategies[" SEARCH STRATEGIES "]
        S1[Stack Trace Search<br/>🔴 Score: 10]
        S2[LLM Analysis<br/>🟡 Score: 5]
        S3[Keyword Match<br/>🟢 Score: 3]
    end
    
    S1 --> |Found: World| L1[org.aspectj.weaver.World]
    S2 --> |Found: World| L1
    S3 --> |Found: World| L1
    
    S1 --> |Found: BcelWorld| L2[org.aspectj.weaver.bcel.BcelWorld]
    S3 --> |Found: BcelWorld| L2
    
    S3 --> |Found: resolve| L3[World.resolve method]
    
    L1 --> Score1[Total: 10 + 5 + 3 = 18 pts<br/>🥇 RANK #1]
    L2 --> Score2[Total: 10 + 3 = 13 pts<br/>🥈 RANK #2]
    L3 --> Score3[Total: 3 pts<br/>🥉 RANK #3]
    
    Score1 --> Result
    Score2 --> Result
    Score3 --> Result
    
    Result[Top-5 Results]
    
    style Bug fill:#FFEBEE,stroke:#C62828
    style S1 fill:#FFCDD2,stroke:#C62828
    style S2 fill:#FFF9C4,stroke:#F57F17
    style S3 fill:#C8E6C9,stroke:#388E3C
    style Score1 fill:#FFD700,stroke:#FF8F00,color:#000
    style Score2 fill:#C0C0C0,stroke:#616161,color:#000
    style Score3 fill:#CD7F32,stroke:#5D4037,color:#fff
```

---

## 4. Knowledge Graph Schema

```mermaid
graph TB
    subgraph Nodes[" NODE TYPES "]
        N1[Class<br/>full_name, type, modifiers]
        N2[Method<br/>signature, return_type]
        N3[Field<br/>id, type, modifiers]
        N4[Package<br/>name]
        N5[File<br/>path]
    end
    
    N1 -->|DEFINED_IN| N5
    N1 -->|BELONGS_TO| N4
    N1 -->|EXTENDS| N1
    N1 -->|IMPLEMENTS| N1
    N1 -->|HAS_METHOD| N2
    N1 -->|HAS_FIELD| N3
    
    style N1 fill:#E3F2FD,stroke:#1976D2
    style N2 fill:#F3E5F5,stroke:#7B1FA2
    style N3 fill:#FFF3E0,stroke:#F57C00
    style N4 fill:#E8F5E9,stroke:#388E3C
    style N5 fill:#FCE4EC,stroke:#C2185B
```

---

## 5. Automation Flow

```mermaid
sequenceDiagram
    actor User
    participant Main as main.py
    participant Parser as code_parser.py
    participant Neo4j as Neo4j Database
    participant Localizer as bug_localizer.py
    participant LLM as Gemini API
    
    User->>Main: python main.py
    
    rect rgb(227, 242, 253)
        Note over Main,Parser: STEP 1: Parse Code
        Main->>Parser: Parse AspectJ modules
        Parser->>Parser: Scan .java files
        Parser->>Parser: Extract classes, methods, fields
        Parser-->>Main: code_structure.json
    end
    
    rect rgb(255, 243, 224)
        Note over Main,Neo4j: STEP 2: Build Graph
        Main->>Neo4j: Connect
        Main->>Neo4j: Clear existing data
        Main->>Neo4j: Create indexes
        Main->>Neo4j: Load code structure
        Neo4j-->>Main: Graph built (12K nodes)
    end
    
    rect rgb(243, 229, 245)
        Note over Main,LLM: STEP 3: Localize Bugs
        Main->>Localizer: Process bug_reports/*.txt
        
        loop For each bug report
            Localizer->>Localizer: Read bug file
            Localizer->>LLM: Extract information
            LLM-->>Localizer: Extracted data
            Localizer->>Neo4j: Query for candidates
            Neo4j-->>Localizer: Candidate locations
            Localizer->>Localizer: Score & rank
            Localizer->>Neo4j: Get relationships
            Neo4j-->>Localizer: Relationship data
        end
        
        Localizer-->>Main: All results
        Main->>Main: Save bug_localization_results.json
    end
    
    Main-->>User: ✅ Complete!
```

---

## 6. Bug Report Processing Detail

```mermaid
flowchart TD
    Start[Bug Report File] --> Read[Read File Content]
    
    Read --> Extract{Extract Method}
    
    Extract -->|LLM Available| LLM[Gemini API]
    Extract -->|Fallback| Keyword[Keyword Parser]
    
    LLM --> Parse[Parse Stack Traces]
    Keyword --> Parse
    
    Parse --> Data[Extracted Data:<br/>- Stack trace classes<br/>- LLM classes<br/>- Keywords<br/>- Potential methods]
    
    Data --> Q1[Query 1: Stack Traces<br/>Score: 10 pts]
    Data --> Q2[Query 2: LLM Classes<br/>Score: 5 pts]
    Data --> Q3[Query 3: Keywords<br/>Score: 3 pts]
    
    Q1 --> Graph[(Neo4j<br/>Knowledge<br/>Graph)]
    Q2 --> Graph
    Q3 --> Graph
    
    Graph --> Candidates[Candidate Locations]
    
    Candidates --> Agg[Aggregate Scores<br/>Same location = Sum scores]
    
    Agg --> Sort[Sort by Score DESC]
    
    Sort --> Top5[Select Top-5]
    
    Top5 --> Enrich[Enrich with:<br/>- Extends/Implements<br/>- Used by<br/>- Affected files]
    
    Enrich --> Result[Top-5 Results with<br/>Scores & Relationships]
    
    style Start fill:#FFEBEE,stroke:#C62828
    style LLM fill:#E3F2FD,stroke:#1976D2
    style Keyword fill:#FFF3E0,stroke:#F57C00
    style Graph fill:#E8F5E9,stroke:#388E3C
    style Result fill:#4CAF50,stroke:#2E7D32,color:#fff
```

---

## 7. System Architecture

```mermaid
graph TB
    subgraph Input[" INPUT LAYER "]
        I1[AspectJ Source Code<br/>8 modules]
        I2[Bug Reports<br/>*.txt files]
    end
    
    subgraph Processing[" PROCESSING LAYER "]
        P1[Code Parser<br/>javalang + regex]
        P2[Bug Localizer<br/>LLM + keyword]
    end
    
    subgraph Storage[" STORAGE LAYER "]
        S1[(Neo4j<br/>Knowledge Graph)]
        S2[code_structure.json]
        S3[bug_localization_results.json]
    end
    
    subgraph External[" EXTERNAL SERVICES "]
        E1[Google Gemini API<br/>Optional]
    end
    
    I1 --> P1
    P1 --> S2
    S2 --> S1
    
    I2 --> P2
    P2 --> E1
    P2 --> S1
    P2 --> S3
    
    style Input fill:#E3F2FD,stroke:#1976D2
    style Processing fill:#FFF3E0,stroke:#F57C00
    style Storage fill:#E8F5E9,stroke:#388E3C
    style External fill:#F3E5F5,stroke:#7B1FA2
```

---

## 8. Top-5 Ranking Visualization

```mermaid
graph LR
    Start[All Candidates<br/>47 locations] --> Dedupe[Deduplicate by<br/>type + name]
    
    Dedupe --> Score[Aggregate Scores<br/>23 unique locations]
    
    Score --> Sort[Sort by Score]
    
    Sort --> R1[#1: World<br/>⭐ 18 points]
    Sort --> R2[#2: BcelWorld<br/>⭐ 13 points]
    Sort --> R3[#3: World.resolve<br/>⭐ 3 points]
    Sort --> R4[#4: TypeMap<br/>⭐ 3 points]
    Sort --> R5[#5: BcelWeaver<br/>⭐ 3 points]
    Sort --> R6[#6: Shadow<br/>⭐ 3 points]
    Sort --> R7[...]
    
    R1 --> Top5[Top-5 Results]
    R2 --> Top5
    R3 --> Top5
    R4 --> Top5
    R5 --> Top5
    
    style Start fill:#E3F2FD,stroke:#1976D2
    style R1 fill:#FFD700,stroke:#FF8F00,color:#000
    style R2 fill:#C0C0C0,stroke:#616161,color:#000
    style R3 fill:#CD7F32,stroke:#5D4037,color:#fff
    style R4 fill:#E0E0E0,stroke:#757575
    style R5 fill:#E0E0E0,stroke:#757575
    style Top5 fill:#4CAF50,stroke:#2E7D32,color:#fff
```

---

## 9. Configuration Flow

```mermaid
flowchart TD
    Config[Configuration<br/>in main.py] --> C1{num_top_locations}
    
    C1 -->|Set to 3| Top3[Return Top-3]
    C1 -->|Set to 5| Top5[Return Top-5]
    C1 -->|Set to 10| Top10[Return Top-10]
    
    Config --> C2{use_llm}
    
    C2 -->|True| LLM[Use Gemini API<br/>Semantic Analysis]
    C2 -->|False| KW[Keyword Matching<br/>Pattern-Based]
    
    Config --> C3[source_dirs]
    C3 --> Modules[Parse Selected<br/>AspectJ Modules]
    
    Top3 --> Results[Localization Results]
    Top5 --> Results
    Top10 --> Results
    LLM --> Results
    KW --> Results
    Modules --> Results
    
    style Config fill:#FFF3E0,stroke:#F57C00
    style Results fill:#4CAF50,stroke:#2E7D32,color:#fff
```

---

## 10. Real-Time Execution Flow

```mermaid
gantt
    title Bug Localization Pipeline Timeline
    dateFormat ss
    axisFormat %S sec
    
    section Step 1
    Load source dirs        :a1, 00, 5s
    Parse Java files        :a2, after a1, 20s
    Save code_structure.json:a3, after a2, 5s
    
    section Step 2
    Connect to Neo4j        :b1, after a3, 2s
    Clear & create indexes  :b2, after b1, 3s
    Load code structure     :b3, after b2, 5s
    
    section Step 3
    Load bug reports        :c1, after b3, 1s
    Process bug 1           :c2, after c1, 5s
    Process bug 2           :c3, after c2, 5s
    Process bug 3           :c4, after c3, 5s
    Save results            :c5, after c4, 2s
```

---

## How to Use These Diagrams

### 1. **In GitHub/GitLab**
Simply paste the code blocks in your `.md` files. They will render automatically.

### 2. **Mermaid Live Editor**
1. Go to https://mermaid.live/
2. Paste any diagram code
3. Export as PNG/SVG for presentations

### 3. **PowerPoint/Presentations**
1. Use Mermaid Live Editor to export as PNG
2. Insert images in your slides

### 4. **Documentation Tools**
Most modern documentation tools (MkDocs, Docusaurus, GitBook) support Mermaid natively.

### 5. **VS Code**
Install "Markdown Preview Mermaid Support" extension to preview in VS Code.

---

## Customization Tips

### Change Colors
```mermaid
style NodeName fill:#HEX,stroke:#HEX,color:#HEX
```

### Change Flow Direction
- `TB` = Top to Bottom
- `LR` = Left to Right
- `BT` = Bottom to Top
- `RL` = Right to Left

### Add Icons
Use emoji in node text:
```mermaid
graph LR
    A[📊 Data] --> B[🔍 Analysis]
```

---

*Created for Bug Localization System v2.0*  
*All diagrams are MIT Licensed - use freely in presentations*

