"""
Bug Localization System using Multi-Agent Architecture (Phase 2)

Ranking Algorithm: BM25 (Robertson & Zaragoza, 2009) combined with:
- Stack trace evidence
- LLM-based semantic analysis
- Knowledge graph relationships
- Pattern Detection Agent (Phase 2)
- Test Failure Agent (Phase 2)
- Bug Type Classifier (Phase 2)
- Judge Agent for score fusion (Phase 2)

Evaluation Metrics: Top-K Accuracy, MAP, MRR (standard IR metrics)
"""

import os
import json
import time
import re
import math
import requests
from typing import List, Dict, Tuple
from collections import Counter
from neo4j_loader import Neo4jKnowledgeGraph
import google.generativeai as genai
from pathlib import Path
from dotenv import load_dotenv

# Phase 2 Agents
from agents import BugTypeClassifier, PatternDetectionAgent, TestFailureAgent, JudgeAgent
from agents import BugLocalizationGraph

load_dotenv()

# Configuration
LMSTUDIO_URL = "http://localhost:1234/v1/chat/completions"
GEMINI_DELAY = 1.0
MAX_RETRIES = 3
INITIAL_BACKOFF = 10.0

# BM25 Parameters (standard values from literature)
BM25_K1 = 1.2  # Term frequency saturation
BM25_B = 0.75  # Document length normalization

# Score weights for combined ranking
W_BM25 = 0.4           # Text similarity weight
W_STACK_TRACE = 0.3    # Stack trace evidence weight
W_SEMANTIC = 0.2       # LLM semantic analysis weight
W_STRUCTURE = 0.1      # Code structure weight


class BM25Ranker:
    """
    BM25 (Best Match 25) ranking algorithm for bug localization.
    
    Reference: Robertson & Zaragoza, "The Probabilistic Relevance Framework: 
               BM25 and Beyond" (2009)
    
    Formula:
    Score(D,Q) = Σ IDF(qi) × [f(qi,D) × (k1 + 1)] / [f(qi,D) + k1 × (1 - b + b × |D|/avgdl)]
    """
    
    def __init__(self, k1: float = BM25_K1, b: float = BM25_B):
        self.k1 = k1
        self.b = b
        self.doc_freqs = {}      # term -> number of docs containing term
        self.doc_lens = {}       # doc_id -> document length
        self.avgdl = 0           # average document length
        self.N = 0               # total number of documents
        self.doc_terms = {}      # doc_id -> Counter of term frequencies
        self.doc_metadata = {}   # doc_id -> {class_name, file_path, etc}
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text with camelCase and snake_case splitting"""
        # Split camelCase: 'MyClassName' -> 'My Class Name'
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
        text = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', text)
        # Split snake_case
        text = text.replace('_', ' ').lower()
        # Extract words (min 2 chars)
        return [w for w in re.findall(r'\w+', text) if len(w) >= 2]
    
    def fit(self, documents: Dict[str, Dict]):
        """
        Index code documents for BM25 ranking.
        
        Args:
            documents: {doc_id: {'text': content, 'class_name': name, 'file_path': path}}
        """
        self.N = len(documents)
        total_len = 0
        
        for doc_id, doc_info in documents.items():
            text = doc_info.get('text', '')
            terms = self._tokenize(text)
            
            self.doc_terms[doc_id] = Counter(terms)
            self.doc_lens[doc_id] = len(terms)
            self.doc_metadata[doc_id] = {
                'class_name': doc_info.get('class_name', doc_id),
                'file_path': doc_info.get('file_path', ''),
                'methods': doc_info.get('methods', [])
            }
            total_len += len(terms)
            
            # Count document frequencies
            for term in set(terms):
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1
        
        self.avgdl = total_len / self.N if self.N > 0 else 0
    
    def _idf(self, term: str) -> float:
        """Calculate Inverse Document Frequency"""
        df = self.doc_freqs.get(term, 0)
        if df == 0:
            return 0
        # BM25 IDF formula
        return math.log((self.N - df + 0.5) / (df + 0.5) + 1)
    
    def score(self, query: str, doc_id: str) -> float:
        """Calculate BM25 score for a single document"""
        query_terms = self._tokenize(query)
        doc_term_freqs = self.doc_terms.get(doc_id, {})
        doc_len = self.doc_lens.get(doc_id, 0)
        
        if doc_len == 0:
            return 0.0
        
        score = 0.0
        for term in query_terms:
            if term not in doc_term_freqs:
                continue
            
            tf = doc_term_freqs[term]
            idf = self._idf(term)
            
            # BM25 formula
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
            score += idf * (numerator / denominator)
        
        return score
    
    def rank(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Rank all documents for a query.
        
        Returns:
            List of (doc_id, score) tuples sorted by score descending
        """
        scores = []
        for doc_id in self.doc_terms:
            s = self.score(query, doc_id)
            if s > 0:
                scores.append((doc_id, s))
        
        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]


class TopKEvaluator:
    """
    Standard IR evaluation metrics for bug localization.
    
    Metrics:
    - Top-K Accuracy: Percentage of bugs with correct file in top K results
    - MAP (Mean Average Precision): Overall ranking quality
    - MRR (Mean Reciprocal Rank): Position of first correct result
    """
    
    @staticmethod
    def top_k_accuracy(results: List[Dict], ground_truth: Dict, k: int) -> float:
        """
        Calculate Top-K accuracy.
        
        Args:
            results: List of {bug_id, ranked_files: [{file_path, ...}]}
            ground_truth: {bug_id: [actual_buggy_files]}
            k: Number of top results to consider
        
        Returns:
            Percentage of bugs with at least one correct file in top K
        """
        hits = 0
        total = 0
        
        for result in results:
            bug_id = result.get('bug_id', '')
            if bug_id not in ground_truth:
                continue
            
            total += 1
            predicted = [r.get('file_path', '') for r in result.get('top_locations', [])[:k]]
            actual = set(ground_truth[bug_id])
            
            if any(p in actual or Path(p).name in actual for p in predicted):
                hits += 1
        
        return (hits / total * 100) if total > 0 else 0.0
    
    @staticmethod
    def mrr(results: List[Dict], ground_truth: Dict) -> float:
        """
        Calculate Mean Reciprocal Rank.
        
        MRR = (1/|Q|) × Σ (1/rank_i)
        """
        rr_sum = 0.0
        total = 0
        
        for result in results:
            bug_id = result.get('bug_id', '')
            if bug_id not in ground_truth:
                continue
            
            total += 1
            predicted = [r.get('file_path', '') for r in result.get('top_locations', [])]
            actual = set(ground_truth[bug_id])
            
            for rank, pred in enumerate(predicted, 1):
                if pred in actual or Path(pred).name in actual:
                    rr_sum += 1.0 / rank
                    break
        
        return rr_sum / total if total > 0 else 0.0
    
    @staticmethod
    def mean_average_precision(results: List[Dict], ground_truth: Dict) -> float:
        """
        Calculate Mean Average Precision.
        
        MAP = (1/|Q|) × Σ AP(q)
        AP(q) = (1/|relevant|) × Σ (P@k × rel(k))
        """
        ap_sum = 0.0
        total = 0
        
        for result in results:
            bug_id = result.get('bug_id', '')
            if bug_id not in ground_truth:
                continue
            
            total += 1
            predicted = [r.get('file_path', '') for r in result.get('top_locations', [])]
            actual = set(ground_truth[bug_id])
            
            hits = 0
            precision_sum = 0.0
            
            for rank, pred in enumerate(predicted, 1):
                if pred in actual or Path(pred).name in actual:
                    hits += 1
                    precision_sum += hits / rank
            
            if len(actual) > 0:
                ap_sum += precision_sum / len(actual)
        
        return ap_sum / total if total > 0 else 0.0
    
    @staticmethod
    def evaluate_all(results: List[Dict], ground_truth: Dict) -> Dict:
        """Calculate all metrics at once"""
        return {
            'top_1': TopKEvaluator.top_k_accuracy(results, ground_truth, 1),
            'top_5': TopKEvaluator.top_k_accuracy(results, ground_truth, 5),
            'top_10': TopKEvaluator.top_k_accuracy(results, ground_truth, 10),
            'mrr': TopKEvaluator.mrr(results, ground_truth),
            'map': TopKEvaluator.mean_average_precision(results, ground_truth)
        }


class BugLocalizer:
    """
    Bug Localization using Multi-Agent Architecture (Phase 2).
    
    Algorithm:
        1. Bug Type Classifier classifies the bug and sets dynamic weights
        2. Pattern Detection Agent analyzes code patterns
        3. Test Failure Agent analyzes test coverage relationships
        4. Judge Agent fuses all signals with consensus checking
        
        Final_Score = Judge(StackTrace, BM25, Pattern, Test) with dynamic weights
    """
    
    def __init__(self, knowledge_graph: Neo4jKnowledgeGraph, use_llm: bool = True, 
                 llm_provider: str = "auto", use_agents: bool = True, use_langgraph: bool = True):
        self.knowledge_graph = knowledge_graph
        self.use_llm = use_llm
        self.use_agents = use_agents
        self.use_langgraph = use_langgraph
        self.model = None
        self.llm_provider = None
        self.last_api_call = 0
        self.bm25 = BM25Ranker()
        self._index_built = False
        
        # Phase 2: Initialize Agents
        self.bug_classifier = BugTypeClassifier()
        self.pattern_agent = PatternDetectionAgent()
        self.test_agent = TestFailureAgent()
        self.judge_agent = JudgeAgent()
        
        # LangGraph Orchestrator
        self.langgraph_orchestrator = None
        
        if use_agents:
            print("[+] Phase 2 Agents initialized:")
            print("    - Bug Type Classifier")
            print("    - Pattern Detection Agent")
            print("    - Test Failure Agent")
            print("    - Judge Agent")
            if use_langgraph:
                print("    - LangGraph Orchestrator (enabled)")
        
        if not use_llm or llm_provider == "keyword":
            print("[+] Using keyword-based matching")
            self.use_llm = False
            return
        
        if llm_provider in ["auto", "lmstudio"]:
            if self._check_lmstudio():
                self.llm_provider = "lmstudio"
                print("[+] LM Studio connected")
                return
            elif llm_provider == "lmstudio":
                print("[-] LM Studio not available at localhost:1234")
                self.use_llm = False
                return
        
        if llm_provider in ["auto", "gemini"]:
            api_key = os.getenv('GEMINI_API_KEY')
            if api_key:
                try:
                    genai.configure(api_key=api_key)
                    self.model = genai.GenerativeModel('gemini-1.5-flash')
                    self.llm_provider = "gemini"
                    print("[+] Gemini API configured")
                    return
                except Exception as e:
                    print(f"[-] Gemini error: {e}")
        
        print("[*] No LLM available, using keyword matching")
        self.use_llm = False
    
    def _init_langgraph(self):
        """Initialize LangGraph orchestrator with BM25 index"""
        if self.langgraph_orchestrator is None and self.use_langgraph:
            self.langgraph_orchestrator = BugLocalizationGraph(
                knowledge_graph=self.knowledge_graph,
                bm25_ranker=self.bm25
            )
            print("[+] LangGraph Orchestrator ready")
    
    def build_bm25_index(self):
        """Build BM25 index from knowledge graph classes"""
        if self._index_built:
            return
        
        print("[*] Building BM25 index...")
        documents = {}
        
        # Get all classes from knowledge graph
        query = """
        MATCH (c:Class)
        OPTIONAL MATCH (c)-[:HAS_METHOD]->(m:Method)
        RETURN c.name as class_name, c.full_name as full_name, 
               c.file_path as file_path, collect(m.name) as methods
        """
        
        with self.knowledge_graph.driver.session() as session:
            results = session.run(query)
            for record in results:
                class_name = record['class_name'] or ''
                full_name = record['full_name'] or class_name
                file_path = record['file_path'] or ''
                methods = [m for m in (record['methods'] or []) if m]
                
                if not class_name:
                    continue
                
                # Create document text from class name and methods
                doc_text = f"{class_name} {full_name} {' '.join(methods)}"
                
                documents[full_name] = {
                    'text': doc_text,
                    'class_name': class_name,
                    'file_path': file_path,
                    'methods': methods
                }
        
        self.bm25.fit(documents)
        self._index_built = True
        print(f"[+] Indexed {len(documents)} classes for BM25")
    
    def _check_lmstudio(self) -> bool:
        try:
            response = requests.get("http://localhost:1234/v1/models", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def _call_lmstudio(self, prompt: str) -> str:
        payload = {
            "model": "local-model",
            "messages": [
                {"role": "system", "content": "You are a bug report analyzer. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1000
        }
        response = requests.post(LMSTUDIO_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    
    def _rate_limit(self):
        elapsed = time.time() - self.last_api_call
        if elapsed < GEMINI_DELAY:
            time.sleep(GEMINI_DELAY - elapsed)
        self.last_api_call = time.time()
    
    def extract_bug_information(self, bug_report: str) -> Dict:
        # Always run keyword extraction first
        keyword_result = self._keyword_parse(bug_report)
        
        if not self.use_llm:
            keyword_result['source'] = 'keyword'
            return keyword_result
        
        # Run LLM extraction
        llm_result = self._llm_extract(bug_report)
        
        if not llm_result:
            keyword_result['source'] = 'keyword'
            return keyword_result
        
        # Merge both results for higher accuracy
        merged = self._merge_results(keyword_result, llm_result)
        merged['source'] = 'hybrid'
        return merged
    
    def _llm_extract(self, bug_report: str) -> Dict:
        prompt = f"""Extract key information from this bug report and return ONLY a JSON object:
- summary: Brief summary
- error_type: Type of error
- keywords: List of technical keywords
- potential_classes: List of class names that might be related
- potential_methods: List of method names that might be related
- stack_trace_classes: Classes from stack trace

Bug Report:
{bug_report}

Return only JSON:"""
        
        if self.llm_provider == "lmstudio":
            try:
                result = self._call_lmstudio(prompt)
                return self._parse_json(result)
            except Exception as e:
                print(f"[*] LM Studio error: {str(e)[:80]}")
                return None
        
        if self.llm_provider == "gemini" and self.model:
            for attempt in range(MAX_RETRIES):
                try:
                    self._rate_limit()
                    response = self.model.generate_content(prompt)
                    return self._parse_json(response.text)
                except Exception as e:
                    err = str(e)
                    if "429" in err or "quota" in err.lower() or "rate" in err.lower():
                        if attempt < MAX_RETRIES - 1:
                            wait = INITIAL_BACKOFF * (2 ** attempt)
                            print(f"[*] Rate limit, retrying in {wait:.0f}s...")
                            time.sleep(wait)
                            continue
                        print("[*] Rate limit exceeded")
                        self.use_llm = False
                    return None
        return None
    
    def _merge_results(self, keyword_result: Dict, llm_result: Dict) -> Dict:
        # Combine and dedupe, tracking what came from where
        kw_classes = set(keyword_result.get('potential_classes', []))
        llm_classes = set(llm_result.get('potential_classes', []))
        
        kw_methods = set(keyword_result.get('potential_methods', []))
        llm_methods = set(llm_result.get('potential_methods', []))
        
        kw_keywords = set(keyword_result.get('keywords', []))
        llm_keywords = set(llm_result.get('keywords', []))
        
        # Items found by both get marked for higher scoring
        both_classes = kw_classes & llm_classes
        both_methods = kw_methods & llm_methods
        
        # Merge all unique items
        all_classes = list(kw_classes | llm_classes)
        all_methods = list(kw_methods | llm_methods)
        all_keywords = list(kw_keywords | llm_keywords)
        
        # Combine stack traces (keyword parser is better at this)
        stack_traces = list(set(
            keyword_result.get('stack_trace_classes', []) + 
            llm_result.get('stack_trace_classes', [])
        ))
        
        return {
            'summary': llm_result.get('summary') or keyword_result.get('summary', ''),
            'error_type': llm_result.get('error_type') or keyword_result.get('error_type', 'Unknown'),
            'keywords': all_keywords[:20],
            'potential_classes': all_classes[:20],
            'potential_methods': all_methods[:15],
            'stack_trace_classes': stack_traces,
            'both_classes': list(both_classes),  # Classes found by both (higher confidence)
            'both_methods': list(both_methods)   # Methods found by both (higher confidence)
        }
    
    def _parse_json(self, result: str) -> Dict:
        result = result.strip()
        try:
            if result.startswith('```'):
                result = result.split('```')[1]
                if result.startswith('json'):
                    result = result[4:]
                result = result.strip()
            return json.loads(result)
        except:
            return None
    
    def _keyword_parse(self, bug_report: str) -> Dict:
        lines = bug_report.split('\n')
        text_lower = bug_report.lower()
        
        keywords = []
        potential_classes = []
        potential_methods = []
        
        class_patterns = ['Pattern', 'Type', 'Weaver', 'World', 'Shadow', 'Munger', 
                         'Resolver', 'Binding', 'Handler', 'Manager', 'Factory', 
                         'Builder', 'Service', 'Exception', 'Error', 'Aspect',
                         'Annotation', 'Match', 'Join', 'Point']
        
        for word in bug_report.split():
            cleaned = word.strip('.,():;[]{}"\'-')
            if not cleaned:
                continue
            
            if cleaned[0].isupper() and any(c.islower() for c in cleaned):
                keywords.append(cleaned)
                if len(cleaned) > 3 and cleaned.isalnum():
                    if any(p in cleaned for p in class_patterns):
                        potential_classes.append(cleaned)
                    elif re.match(r'^[A-Z][a-z]+([A-Z][a-z]+)+$', cleaned):
                        potential_classes.append(cleaned)
            
            if cleaned[0].islower() and any(c.isupper() for c in cleaned) and cleaned.isalnum():
                if len(cleaned) > 4:
                    potential_methods.append(cleaned)
        
        fqcn_pattern = r'([a-z][a-z0-9_]*\.)+[A-Z][a-zA-Z0-9]*'
        for match in re.finditer(fqcn_pattern, bug_report):
            class_name = match.group(0).rsplit('.', 1)[-1]
            if class_name not in potential_classes:
                potential_classes.append(class_name)
        
        stack_trace_classes = []
        for line in lines:
            if 'at ' in line and '(' in line:
                parts = line.split('at ')
                if len(parts) > 1:
                    class_part = parts[1].split('(')[0].strip()
                    if '.' in class_part:
                        full_class = class_part.rsplit('.', 1)[0]
                        stack_trace_classes.append(full_class)
                        simple = full_class.rsplit('.', 1)[-1]
                        if simple not in potential_classes:
                            potential_classes.append(simple)
        
        error_type = 'Unknown'
        if 'nullpointerexception' in text_lower or 'npe' in text_lower:
            error_type = 'NullPointerException'
        elif 'classcastexception' in text_lower:
            error_type = 'ClassCastException'
        elif 'compilation' in text_lower or 'compile' in text_lower:
            error_type = 'CompilationError'
        elif 'weaving' in text_lower or 'weave' in text_lower:
            error_type = 'WeavingError'
        
        summary = ''
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('at ') and len(stripped) > 10:
                summary = stripped[:200]
                break
        
        return {
            'summary': summary or (lines[0] if lines else ''),
            'error_type': error_type,
            'keywords': list(set(keywords))[:20],
            'potential_classes': list(set(potential_classes))[:15],
            'potential_methods': list(set(potential_methods))[:10],
            'stack_trace_classes': list(set(stack_trace_classes))
        }
    
    def identify_buggy_locations(self, bug_report: str, num_top_locations: int = 10) -> List[Dict]:
        """
        Identify suspicious code locations using Multi-Agent Architecture.
        
        Phase 2 Algorithm (with LangGraph):
            1. LangGraph orchestrates the agent workflow
            2. Bug Type Classifier: Classify bug and get dynamic weights
            3. BM25 Agent: Calculate text similarity scores
            4. Pattern Detection Agent: Analyze code patterns
            5. Test Failure Agent: Analyze test relationships
            6. Judge Agent: Fuse all scores with consensus checking
            7. Return Top-K ranked results
        
        Args:
            bug_report: The bug report text
            num_top_locations: K value for Top-K results (default 10)
            
        Returns:
            List of top K suspicious locations with scores and explanations
        """
        print("\n" + "="*70)
        if self.use_langgraph:
            print("BUG LOCALIZATION - LANGGRAPH MULTI-AGENT SYSTEM")
        else:
            print("BUG LOCALIZATION - MULTI-AGENT SYSTEM (Phase 2)")
        print("="*70)
        
        # Build BM25 index if not already built
        self.build_bm25_index()
        
        # Initialize LangGraph if enabled
        if self.use_langgraph:
            self._init_langgraph()
            return self._localize_with_langgraph(bug_report, num_top_locations)
        
        # ===== STEP 1: Extract Bug Information =====
        print("\n[1/7] Extracting bug information...")
        info = self.extract_bug_information(bug_report)
        source = info.get('source', 'keyword')
        print(f"      Mode: {source}")
        print(f"      Keywords: {', '.join(info.get('keywords', [])[:5])}")
        
        # ===== STEP 2: Bug Type Classification =====
        print("\n[2/7] Bug Type Classifier Agent...")
        classification = self.bug_classifier.classify(bug_report)
        bug_type = classification.bug_type
        confidence = classification.confidence
        dynamic_weights = classification.weights
        
        print(f"      Bug Type: {bug_type} (confidence: {confidence:.2f})")
        print(f"      Indicators: {', '.join(classification.indicators[:3])}")
        
        # Update Judge Agent with dynamic weights
        if self.use_agents:
            self.judge_agent.set_weights(dynamic_weights)
            print(f"      Dynamic Weights: ST={dynamic_weights['stack_trace']:.2f}, "
                  f"BM25={dynamic_weights['bm25']:.2f}, "
                  f"Pattern={dynamic_weights['pattern']:.2f}, "
                  f"Test={dynamic_weights['test']:.2f}")
        
        # Get stack trace classes
        stack_trace_classes = set()
        for st in info.get('stack_trace_classes', []):
            stack_trace_classes.add(st.split('.')[-1])
        
        # Get LLM-identified classes
        llm_classes = set(info.get('potential_classes', []))
        both_classes = set(info.get('both_classes', []))
        
        # ===== STEP 3: BM25 Scoring =====
        print("\n[3/7] BM25 Agent: Computing text similarity...")
        query = f"{info.get('summary', '')} {' '.join(info.get('keywords', []))} {' '.join(info.get('potential_classes', []))}"
        bm25_results = self.bm25.rank(query, top_k=100)
        print(f"      Candidates found: {len(bm25_results)}")
        
        # Normalize BM25 scores to [0, 1]
        max_bm25 = max([s for _, s in bm25_results]) if bm25_results else 1.0
        
        # Build candidate list
        candidate_names = []
        bm25_scores = {}
        stack_trace_scores = {}
        
        for doc_id, bm25_score in bm25_results:
            metadata = self.bm25.doc_metadata.get(doc_id, {})
            class_name = metadata.get('class_name', doc_id)
            
            candidate_names.append(doc_id)
            bm25_scores[doc_id] = bm25_score / max_bm25 if max_bm25 > 0 else 0
            stack_trace_scores[doc_id] = 1.0 if class_name in stack_trace_classes else 0.0
        
        # Also add stack trace classes not in BM25 results
        for class_name in stack_trace_classes:
            for r in self.knowledge_graph.query_classes_by_name(class_name):
                if r['full_name'] not in candidate_names:
                    candidate_names.append(r['full_name'])
                    bm25_scores[r['full_name']] = 0.0
                    stack_trace_scores[r['full_name']] = 1.0
        
        print(f"\n[4/7] Stack Trace Analysis...")
        st_count = sum(1 for s in stack_trace_scores.values() if s > 0)
        print(f"      Classes in stack trace: {st_count}")
        
        # ===== STEP 5: Pattern Detection Agent =====
        print("\n[5/7] Pattern Detection Agent: Analyzing code patterns...")
        if self.use_agents:
            pattern_scores = self.pattern_agent.get_pattern_scores(candidate_names, bug_type)
            pattern_count = sum(1 for s in pattern_scores.values() if s > 0)
            print(f"      Patterns detected in: {pattern_count} classes")
        else:
            pattern_scores = {name: 0.0 for name in candidate_names}
        
        # ===== STEP 6: Test Failure Agent =====
        print("\n[6/7] Test Failure Agent: Analyzing test relationships...")
        if self.use_agents:
            test_scores = self.test_agent.get_test_scores(candidate_names, bug_report)
            test_count = sum(1 for s in test_scores.values() if s > 0)
            print(f"      Test relationships found: {test_count} classes")
        else:
            test_scores = {name: 0.0 for name in candidate_names}
        
        # ===== STEP 7: Judge Agent - Score Fusion =====
        print("\n[7/7] Judge Agent: Fusing scores with consensus check...")
        
        if self.use_agents:
            judgment = self.judge_agent.judge(
                candidates=candidate_names,
                stack_trace_scores=stack_trace_scores,
                bm25_scores=bm25_scores,
                pattern_scores=pattern_scores,
                test_scores=test_scores,
                bug_type=bug_type
            )
            
            print(f"      Consensus rate: {judgment.consensus_rate:.1%}")
            
            # Build final results from judgment
            top_k_judgments = self.judge_agent.get_top_k(judgment, num_top_locations)
            
            results = []
            for j in top_k_judgments:
                metadata = self.bm25.doc_metadata.get(j.class_name, {})
                results.append({
                    'type': 'class',
                    'name': j.class_name,
                    'file_path': metadata.get('file_path', ''),
                    'score': j.final_score,
                    'bm25_score': bm25_scores.get(j.class_name, 0) * max_bm25,
                    'stack_trace': stack_trace_scores.get(j.class_name, 0) > 0,
                    'pattern_score': pattern_scores.get(j.class_name, 0),
                    'test_score': test_scores.get(j.class_name, 0),
                    'consensus': j.consensus,
                    'reason': j.explanation,
                    'rank': j.rank
                })
        else:
            # Fallback to original scoring
            results = []
            for doc_id in candidate_names:
                metadata = self.bm25.doc_metadata.get(doc_id, {})
                class_name = metadata.get('class_name', doc_id)
                
                final_score = (
                    W_BM25 * bm25_scores.get(doc_id, 0) +
                    W_STACK_TRACE * stack_trace_scores.get(doc_id, 0) +
                    W_SEMANTIC * (1.0 if class_name in llm_classes else 0.0)
                )
                
                results.append({
                    'type': 'class',
                    'name': doc_id,
                    'file_path': metadata.get('file_path', ''),
                    'score': final_score,
                    'bm25_score': bm25_scores.get(doc_id, 0) * max_bm25,
                    'stack_trace': stack_trace_scores.get(doc_id, 0) > 0,
                    'reason': 'Stack trace' if stack_trace_scores.get(doc_id, 0) > 0 else 'BM25'
                })
            
            results.sort(key=lambda x: x['score'], reverse=True)
            results = results[:num_top_locations]
        
        # ===== Print Results =====
        print(f"\nTop-{num_top_locations} Suspicious Locations:")
        print("-"*80)
        print(f"{'Rank':<5} {'Score':<8} {'BM25':<7} {'ST':<4} {'Pat':<5} {'Test':<5} {'Class':<35}")
        print("-"*80)
        
        for i, loc in enumerate(results, 1):
            st_mark = "Y" if loc.get('stack_trace') else "-"
            class_short = loc['name'][-33:] if len(loc['name']) > 33 else loc['name']
            pat_score = f"{loc.get('pattern_score', 0):.2f}" if 'pattern_score' in loc else "-"
            test_score = f"{loc.get('test_score', 0):.2f}" if 'test_score' in loc else "-"
            print(f"{i:<5} {loc['score']:<8.4f} {loc.get('bm25_score', 0):<7.2f} {st_mark:<4} {pat_score:<5} {test_score:<5} {class_short}")
        
        print("-"*80)
        
        if self.use_agents:
            print(f"\nBug Type: {bug_type} | Weights: ST={dynamic_weights['stack_trace']:.2f}, "
                  f"BM25={dynamic_weights['bm25']:.2f}, Pat={dynamic_weights['pattern']:.2f}, "
                  f"Test={dynamic_weights['test']:.2f}")
        
        print("="*70)
        
        return results
    
    def _localize_with_langgraph(self, bug_report: str, num_top_locations: int) -> List[Dict]:
        """
        Run bug localization using LangGraph orchestrator.
        
        This method uses the LangGraph state machine to coordinate agents.
        """
        print("\n[*] Running LangGraph Agent Workflow...")
        
        # Run the LangGraph pipeline
        result = self.langgraph_orchestrator.localize(bug_report, top_k=num_top_locations)
        
        # Print agent execution trace
        print("\n" + "-"*60)
        print("AGENT EXECUTION TRACE:")
        print("-"*60)
        for step in result["agent_trace"]:
            print(f"  {step}")
        print("-"*60)
        
        # Print classification info
        print(f"\nBug Type: {result['bug_type']} (confidence: {result['bug_confidence']:.2f})")
        print(f"Consensus Rate: {result['consensus_rate']:.1%}")
        print(f"Total Candidates Evaluated: {result['total_candidates']}")
        
        # Print weights
        weights = result['weights_used']
        print(f"Dynamic Weights: ST={weights.get('stack_trace', 0):.2f}, "
              f"BM25={weights.get('bm25', 0):.2f}, "
              f"Pattern={weights.get('pattern', 0):.2f}, "
              f"Test={weights.get('test', 0):.2f}")
        
        # Print results table
        print(f"\nTop-{num_top_locations} Suspicious Locations:")
        print("-"*85)
        print(f"{'Rank':<5} {'Score':<8} {'BM25':<7} {'ST':<4} {'Pat':<5} {'Test':<5} {'Cons':<5} {'Class':<30}")
        print("-"*85)
        
        for loc in result["top_k"]:
            st_mark = "Y" if loc.get('stack_trace') else "-"
            cons_mark = "Y" if loc.get('consensus') else "-"
            class_short = loc['class_name'][-28:] if len(loc['class_name']) > 28 else loc['class_name']
            print(f"{loc['rank']:<5} {loc['score']:<8.4f} {loc.get('bm25_score', 0):<7.3f} "
                  f"{st_mark:<4} {loc.get('pattern_score', 0):<5.2f} {loc.get('test_score', 0):<5.2f} "
                  f"{cons_mark:<5} {class_short}")
        
        print("-"*85)
        
        # Convert to standard format
        results = []
        for loc in result["top_k"]:
            metadata = self.bm25.doc_metadata.get(loc['class_name'], {})
            results.append({
                'type': 'class',
                'name': loc['class_name'],
                'file_path': metadata.get('file_path', ''),
                'score': loc['score'],
                'bm25_score': loc.get('bm25_score', 0),
                'stack_trace': loc.get('stack_trace', False),
                'pattern_score': loc.get('pattern_score', 0),
                'test_score': loc.get('test_score', 0),
                'consensus': loc.get('consensus', False),
                'reason': loc.get('explanation', ''),
                'rank': loc['rank']
            })
        
        return results

    def _rank_candidates(self, candidates: List[Dict]) -> List[Dict]:
        """Legacy ranking method - now uses BM25-based ranking"""
        scores = {}
        for c in candidates:
            key = (c['type'], c['name'])
            if key not in scores:
                scores[key] = c.copy()
                scores[key]['score'] = 0.0
            scores[key]['score'] += c['score']
        
        ranked = list(scores.values())
        ranked.sort(key=lambda x: x['score'], reverse=True)
        return ranked
    
    def localize_from_text(self, bug_report: str, bug_id: str = "unknown", num_top_locations: int = 10) -> Dict:
        print(f"\nProcessing: {bug_id}")
        print("-"*70)
        preview = bug_report[:200] + "..." if len(bug_report) > 200 else bug_report
        print(preview)
        
        locations = self.identify_buggy_locations(bug_report, num_top_locations)
        
        return {
            'bug_id': bug_id,
            'top_locations': locations
        }
    
    def localize_from_file(self, bug_report_file: str, num_top_locations: int = 10) -> Dict:
        with open(bug_report_file, 'r', encoding='utf-8') as f:
            bug_report = f.read()
        return self.localize_from_text(bug_report, bug_report_file, num_top_locations)


def evaluate_results(results: List[Dict], ground_truth_file: str = None) -> Dict:
    """
    Evaluate bug localization results using standard IR metrics.
    
    If ground_truth_file is provided, calculate:
    - Top-1, Top-5, Top-10 Accuracy
    - MRR (Mean Reciprocal Rank)
    - MAP (Mean Average Precision)
    """
    if not ground_truth_file or not Path(ground_truth_file).exists():
        print("[*] No ground truth file - skipping evaluation")
        return {}
    
    with open(ground_truth_file, 'r') as f:
        ground_truth = json.load(f)
    
    metrics = TopKEvaluator.evaluate_all(results, ground_truth)
    
    print("\n" + "="*50)
    print("EVALUATION METRICS")
    print("="*50)
    print(f"Top-1 Accuracy:  {metrics['top_1']:.2f}%")
    print(f"Top-5 Accuracy:  {metrics['top_5']:.2f}%")
    print(f"Top-10 Accuracy: {metrics['top_10']:.2f}%")
    print(f"MRR:             {metrics['mrr']:.4f}")
    print(f"MAP:             {metrics['map']:.4f}")
    print("="*50)
    
    return metrics


def main():
    kg = Neo4jKnowledgeGraph()
    if not kg.driver:
        print("[-] Neo4j not connected")
        return
    
    localizer = BugLocalizer(kg, use_llm=True)
    
    # Build BM25 index once
    localizer.build_bm25_index()
    
    bug_dir = Path('bug_reports')
    if bug_dir.exists():
        results = []
        for f in bug_dir.glob('*.txt'):
            result = localizer.localize_from_file(str(f), num_top_locations=10)
            results.append(result)
        
        # Save results
        output_dir = Path('../outputs/json')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(output_dir / 'bug_localization_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n[+] Saved results to {output_dir / 'bug_localization_results.json'}")
        
        # Evaluate if ground truth exists
        ground_truth_file = Path('../ground_truth.json')
        if ground_truth_file.exists():
            metrics = evaluate_results(results, str(ground_truth_file))
            
            # Save metrics
            with open(output_dir / 'evaluation_metrics.json', 'w') as f:
                json.dump(metrics, f, indent=2)
    
    kg.close()


if __name__ == "__main__":
    main()
