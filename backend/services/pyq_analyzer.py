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
5. A list of specific past questions related to this topic from the PYQ paper, each accompanied by a comprehensive model answer based on the syllabus/notes context.

You MUST return a JSON object with a single key "topics" which contains an array of objects. Each object in the array must contain:
- "topic": The name of the topic.
- "frequency": An integer representing estimated number of occurrences.
- "importance": One of "High", "Medium", "Low".
- "description": A concise description of the typical question pattern and exam focus.
- "questions": An array of objects, where each object contains:
  - "question": The actual question text found in the PYQ paper.
  - "answer": A comprehensive model answer explaining the key concepts/steps needed to answer it.

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
                    
            desc = f"Typical question pattern focuses on defining **{topic_title}** and listing its core features."
            mock_answer = f"According to the lecture materials: {notes_match}." if notes_match else f"This topic covers the definition, structure, and theoretical implementation of {topic_title}. Make sure to detail all standard definitions, diagrams, and components as outlined in the syllabus."
                
            analysis_topics.append({
                "topic": topic_title,
                "frequency": freq,
                "importance": imp,
                "description": desc,
                "questions": [
                    {
                        "question": question,
                        "answer": mock_answer
                    }
                ]
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
                "description": "Asked in almost every semester paper. Usually carries 8 marks. Students are required to define deadlock and state the four necessary conditions with extensive explanation and examples.",
                "questions": [
                    {
                        "question": "Define Deadlock. Explain the four necessary conditions that must hold simultaneously for a deadlock to occur. Outline how each condition contributes to the state. (8 Marks)",
                        "answer": "### 1. Definition of Deadlock\nA deadlock is a state in computer systems where a set of processes are permanently blocked because each process is holding a resource and waiting to acquire another resource that is currently held by some other process in the same set. Since no process releases its currently held resource, none of them can progress, leading to a system standstill.\n\n### 2. The Four Necessary Coffman Conditions\nFor a deadlock to occur, the following four conditions must hold simultaneously. If even one of these conditions is prevented, deadlock cannot occur:\n\n1. **Mutual Exclusion**:\n   - **Explanation**: At least one resource must be held in a non-shareable mode. This means only one process can use the resource at any given instant.\n   - **Impact**: If another process requests that resource, the requesting process must be delayed until the resource is released. Resources like printers, tape drives, and database write-locks are mutually exclusive.\n\n2. **Hold and Wait**:\n   - **Explanation**: A process must currently be holding at least one resource and requesting additional resources that are currently being held by other processes.\n   - **Impact**: Instead of releasing what it already has before requesting more, the process holds on to its allocated resources while waiting, keeping them unavailable to others.\n\n3. **No Preemption**:\n   - **Explanation**: Resources cannot be preempted from a process. A resource can only be released voluntarily by the process holding it, after that process has finished its task.\n   - **Impact**: The operating system cannot forcibly take a resource away from a blocked process to allocate it to another process.\n\n4. **Circular Wait**:\n   - **Explanation**: A closed chain of processes must exist, such that each process is waiting for a resource held by the next process in the chain.\n   - **Impact**: Specifically, if there is a set of processes {P0, P1, ..., Pn}, P0 is waiting for a resource held by P1, P1 is waiting for P2, and Pn is waiting for P0. This circular dependency prevents any execution progress."
                    }
                ]
            },
            {
                "topic": "Paging vs Segmentation Comparison",
                "frequency": 5,
                "importance": "High",
                "description": "Very common comparison question, carrying 8 marks. Requires a detailed comparison table and explanations of internal/external fragmentation.",
                "questions": [
                    {
                        "question": "Compare Paging and Segmentation memory management schemes in detail. Your comparison should cover the programmers view, hardware support, fragmentation issues, and sharing of code. (8 Marks)",
                        "answer": "### 1. Overview\nBoth Paging and Segmentation are non-contiguous memory management techniques, but they differ fundamentally in how they divide memory and present it to the programmer.\n\n### 2. Detailed Comparison Table (8 Marks Value)\n\n| Feature | Paging | Segmentation |\n| :--- | :--- | :--- |\n| **Basic Concept** | Divides physical memory into fixed-size blocks (pages/frames). | Divides logical memory into variable-size blocks based on logical modules (segments). |\n| **Programmer View** | Totally invisible to the programmer (flat address space). | Visible to the programmer (divided into code, stack, data segments). |\n| **Size** | Pages are of fixed size (e.g., 4KB), determined by hardware. | Segments are of variable size, determined by user/program requirements. |\n| **Fragmentation** | Causes **Internal Fragmentation** (unused space in the last page frame). | Causes **External Fragmentation** (scattered free slots too small for new segments). |\n| **Hardware Support** | Requires a **Page Table** mapping page number to frame number. | Requires a **Segment Table** mapping segment number to base limit. |\n| **Sharing & Protection** | Harder to implement because logical code is split across arbitrary page boundaries. | Easier to implement because protection labels can be attached to complete logical segments. |\n\n### 3. Key Differences in Detail\n- **Fragmentation**: Paging eliminates external fragmentation by using fixed-size slots, but wastes space inside the last frame of a process (internal fragmentation). Segmentation eliminates internal fragmentation because segments are allocated exactly the size requested, but creates external fragmentation over time as segments are loaded and deleted.\n- **Address Translation**:\n  - In Paging: CPU logical address is divided into `Page Number (p)` and `Offset (d)`. Page Table maps `p` to `Frame (f)`. Physical Address = `f * page_size + d`.\n  - In Segmentation: CPU logical address is divided into `Segment Number (s)` and `Offset (d)`. Segment Table checks if `d < limit`, then adds `base` to get the physical address: `Physical Address = base + d`."
                    }
                ]
            },
            {
                "topic": "Banker's Algorithm Problems",
                "frequency": 4,
                "importance": "High",
                "description": "A high-scoring numerical problem (usually 8 marks). Requires calculating the 'Need' matrix and finding a safe execution sequence of processes.",
                "questions": [
                    {
                        "question": "Explain the Banker's Algorithm for deadlock avoidance. Detail the Safety Algorithm steps and outline how a resource-request is checked. (8 Marks)",
                        "answer": "### 1. Introduction to Banker's Algorithm\nThe Banker's Algorithm is a deadlock avoidance algorithm used by operating systems. It is named after its banking analogy, where a banker decides whether to approve loan requests based on credit limits and available cash. In an OS, the resource manager checks if granting a resource request will leave the system in a **Safe State**.\n\n### 2. Data Structures Used\nFor $n$ processes and $m$ resource types:\n- `Available[m]`: Vector of length $m$ indicating available resources of each type.\n- `Max[n][m]`: Max resource demand of each process.\n- `Allocation[n][m]`: Resources currently allocated to each process.\n- `Need[n][m]`: Remaining resource need of each process: `Need[i][j] = Max[i][j] - Allocation[i][j]`.\n\n### 3. The Safety Algorithm (8 Marks Detail)\nThis algorithm determines if a system state is safe:\n1. Let `Work` be a vector of length $m$, initialized to `Available`.\n2. Let `Finish` be a boolean array of length $n$, initialized to `False` for all $i$.\n3. Find an index $i$ such that both:\n   - `Finish[i] == False`\n   - `Need[i] <= Work`\n   If no such $i$ exists, go to **Step 5**.\n4. If found, update:\n   - `Work = Work + Allocation[i]`\n   - `Finish[i] = True`\n   Go back to **Step 3**.\n5. If `Finish[i] == True` for all $i$, then the system is in a **Safe State**. If any process remains unfinished, the system is unsafe (deadlock risk).\n\n### 4. Resource-Request Algorithm\nWhen process $P_i$ makes a request vector `Request[i]`:\n1. If `Request[i] <= Need[i]`, proceed. Otherwise, raise an error (request exceeds maximum claim).\n2. If `Request[i] <= Available`, proceed. Otherwise, $P_i$ must wait (resources not available).\n3. Temporarily allocate resources by modifying states:\n   - `Available = Available - Request[i]`\n   - `Allocation[i] = Allocation[i] + Request[i]`\n   - `Need[i] = Need[i] - Request[i]`\n4. Run the **Safety Algorithm**. If safe, transaction is finalized and resources are allocated. If unsafe, rollback temporary changes and force $P_i$ to wait."
                    }
                ]
            },
            {
                "topic": "CPU Scheduling Algorithms",
                "frequency": 4,
                "importance": "High",
                "description": "Long-form problems asking to explain and compute scheduling metrics using Gantt charts.",
                "questions": [
                    {
                        "question": "Explain Round Robin (RR) and Preemptive Shortest Job First (SRTF) scheduling algorithms. Contrast their performance on average waiting time and response time. (8 Marks)",
                        "answer": "### 1. Round Robin (RR) Scheduling\n- **Mechanism**: Round Robin is a preemptive scheduling algorithm designed for time-sharing systems. The CPU scheduler circles through a ready queue, allocating the CPU to each process for a fixed time interval known as a **Time Quantum** (typically 10-100 milliseconds).\n- **Preemption**: If a process's CPU burst exceeds the time quantum, it is preempted and put back at the tail of the ready queue.\n- **Performance**: RR provides excellent **Response Time** (time from submission to first response) but can result in high average waiting times if the time quantum is too small (due to frequent context switches).\n\n### 2. Shortest Remaining Time First (SRTF)\n- **Mechanism**: SRTF is the preemptive version of Shortest Job First (SJF) scheduling. When a new process arrives in the ready queue, its remaining CPU burst time is compared with the remaining time of the currently executing process.\n- **Preemption**: If the newly arrived process has a shorter remaining CPU burst time, the CPU is preempted from the current process and allocated to the new one.\n- **Performance**: SRTF is mathematically optimal as it guarantees the minimum **Average Waiting Time** for a given set of processes. However, it can cause **starvation** for long processes if short processes keep entering the queue.\n\n### 3. Structural Comparison (8 Marks Analysis)\n\n| Attribute | Round Robin (RR) | Shortest Remaining Time First (SRTF) |\n| :--- | :--- | :--- |\n| **Preemption Criteria** | Time quantum expiration. | Arrival of process with shorter remaining burst. |\n| **Average Waiting Time** | Moderate to high. | Optimal (Minimum possible). |\n| **Response Time** | Very good (Guaranteed upper bound). | Poor for longer processes. |\n| **Starvation Risk** | None. | High for long-running processes. |\n| **Context Overhead** | High (depends on time quantum). | Moderate (only on arrival check preemption). |"
                    }
                ]
            },
            {
                "topic": "Semaphores and Mutual Exclusion",
                "frequency": 3,
                "importance": "Medium",
                "description": "Coding/theoretical questions on critical section solutions using Semaphores.",
                "questions": [
                    {
                        "question": "What is a Semaphore? Explain how Binary and Counting Semaphores work. Write a C/pseudo-code solution for the Producer-Consumer problem using semaphores. (8 Marks)",
                        "answer": "### 1. Semaphore Definition\nA semaphore is a synchronization tool represented as an integer variable. Except during initialization, it is accessed only through two standard atomic, indivisible operations:\n- `wait(S)` (originally `P(S)`): Decrements the semaphore value. If the value becomes negative, the executing process is blocked.\n- `signal(S)` (originally `V(S)`): Increments the semaphore value. If there are blocked processes, one is unblocked.\n\n### 2. Binary vs Counting Semaphores\n- **Binary Semaphore**: The integer value ranges only between 0 and 1. It acts as a lock (Mutex) to guarantee mutual exclusion in critical sections.\n- **Counting Semaphore**: The integer value can range over an unrestricted domain. It is used to control access to a resource pool with a finite number of instances.\n\n### 3. Producer-Consumer Problem Solution (8 Marks Value)\nBelow is the pseudocode solving the bounded-buffer Producer-Consumer problem using three semaphores:\n1. `mutex` (binary semaphore initialized to 1) for mutual exclusion on buffer access.\n2. `empty` (counting semaphore initialized to `BUFFER_SIZE`) tracking empty buffer slots.\n3. `full` (counting semaphore initialized to 0) tracking filled buffer slots.\n\n```c\n// Shared buffer structures\nitem buffer[BUFFER_SIZE];\nint in = 0, out = 0;\n\n// Semaphores\nsemaphore mutex = 1;\nsemaphore empty = BUFFER_SIZE;\nsemaphore full = 0;\n\nvoid producer() {\n    while(true) {\n        // Produce an item\n        item next_produced = produce_item();\n        \n        wait(empty);  // Wait for an empty slot\n        wait(mutex);  // Lock buffer critical section\n        \n        buffer[in] = next_produced;\n        in = (in + 1) % BUFFER_SIZE;\n        \n        signal(mutex); // Unlock critical section\n        signal(full);  // Signal that an item is available\n    }\n}\n\nvoid consumer() {\n    while(true) {\n        wait(full);   // Wait for a filled slot\n        wait(mutex);  // Lock buffer critical section\n        \n        item next_consumed = buffer[out];\n        out = (out + 1) % BUFFER_SIZE;\n        \n        signal(mutex); // Unlock critical section\n        signal(empty); // Signal that a slot is empty\n        \n        // Consume the item\n        consume_item(next_consumed);\n    }\n}\n```"
                    }
                ]
            }
        ]
