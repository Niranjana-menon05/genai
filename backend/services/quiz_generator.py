import os
import json
from typing import List, Dict, Any
from backend import config
from backend.services.study_agent import get_groq_model

class QuizGenerator:
    @classmethod
    def generate_quiz(cls, context_chunks: List[Dict[str, Any]], quiz_type: str, difficulty: str, count: int = 5) -> Dict[str, Any]:
        """Generates quiz questions based on context."""
        context_text = "\n\n".join([f"Context Chunk: {c['text']}" for c in context_chunks])
        
        if config.IS_MOCK_MODE or not get_groq_model():
            if context_chunks:
                questions = cls._generate_dynamic_mock_quiz(context_chunks, quiz_type, difficulty, count)
            else:
                questions = cls._generate_mock_quiz(quiz_type, difficulty, count)
            return {
                "questions": questions,
                "mode": "mock"
            }
            
        try:
            model = get_groq_model()
            from langchain_core.prompts import ChatPromptTemplate
            
            # Format requirements based on quiz type
            format_instructions = ""
            if quiz_type.lower() == "mcq":
                format_instructions = """Each question must be multiple choice.
Return a JSON array of objects, where each object has:
- "question": The question text.
- "options": An array of exactly 4 strings.
- "correct_answer": The exact string of the correct option.
- "explanation": An elaborate, highly detailed explanation (at least 3-4 sentences) explaining why the answer is correct and why other options are incorrect based on the study material."""
            elif quiz_type.lower() == "short":
                format_instructions = """Each question must be a short answer question testing conceptual depth.
Return a JSON array of objects, where each object has:
- "question": The question text.
- "sample_answer": An elaborate, comprehensive model answer (at least 5-8 sentences or bullet points) that is structured and highly detailed, showing deep academic understanding.
- "explanation": A detailed breakdown of the key scoring criteria, essential terms, and concepts the evaluator will look for in the answer."""
            else:  # Viva
                format_instructions = """Each question must be a viva-voce/oral examination question.
Return a JSON array of objects, where each object has:
- "question": The question text.
- "sample_answer": An elaborate, detailed verbal response (4-6 sentences) that is professional, structured, and displays strong conceptual mastery.
- "explanation": In-depth background information, follow-up questions to expect, and practical tips on how to effectively structure and present this verbal response to an academic examiner."""

            prompt_template = ChatPromptTemplate.from_messages([
                ("system", f"""You are an expert university exam paper setter. Generate a quiz of exactly {count} {quiz_type.upper()} questions of {difficulty.upper()} difficulty based on the provided document context.

Generate high-quality quiz questions ONLY from the provided study material.

Rules:
1. Read the study material carefully and understand the concepts before generating questions.
2. Every question must test a meaningful concept, not isolated words, headings, filenames, table entries, bullet points, page numbers, image captions, formatting text, or metadata.
3. Never create questions from:
   - document titles
   - section headings alone
   - bold words without context
   - figure labels
   - page numbers
   - OCR mistakes
   - incomplete sentences
4. Questions must be grammatically correct and natural.
5. Each question must have ONE clearly correct answer. (For MCQs, wrong options should be plausible but incorrect).
6. Do not repeat questions that test exactly the same concept.
7. Every question should focus on a different topic whenever possible.
8. If insufficient information exists for a concept, skip it.
9. Return ONLY valid JSON in the requested format. Do not write any conversational intro or outro. Use double quotes for JSON keys and values. Escape any double quotes inside text.

Format Requirements:
{format_instructions}

Context:
{{context}}"""),
                ("human", "Generate the quiz now.")
            ])
            
            chain = prompt_template | model
            response = chain.invoke({"context": context_text if context_text else "General computer science and operating systems."})
            
            # Clean and parse JSON response
            raw_content = response.content.strip()
            
            # Strip markdown json blocks if present
            if raw_content.startswith("```json"):
                raw_content = raw_content[7:]
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3]
            raw_content = raw_content.strip()
            
            parsed_questions = json.loads(raw_content)
            return {
                "questions": parsed_questions,
                "mode": "live"
            }
        except Exception as e:
            print(f"Error generating quiz: {e}")
            if context_chunks:
                questions = cls._generate_dynamic_mock_quiz(context_chunks, quiz_type, difficulty, count)
            else:
                questions = cls._generate_mock_quiz(quiz_type, difficulty, count)
            return {
                "questions": questions,
                "mode": "fallback_mock",
                "error": str(e)
            }

    @classmethod
    def _generate_dynamic_mock_quiz(cls, chunks: List[Dict[str, Any]], quiz_type: str, difficulty: str, count: int) -> List[Dict[str, Any]]:
        import re
        import random

        # Extract all text
        text = " ".join([c["text"] for c in chunks])
        text = re.sub(r'\s+', ' ', text)
        
        # Split into sentences
        raw_sentences = text.split(".")
        
        pairs = []
        all_predicates = []
        
        ignore_words = {
            "limitation", "limitations", "goal", "goals", "note", "notes", "important", 
            "advantage", "advantages", "disadvantage", "disadvantages", "warning", "warnings", 
            "step", "steps", "rule", "rules", "example", "examples", "requirement", "requirements", 
            "feature", "features", "characteristic", "characteristics", "type", "types", 
            "method", "methods", "function", "functions", "property", "properties", 
            "application", "applications", "benefit", "benefits", "drawback", "drawbacks", 
            "difference", "differences", "similarity", "similarities", "definition", "definitions", 
            "description", "descriptions", "explanation", "explanations", "introduction", "introductions", 
            "summary", "summaries", "conclusion", "conclusions", "fact", "facts", "problem", "problems", 
            "solution", "solutions", "it", "they", "this", "these", "that", "those", "he", "she", 
            "we", "you", "i", "who", "which", "what", "where", "when", "why", "how", "another", 
            "other", "others", "some", "any", "all", "each", "every", "both", "either", "neither", 
            "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", 
            "first", "second", "third", "fourth", "fifth", "last", "next", "previous", "following", 
            "above", "below", "here", "there", "their", "our", "your", "my", "his", "her", "its", 
            "a", "an", "the", "key", "main", "major", "primary", "secondary", "essential", 
            "crucial", "critical", "significant", "minor", "basic", "simple", "complex", "points",
            "point", "aspect", "aspects", "factor", "factors", "issue", "issues", "item", "items",
            "detail", "details", "part", "parts", "element", "elements", "component", "components",
            "objective", "objectives", "purpose", "purposes", "target", "targets", "result", "results",
            "outcome", "outcomes", "effect", "effects", "impact", "impacts", "influence", "influences",
            "reason", "reasons", "cause", "causes", "source", "sources", "origin", "origins",
            "idea", "ideas", "concept", "concepts", "notion", "notions", "theory", "theories"
        }

        def clean_text(text_str: str) -> str:
            text_str = text_str.replace("*", "").replace("`", "")
            # Remove parenthesized figure/page references, e.g. (Figure 2) or (slide 5)
            text_str = re.sub(r'\(\s*(?:figure|fig|slide|page|sec|section|table)\s*\d+[a-z]?\s*\)', '', text_str, flags=re.IGNORECASE).strip()
            # Remove direct references, e.g. Figure 2 or slide 5
            text_str = re.sub(r'\b(figure|fig|slide|page|sec|section|table)\s*\d+[a-z]?\b', '', text_str, flags=re.IGNORECASE).strip()
            # Remove trailing numbers (typically slide or page numbers)
            text_str = re.sub(r'\b\d+\b$', '', text_str).strip()
            # Clean duplicate whitespaces
            text_str = re.sub(r'\s+', ' ', text_str).strip()
            return text_str
        
        for s in raw_sentences:
            s_clean = s.strip()
            if 30 < len(s_clean) < 180 and not any(x in s_clean.lower() for x in ("page break", "slide break", "table data", "---")):
                # Split at standard definition points
                parts = re.split(r'\bis\b|\bare\b|\brefers to\b|\bmeans\b|:| - ', s_clean, maxsplit=1, flags=re.IGNORECASE)
                if len(parts) == 2:
                    sub = parts[0].strip()
                    pred = parts[1].strip()
                    # Clean subject (remove leading bullet marks, letters like A), a), numbers, etc.)
                    sub = re.sub(r'^(?:[a-zA-Z0-9]{1,3}[\.\)]|[•\-\*\d\.#\s\(\)])+', '', sub).strip()
                    # Clean predicate as well from leading symbols
                    pred = re.sub(r'^(?:[a-zA-Z0-9]{1,3}[\.\)]|[•\-\*\d\.#\s\(\)])+', '', pred).strip()
                    
                    # Clean figures, page numbers, trailing digits, etc.
                    sub = clean_text(sub)
                    pred = clean_text(pred)
                    
                    # Normalize subject to check if it's generic
                    sub_norm = sub.lower()
                    # Remove common leading determiners/adjectives
                    sub_norm = re.sub(r'^(?:the|a|an|main|key|major|primary|another|this|that|these|those|some|any|our|their|your|my|its)\s+', '', sub_norm).strip()
                    
                    if not sub_norm or sub_norm in ignore_words:
                        continue
                        
                    # Skip if the subject is a single character or starts with non-alphanumeric character
                    if len(sub_norm) < 2 or not sub_norm[0].isalnum():
                        continue
                    
                    if 2 < len(sub) < 35 and 10 < len(pred) < 130:
                        # Capitalise subject
                        if sub:
                            sub = sub[0].upper() + sub[1:]
                        pairs.append((sub, pred, s_clean))
                        all_predicates.append(pred)

        # If we don't have enough structured pairs, fall back to simple sentence prompts
        if len(pairs) < count:
            generated = []
            random.seed(len(text))
            shuffled_sentences = [s.strip() for s in raw_sentences if 30 < len(s.strip()) < 150]
            random.shuffle(shuffled_sentences)
            
            for s in shuffled_sentences[:count]:
                # Make a simple sentence query
                words = s.split()
                if len(words) > 4:
                    keyword = " ".join(words[:2])
                    rest = " ".join(words[2:])
                    
                    keyword = clean_text(keyword)
                    rest = clean_text(rest)
                    s_clean_words = clean_text(s)
                    
                    # Fallback question templates
                    fallback_mcq_templates = [
                        f"Based on your notes, which of the following completes: '{keyword} ...'?",
                        f"How does the phrase '{keyword} ...' finish in the source text?",
                        f"Identify the correct continuation of the statement: '{keyword} ...'",
                        f"Complete the following concept from your readings: '{keyword} ...'",
                        f"Which option accurately completes: '{keyword} ...'?"
                    ]
                    fallback_text_templates = [
                        f"Explain the context of: '{keyword}' from your reading material.",
                        f"Provide a brief explanation of how '{keyword}' is used in the text.",
                        f"Discuss the concept of '{keyword}' based on your study notes.",
                        f"What does the source material state regarding '{keyword}'?",
                        f"Elaborate on the significance of '{keyword}' in your notes."
                    ]
                    
                    if quiz_type.lower() == "mcq":
                        generated.append({
                            "question": fallback_mcq_templates[len(generated) % len(fallback_mcq_templates)],
                            "options": [rest, "a fundamental component of the algorithm.", "an optimized resource constraint.", "scheduling queue parameters."],
                            "correct_answer": rest,
                            "explanation": f"Source document text: '{s_clean_words}'."
                        })
                    else:
                        generated.append({
                            "question": fallback_text_templates[len(generated) % len(fallback_text_templates)],
                            "sample_answer": s_clean_words,
                            "explanation": f"Source notes state: '{s_clean_words}'."
                        })
            # Fill in if still empty
            if not generated:
                return cls._generate_mock_quiz(quiz_type, difficulty, count)
            return generated[:count]

        # Shuffle pairs
        random.seed(len(text))
        random.shuffle(pairs)
        
        generated = []
        for i, (sub, pred, full_sentence) in enumerate(pairs[:count]):
            # Clean full sentence and predicate
            full_sentence_clean = clean_text(full_sentence)
            pred_clean = clean_text(pred)
            
            if quiz_type.lower() == "mcq":
                # Correct option is the predicate
                correct_ans = pred_clean
                
                # Distractors are other predicates from the document
                other_preds = [clean_text(p) for p in all_predicates if p != pred]
                random.shuffle(other_preds)
                distractors = other_preds[:3]
                
                # Pad distractors if needed
                while len(distractors) < 3:
                    distractors.append(f"A conceptual mechanism described in the {sub} module.")
                    
                options = [correct_ans] + distractors
                random.shuffle(options)
                
                mcq_templates = [
                    f"What is the primary function or definition of '{sub}' as described in the study notes?",
                    f"Based on your readings, how is the concept of '{sub}' defined?",
                    f"Which of the following best describes the role of '{sub}'?",
                    f"In the context of the study material, what does '{sub}' refer to?",
                    f"Which option correctly explains the mechanism of '{sub}'?"
                ]
                q_text = mcq_templates[i % len(mcq_templates)]
                
                generated.append({
                    "question": q_text,
                    "options": options,
                    "correct_answer": correct_ans,
                    "explanation": f"According to your materials: '{full_sentence_clean}'"
                })
            elif quiz_type.lower() == "short":
                short_templates = [
                    f"Based on your lecture notes, provide a detailed explanation of '{sub}'.",
                    f"Discuss the significance and key operational constraints of '{sub}'.",
                    f"Explain '{sub}' in detail, highlighting its role within the system.",
                    f"Describe the mechanism of '{sub}' and summarize its main objectives as outlined in your study materials.",
                    f"Write a comprehensive conceptual overview of '{sub}', focusing on its definition and behavior."
                ]
                q_text = short_templates[i % len(short_templates)]
                
                generated.append({
                    "question": q_text,
                    "sample_answer": f"{sub} refers to the concept or mechanism where {pred_clean}. In the context of the study material, understanding this is essential for analyzing the system's behavior and operational constraints. Key aspects include its basic definition, its role in the overall architecture, and how it relates to other components.",
                    "explanation": f"The evaluator will look for a clear explanation of {sub} as {pred_clean}. The response should detail its definition, context within the study material, and its primary implications."
                })
            else:  # viva
                viva_templates = [
                    f"If asked in a viva voce: 'What do you understand by the term \"{sub}\"?', how would you respond?",
                    f"How would you explain the concept of \"{sub}\" if an examiner asks you to define it during a viva?",
                    f"Prepare a verbal response to the examiner's question: 'What is the primary purpose of \"{sub}\"?'",
                    f"If an examiner asks you to describe \"{sub}\" in your own words, how would you structure your answer?",
                    f"During a viva, how would you summarize the core function and limits of \"{sub}\"?"
                ]
                q_text = viva_templates[i % len(viva_templates)]
                
                generated.append({
                    "question": q_text,
                    "sample_answer": f"Sir/Ma'am, {sub} is defined as {pred_clean}. To elaborate further, it functions as a core concept in this domain, defining key boundaries or constraints. We study this to understand how different components interact and how system behavior is coordinated under typical workloads.",
                    "explanation": f"Explain {sub} clearly using its definition: '{pred_clean}'. To impress the examiner, relate it to the broader topics in the study material and discuss its practical implications or limitations."
                })
                
        return generated


    @staticmethod
    def _generate_mock_quiz(quiz_type: str, difficulty: str, count: int) -> List[Dict[str, Any]]:
        # Ensure count matches request (within limits)
        if count > 5:
            count = 5
            
        mcq_questions = [
            {
                "question": "Which of the following is NOT a necessary condition for a deadlock to occur?",
                "options": [
                    "Mutual Exclusion",
                    "Hold and Wait",
                    "Preemption",
                    "Circular Wait"
                ],
                "correct_answer": "Preemption",
                "explanation": "According to the Coffman conditions, **No Preemption** is the necessary condition for a deadlock to occur, meaning resources cannot be forcibly snatched from a process. **Preemption** (the ability of the OS to preempt resources) is actually a deadlock recovery or prevention strategy, not a cause of deadlock. The other three necessary conditions are Mutual Exclusion, Hold & Wait, and Circular Wait."
            },
            {
                "question": "What memory allocation problem does Paging solve, and what type of fragmentation does it introduce?",
                "options": [
                    "Solves Internal Fragmentation; introduces External Fragmentation",
                    "Solves External Fragmentation; introduces Internal Fragmentation",
                    "Solves both Internal and External Fragmentation",
                    "Solves Page Faults; introduces Belady's Anomaly"
                ],
                "correct_answer": "Solves External Fragmentation; introduces Internal Fragmentation",
                "explanation": "Paging solves the problem of **External Fragmentation** by dividing physical memory into fixed-size frames and allocating memory non-contiguously. However, because memory is allocated in fixed pages, if a process requests a size that is not an exact multiple of the page size, the last page frame will have unused memory, which introduces **Internal Fragmentation**."
            },
            {
                "question": "In the Banker's Algorithm for deadlock avoidance, how is the remaining resource demand (Need) computed?",
                "options": [
                    "Need = Max - Allocation",
                    "Allocation = Max + Need",
                    "Available = Max - Need",
                    "Need = Allocation - Max"
                ],
                "correct_answer": "Need = Max - Allocation",
                "explanation": "The safety matrix calculations in the Banker's Algorithm define the **Need** matrix as the maximum potential resource claim of a process minus its currently allocated resources: `Need = Max - Allocation`. This determines how many more resources the process might request in the worst-case scenario before releasing its allocations."
            },
            {
                "question": "Which CPU scheduling algorithm is mathematically proven to guarantee the minimum average waiting time for a given set of stationary processes?",
                "options": [
                    "Round Robin (RR)",
                    "Shortest Job First (SJF)",
                    "First-Come First-Served (FCFS)",
                    "Priority Scheduling"
                ],
                "correct_answer": "Shortest Job First (SJF)",
                "explanation": "Shortest Job First (SJF) scheduling is provably optimal. By scheduling the process with the shortest CPU burst time first, it minimizes the wait time for the remaining processes in the queue, thereby guaranteeing the absolute minimum average waiting time for any non-preemptive set of processes."
            },
            {
                "question": "Belady's Anomaly is a counter-intuitive phenomenon. In which page replacement algorithm is it most commonly observed, and what causes it?",
                "options": [
                    "LRU (Least Recently Used) because it tracks history.",
                    "FIFO (First-In, First-Out) because it does not follow the stack property.",
                    "Optimal Page Replacement because it looks into the future.",
                    "LFU (Least Frequently Used) because of frequency count stagnation."
                ],
                "correct_answer": "FIFO (First-In, First-Out) because it does not follow the stack property.",
                "explanation": "Belady's Anomaly is the phenomenon where increasing the number of page frames results in an increase in the number of page faults. It occurs in FIFO page replacement because FIFO is not a stack-based algorithm (it does not satisfy the property where the set of pages in memory for $n$ frames is a subset of pages in memory for $n+1$ frames)."
            }
        ]

        short_questions = [
            {
                "question": "Explain the difference between a Mutex and a Binary Semaphore in detail.",
                "sample_answer": "1. **Ownership**: A Mutex has a strict concept of ownership. The thread that locks the Mutex is the only thread allowed to unlock it. A Binary Semaphore has no owner; any thread can signal and release a thread waiting on it.\n2. **Use Case**: Mutexes are designed specifically to achieve mutual exclusion for a critical section. Binary Semaphores are signaling mechanisms used to synchronize task execution or signal event occurrences.\n3. **Safety Features**: Because Mutexes have owners, they can implement safety features like priority inheritance to avoid priority inversion. Semaphores do not support priority inheritance.",
                "explanation": "The evaluator will look for: (1) **Ownership** concept (Mutex has an owner, Semaphore does not), (2) **Mutual exclusion locking** vs. **general signaling**, (3) **Priority inversion/priority inheritance** support."
            },
            {
                "question": "What is a Translation Lookaside Buffer (TLB)? Explain its function and role in address translation.",
                "sample_answer": "A Translation Lookaside Buffer (TLB) is a high-speed, hardware associative cache located inside the CPU's Memory Management Unit (MMU). It stores a small number of recent virtual-to-physical page translations. \nWhen the CPU requests a logical address, the MMU checks the TLB first (a TLB hit). If found, translation is instant. If not (a TLB miss), the MMU must perform a full page table walk in main memory, which takes two or more memory accesses (one to read the page table entry, one to read actual data). The TLB is used to reduce this translation latency and speed up instruction execution.",
                "explanation": "The answer must cover: (1) **Hardware cache** definition, (2) **TLB Hit vs. TLB Miss** mechanics, (3) **Reducing memory latency** (avoiding double memory access)."
            },
            {
                "question": "Define a Race Condition. How does it occur, and what is the standard method to prevent it?",
                "sample_answer": "A Race Condition is an undesirable situation that occurs when multiple processes or threads access and manipulate shared data concurrently, and the final outcome of the execution depends entirely on the relative order or timing of their execution.\nIt occurs when at least one thread modifies the shared variable without proper synchronization, leaving the data in an inconsistent state. To prevent race conditions, the critical sections of code that access shared variables must be executed in a mutually exclusive manner, using synchronization mechanisms like Mutex locks, Semaphores, or monitor blocks.",
                "explanation": "Key grading points: (1) **Concurrent access to shared data**, (2) **Outcome depends on execution timing**, (3) **Mutual exclusion / lock synchronization** as the prevention method."
            },
            {
                "question": "Contrast Internal Fragmentation and External Fragmentation. Provide examples of memory schemes where each occurs.",
                "sample_answer": "- **Internal Fragmentation**: Occurs when physical memory is divided into fixed-size partitions. A process is allocated a partition larger than its request, leaving unused memory space inside the allocated block. Example: **Paging** (wasted space in the last page frame) or **Static Partitioning**.\n- **External Fragmentation**: Occurs when physical memory is allocated dynamically. As processes load and terminate, free memory is broken into tiny, non-contiguous slots. There is enough total free space to satisfy a process request, but it cannot be used because it is not contiguous. Example: **Segmentation** or **Dynamic Partitioning**.",
                "explanation": "Ensure you contrast: (1) **Location of wasted memory** (inside allocated block vs. outside/between blocks), (2) **Fixed vs. Variable partitioning**, (3) **Typical memory schemes** (Paging for internal, Segmentation for external)."
            },
            {
                "question": "Explain the difference between Logical (Virtual) Address Space and Physical Address Space. How are they mapped?",
                "sample_answer": "1. **Logical (Virtual) Address Space**: The set of all virtual addresses that a CPU generates during program execution. It is logical because it exists from the perspective of the running process, isolated from physical RAM.\n2. **Physical Address Space**: The set of all physical addresses in the hardware memory (RAM) unit where instructions and data actually reside.\n3. **Mapping**: The translation from logical to physical addresses is handled dynamically at run-time by a hardware component called the **Memory Management Unit (MMU)**. The MMU uses base registers, page tables, or segment tables to translate virtual addresses on the fly.",
                "explanation": "The answer must define: (1) **Logical address** as CPU-generated, (2) **Physical address** as RAM hardware locations, (3) **MMU** (Memory Management Unit) as the component translating them."
            }
        ]

        viva_questions = [
            {
                "question": "What is the consequence of leaving deadlocks unhandled in a system? How does a general-purpose OS handle them?",
                "sample_answer": "If deadlocks are unhandled, the locked processes will remain frozen indefinitely, keeping their allocated resources occupied and unavailable to other processes. This causes system performance to degrade over time, eventually requiring a manual system reboot.\nTo avoid the high computational cost of constant deadlock avoidance algorithms, most general-purpose operating systems (like Windows, Linux, and macOS) employ the **Ostrich Algorithm**, which ignores the problem entirely under the assumption that deadlocks occur rarely enough that the cost of handling them exceeds the cost of a reboot.",
                "explanation": "Explain that: (1) **Resources stay locked, processes freeze**, (2) **Manual reboot is needed**, (3) **Ostrich Algorithm** is the standard approach used by modern OSs (ignoring the deadlock for performance reasons)."
            },
            {
                "question": "Is the Banker's Algorithm practical to run in a real operating system? Justify your answer with two key limitations.",
                "sample_answer": "No, the Banker's Algorithm is highly impractical for real-world operating systems due to two major limitations:\n1. **A priori knowledge**: It requires all processes to declare their maximum resource claims in advance before execution begins, which is impossible in a dynamic, multi-tasking OS.\n2. **Dynamic process changes**: It assumes processes are fixed in number and resources do not change dynamically. Additionally, running safety state checks ($O(m \\cdot n^2)$ overhead) on every resource request would cause severe CPU bottlenecking.",
                "explanation": "Justification must detail: (1) **Difficulty of knowing max resource claims in advance**, (2) **Severe CPU performance overhead** of safety checks in a dynamic system."
            },
            {
                "question": "Why must page sizes always be powers of 2? Explain the mathematical advantage in address translation.",
                "sample_answer": "Page sizes must be powers of 2 (such as 4KB, which is $2^{12}$ bytes) because it simplifies the hardware design of the Memory Management Unit (MMU). \nSpecifically, it allows address translation to occur without mathematical division or multiplication. By using powers of 2, a logical address can be split directly into bits. For a 32-bit address with 4KB page size ($2^{12}$), the lower 12 bits represent the page offset, and the upper 20 bits represent the page number. Translation is done instantly using simple bitwise shifts.",
                "explanation": "Key explanation points: (1) **Simplifying hardware design**, (2) **Avoiding division/multiplication**, (3) **Bit division** (upper bits for page number, lower bits for offset)."
            },
            {
                "question": "Describe what occurs during a context switch. What is its main drawback?",
                "sample_answer": "During a context switch, the OS halts the currently executing process and saves its state (including CPU registers, program counter, stack pointer, and memory mappings) into its Process Control Block (PCB). It then loads the saved state of the next scheduled process from its PCB into the CPU registers, enabling execution to resume.\nThe main drawback is **system overhead**. Context switching does not perform any useful real-world work; it consumes CPU cycles saving and loading states, flushing CPU caches, and reloading TLB tables, which slows down the system.",
                "explanation": "Describe: (1) **Saving current state to PCB**, (2) **Loading new state from PCB**, (3) **Overhead penalty** (cache invalidation, TLB flush, wasted CPU cycles)."
            },
            {
                "question": "Differentiate between preemptive and non-preemptive CPU scheduling. Which is preferred for time-sharing systems?",
                "sample_answer": "- **Preemptive Scheduling**: The operating system can interrupt a currently running process at any time (e.g., on a timer interrupt or priority arrival) and allocate the CPU to another process. This is preferred for time-sharing/interactive systems (like Windows/Linux) because it guarantees responsiveness and prevents starvation.\n- **Non-Preemptive Scheduling**: Once a process is allocated the CPU, it keeps running until it voluntarily relinquishes control (by blocking for I/O or terminating). It is simple but can cause long processes to block others indefinitely.",
                "explanation": "Contrast: (1) **Forcible interruption** (preemptive) vs. **runs until voluntary release** (non-preemptive), (2) **Time-sharing preference** (preemptive scheduling is required for interactive responsiveness)."
            }
        ]

        # Select corresponding list
        if quiz_type.lower() == "mcq":
            return mcq_questions[:count]
        elif quiz_type.lower() == "short":
            return short_questions[:count]
        else:
            return viva_questions[:count]
