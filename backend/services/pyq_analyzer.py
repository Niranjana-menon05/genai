import os
import json
import re
from typing import List, Dict, Any
from backend import config
from backend.services.study_agent import get_groq_model

class PYQAnalyzer:
    @classmethod
    def analyze_pyq(cls, pyq_text: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyzes PYQ papers against lecture notes context to extract frequently asked topics."""
        context_text = "\n\n".join([f"Context Chunk: {c['text']}" for c in context_chunks])
        
        if config.IS_MOCK_MODE or not get_groq_model():
            if context_chunks or pyq_text:
                analysis = cls._generate_dynamic_mock_analysis(pyq_text, context_chunks)
            else:
                analysis = cls._generate_mock_analysis()
            return {
                "analysis": analysis,
                "mode": "mock"
            }
            
        try:
            model = get_groq_model()
            from langchain_core.prompts import ChatPromptTemplate
            
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", """You are an academic examiner and syllabus designer. Analyze the uploaded Previous Year Question (PYQ) paper text against the syllabus/lecture note context provided.
                
Identify:
1. The most frequently asked topics.
2. The frequency count (estimate how many times they appear across years/sections).
3. The importance level (High, Medium, Low).
4. A description of what specific sub-questions are asked and key points to study.

You MUST return a JSON object with a single key "topics" which contains an array of objects. Each object in the array must contain:
- "topic": The name of the topic.
- "frequency": An integer representing estimated number of occurrences.
- "importance": One of "High", "Medium", "Low".
- "description": A concise description of the typical question pattern and exam focus.

Return ONLY valid JSON. Do not include any conversational text. Use double quotes. Escape any quotes inside text."""),
                ("human", "Syllabus/Notes Context:\n{context}\n\nPYQ Paper Content:\n{pyq}")
            ])
            
            chain = prompt_template | model
            response = chain.invoke({
                "context": context_text if context_text else "General operating system syllabus covering process management, scheduling, memory management, and file systems.",
                "pyq": pyq_text
            })
            
            # Clean and parse JSON response
            raw_content = response.content.strip()
            if raw_content.startswith("```json"):
                raw_content = raw_content[7:]
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3]
            raw_content = raw_content.strip()
            
            parsed_analysis = json.loads(raw_content)
            return {
                "analysis": parsed_analysis.get("topics", parsed_analysis),
                "mode": "live"
            }
        except Exception as e:
            print(f"Error during PYQ analysis: {e}")
            if context_chunks or pyq_text:
                analysis = cls._generate_dynamic_mock_analysis(pyq_text, context_chunks)
            else:
                analysis = cls._generate_mock_analysis()
            return {
                "analysis": analysis,
                "mode": "fallback_mock",
                "error": str(e)
            }

    @classmethod
    def _generate_dynamic_mock_analysis(cls, pyq_text: str, context_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        import random
        
        # 1. Extract actual questions from the PYQ paper
        lines = pyq_text.split("\n")
        raw_questions = []
        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue
                
            # Filter lines that look like questions: start with digit/Q/subparts or contain question marks/verbs
            is_question = False
            # Check prefix (e.g. Q1, 1., a))
            if re.match(r'^(Q\d+|\d+[\.\)]|[a-g]\))', line_clean, re.IGNORECASE):
                is_question = True
            # Check key verbs / question marks
            elif "?" in line_clean or any(verb in line_clean.lower() for verb in ("explain", "define", "discuss", "what is", "difference between", "distinguish", "calculate", "prove")):
                if len(line_clean) > 15: # avoid tiny headers
                    is_question = True
                    
            if is_question:
                # Remove question prefixes (numbers/bullets) for cleaner display
                cleaned_q = re.sub(r'^(Q\d+[\.\)]?|\d+[\.\)]|[a-g]\)\s*|[\*\-\#]\s*)', '', line_clean, flags=re.IGNORECASE).strip()
                if len(cleaned_q) > 10:
                    raw_questions.append(cleaned_q)

        # 2. Get notes content text to match definitions
        notes_text = " ".join([c["text"] for c in context_chunks])
        sentences = notes_text.replace("\n", " ").split(".")
        
        # 3. Match questions to syllabus concepts
        analysis_topics = []
        importances = ["High", "High", "Medium", "Medium", "Low", "Low"]
        random.seed(len(pyq_text))

        # If we couldn't extract enough questions, write some based on keyword matches
        if len(raw_questions) < 3:
            # Fallback to scanning capitalized terms in combined text
            combined_text = pyq_text + " " + notes_text
            terms = re.findall(r'\b[A-Z][a-zA-Z]+\s+[A-Z][a-zA-Z]+\b|\b[A-Z][a-zA-Z]+\b', combined_text)
            ignore_words = {"lecture", "notes", "chapter", "module", "question", "marks", "exam", "syllabus", "content"}
            unique_terms = []
            for t in terms:
                if t.lower() not in ignore_words and len(t) > 5 and t not in unique_terms:
                    unique_terms.append(t)
            
            for term in unique_terms[:5]:
                raw_questions.append(f"Explain the concept of {term} and its applications.")

        # Limit to 6 topics
        selected_questions = raw_questions[:6]
        
        for idx, question in enumerate(selected_questions):
            # Formulate a cleaner "Topic Title" by extracting the key words/phrase
            topic_title = question
            # Strip leading symbols (leftover dots, dashes, spaces)
            topic_title = re.sub(r'^[\.\,\-\*#\s\(\)]+', '', topic_title).strip()
            # Strip question mark and common prefixes
            topic_title = re.sub(r'\?+$', '', topic_title).strip()
            topic_title = re.sub(r'^(explain|define|discuss|what is|write a short note on|differentiate between|compare)\s+', '', topic_title, flags=re.IGNORECASE).strip()
            
            # Capitalise first letter
            if topic_title:
                topic_title = topic_title[0].upper() + topic_title[1:]
                # Limit length for title display
                if len(topic_title) > 40:
                    topic_title = topic_title[:38] + "..."
            
            freq = random.randint(3, 6) if idx < 3 else random.randint(1, 2)
            imp = importances[idx] if idx < len(importances) else "Low"
            
            # Find a matching reference sentence in the notes
            notes_match = ""
            # Extract nouns from question for basic match
            q_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{5,15}\b', question)]
            max_matches = 0
            
            for s in sentences:
                s_clean = s.strip()
                if len(s_clean) < 30 or len(s_clean) > 200:
                    continue
                matches = sum(1 for qw in q_words if qw in s_clean.lower())
                if matches > max_matches:
                    max_matches = matches
                    notes_match = s_clean
                    
            desc = f"**Question in PYQ**: \"{question}\""
            if notes_match:
                desc += f"\n\n**Lecture Reference**: *\"{notes_match}.\"*"
            else:
                desc += "\n\n**Lecture Reference**: *No direct matching reference found in lecture notes. Recommend reviewing syllabus definition.*"
                
            analysis_topics.append({
                "topic": topic_title,
                "frequency": freq,
                "importance": imp,
                "description": desc
            })
            
        # If still empty, return default mock analysis
        if not analysis_topics:
            return cls._generate_mock_analysis()
            
        return analysis_topics

    @staticmethod
    def _generate_mock_analysis() -> List[Dict[str, Any]]:
        return [
            {
                "topic": "Coffman Conditions & Deadlock Definition",
                "frequency": 6,
                "importance": "High",
                "description": "Asked in almost every semester paper. Usually carries 4 to 8 marks. Students are required to define deadlock and state the four necessary conditions (Mutual Exclusion, Hold & Wait, No Preemption, Circular Wait) with diagrammatic examples."
            },
            {
                "topic": "Paging vs Segmentation",
                "frequency": 5,
                "importance": "High",
                "description": "Very common comparison question, usually carrying 6 marks. Requires a detailed comparison table outlining page frame sizes, user views of memory, and how internal/external fragmentation affects each."
            },
            {
                "topic": "Banker's Algorithm Problems",
                "frequency": 4,
                "importance": "High",
                "description": "A high-scoring numerical problem (usually 8-10 marks). Requires calculating the 'Need' matrix and finding a safe execution sequence of processes given allocation, max demand, and availability vectors."
            },
            {
                "topic": "CPU Scheduling Algorithms (Gantt Charts)",
                "frequency": 4,
                "importance": "High",
                "description": "Numerical problems asking to compute Average Waiting Time and Average Turnaround Time using algorithms like FCFS, SJF, Priority, or Round Robin. Always demands drawing the scheduling Gantt chart."
            },
            {
                "topic": "Semaphores and Mutual Exclusion",
                "frequency": 3,
                "importance": "Medium",
                "description": "Theoretical or code-based questions on process synchronization. Commonly asks to implement a critical section lock using binary semaphores (`wait()` and `signal()` operations) or explain the Producer-Consumer problem."
            },
            {
                "topic": "Belady's Anomaly & FIFO Page Replacement",
                "frequency": 2,
                "importance": "Medium",
                "description": "Typically asked as a short-note question (4 marks) or as a sub-question in page replacement numericals. Requires explaining why increasing page frames sometimes paradoxically increases page faults under FIFO."
            },
            {
                "topic": "Logical vs Physical Address Space",
                "frequency": 2,
                "importance": "Low",
                "description": "Introductory concept, usually asked as a short 2-mark definition. Focuses on the role of the Memory Management Unit (MMU) in dynamic run-time mapping."
            }
        ]
