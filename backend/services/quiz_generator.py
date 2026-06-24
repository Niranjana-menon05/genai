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
                format_instructions = """Each question must be multiple choice. You MUST return a JSON array of objects, where each object has:
- "question": The question text.
- "options": An array of exactly 4 strings.
- "correct_answer": The exact string of the correct option.
- "explanation": A detailed explanation of why the answer is correct and others are incorrect, verified for exam accuracy."""
            elif quiz_type.lower() == "short":
                format_instructions = """Each question must be a short answer question. Return a JSON array of objects, where each object has:
- "question": The question text.
- "sample_answer": A concise, ideal exam-style answer (2-4 sentences).
- "explanation": An explanation of key concepts the grading evaluator will look for."""
            else:  # Viva
                format_instructions = """Each question must be a typical viva-voce/oral examination question. Return a JSON array of objects, where each object has:
- "question": The question text.
- "sample_answer": A quick, conversational, punchy response (1-2 sentences) that demonstrates deep understanding.
- "explanation": Extra background knowledge or tip on how to impress the examiner."""

            prompt_template = ChatPromptTemplate.from_messages([
                ("system", f"""You are an educational assessment expert. Generate a quiz of exactly {count} {quiz_type.upper()} questions of {difficulty.upper()} difficulty based on the provided document context.
                
{format_instructions}

Ensure the output is valid JSON only, inside a code block or as raw text. Do not write any conversational intro or outro. Use double quotes for JSON keys and values. Escape any double quotes inside text.

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
        
        for s in raw_sentences:
            s_clean = s.strip()
            if 30 < len(s_clean) < 180 and not any(x in s_clean.lower() for x in ("page break", "slide break", "table data", "---")):
                # Split at standard definition points
                parts = re.split(r'\bis\b|\bare\b|\brefers to\b|\bmeans\b|:| - ', s_clean, maxsplit=1, flags=re.IGNORECASE)
                if len(parts) == 2:
                    sub = parts[0].strip()
                    pred = parts[1].strip()
                    # Clean subject (remove leading bullet marks or numbers)
                    sub = re.sub(r'^[\d\.\-\*#\s\(\)]+', '', sub).strip()
                    
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
                    if quiz_type.lower() == "mcq":
                        generated.append({
                            "question": f"Based on your notes, which of the following completes: '{keyword} ...'?",
                            "options": [rest, "a fundamental component of the algorithm.", "an optimized resource constraint.", "scheduling queue parameters."],
                            "correct_answer": rest,
                            "explanation": f"Source document text: '{s}'."
                        })
                    else:
                        generated.append({
                            "question": f"Explain the context of: '{keyword}' from your reading material.",
                            "sample_answer": s,
                            "explanation": f"Source notes state: '{s}'."
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
            if quiz_type.lower() == "mcq":
                # Correct option is the predicate
                correct_ans = pred
                
                # Distractors are other predicates from the document
                other_preds = [p for p in all_predicates if p != pred]
                random.shuffle(other_preds)
                distractors = other_preds[:3]
                
                # Pad distractors if needed
                while len(distractors) < 3:
                    distractors.append(f"A conceptual mechanism described in the {sub} module.")
                    
                options = [correct_ans] + distractors
                random.shuffle(options)
                
                generated.append({
                    "question": f"Based on your study notes, what is the description or function of **'{sub}'**?",
                    "options": options,
                    "correct_answer": correct_ans,
                    "explanation": f"According to your materials: '{full_sentence}'"
                })
            elif quiz_type.lower() == "short":
                generated.append({
                    "question": f"Based on your lecture notes, define or explain: **'{sub}'**.",
                    "sample_answer": f"{sub} is {pred}.",
                    "explanation": f"Your explanation should include: '{pred}'."
                })
            else:  # viva
                generated.append({
                    "question": f"If asked in a viva voce: 'What do you understand by the term **\"{sub}\"**?', how would you respond?",
                    "sample_answer": f"According to our notes, it is {pred}.",
                    "explanation": f"Impress the examiner by stating that it is: '{pred}'."
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
                "explanation": "According to the Coffman conditions, 'No Preemption' is the necessary condition. If resources can be preempted (taken away), deadlocks can be resolved or prevented."
            },
            {
                "question": "What memory allocation problem does Paging solve?",
                "options": [
                    "Internal Fragmentation",
                    "External Fragmentation",
                    "Belady's Anomaly",
                    "Page Fault Overhead"
                ],
                "correct_answer": "External Fragmentation",
                "explanation": "Paging avoids external fragmentation by dividing physical memory into fixed-sized frames and logical memory into pages, allowing non-contiguous allocation. However, paging can still suffer from minor internal fragmentation in the last page frame."
            },
            {
                "question": "In the Banker's Algorithm, which of the following represents the allocation state?",
                "options": [
                    "Need = Max - Allocation",
                    "Allocation = Max + Need",
                    "Available = Max - Need",
                    "Need = Allocation - Max"
                ],
                "correct_answer": "Need = Max - Allocation",
                "explanation": "The safety matrix calculation in the Banker's Algorithm defines the Need vector/matrix as the maximum potential resource demand minus the currently allocated resources: Need = Max - Allocation."
            },
            {
                "question": "Which CPU scheduling algorithm guarantees the minimum average waiting time?",
                "options": [
                    "Round Robin (RR)",
                    "Shortest Job First (SJF)",
                    "First-Come First-Served (FCFS)",
                    "Priority Scheduling"
                ],
                "correct_answer": "Shortest Job First (SJF)",
                "explanation": "Shortest Job First (SJF) scheduling is provably optimal. By scheduling the process with the shortest burst time first, it minimizes the average waiting time for a given set of processes."
            },
            {
                "question": "Belady's Anomaly is most commonly observed in which of the following page replacement algorithms?",
                "options": [
                    "LRU (Least Recently Used)",
                    "Optimal Page Replacement",
                    "FIFO (First-In, First-Out)",
                    "LFU (Least Frequently Used)"
                ],
                "correct_answer": "FIFO (First-In, First-Out)",
                "explanation": "Belady's Anomaly is the phenomenon where increasing the number of page frames results in an increase in the number of page faults. It occurs in FIFO page replacement but not in stack-based algorithms like LRU."
            }
        ]

        short_questions = [
            {
                "question": "Explain the difference between a mutex and a binary semaphore.",
                "sample_answer": "A mutex lock is owned by the process/thread that acquires it, meaning only the thread that locked the mutex can unlock it. A binary semaphore, however, does not have the concept of ownership; any thread can trigger a signal() operation to release a thread waiting on a wait() operation.",
                "explanation": "Evaluators look for the concept of 'Ownership'. A mutex is a locking mechanism, whereas a semaphore is a signaling mechanism."
            },
            {
                "question": "What is a Translation Lookaside Buffer (TLB) and why is it used?",
                "sample_answer": "A TLB is a high-speed associative hardware cache. It stores recent virtual-to-physical page translations. It is used to reduce the memory access time since a standard page table lookup requires two memory accesses (one for the table and one for the data).",
                "explanation": "Ensure you mention 'hardware cache', 'speeding up translations', and avoiding 'two memory accesses'."
            },
            {
                "question": "What is race condition?",
                "sample_answer": "A race condition is an undesirable situation that occurs when multiple threads or processes access and manipulate shared data concurrently, and the final outcome of the execution depends on the specific order or timing in which the accesses occur.",
                "explanation": "Highlight 'concurrent access', 'shared data', and 'outcome depending on execution order'."
            },
            {
                "question": "Describe the main difference between internal and external fragmentation.",
                "sample_answer": "Internal fragmentation occurs when memory partitions are fixed-size and a process is allocated a partition larger than it needs, leaving unused space inside the allocated block. External fragmentation occurs when memory is variable-size and there is enough total free memory to satisfy a process request, but the memory is divided into small, non-contiguous blocks.",
                "explanation": "Contrast fixed partitioning (internal) with dynamic partitioning (external) and define where the wasted memory resides."
            },
            {
                "question": "What are virtual addresses and physical addresses?",
                "sample_answer": "A virtual (logical) address is generated by the CPU during execution, representing the address space of a process. A physical address is the actual physical location in primary memory (RAM) where the instruction or data resides. The MMU handles the mapping between the two.",
                "explanation": "Differentiate CPU-generated (logical/virtual) from RAM-resident (physical) and credit the MMU for mapping."
            }
        ]

        viva_questions = [
            {
                "question": "What will happen if we don't handle deadlocks in a system?",
                "sample_answer": "The system will lock up, processes will freeze, and resources will remain occupied indefinitely until the system is manually restarted or process tasks are killed.",
                "explanation": "Give a direct answer indicating process freezing and the necessity of rebooting."
            },
            {
                "question": "Is the Banker's Algorithm practical to run in a general-purpose OS? Why?",
                "sample_answer": "No, it is not practical. It requires knowing the maximum resource demands of all processes in advance, which is rarely possible, and running the safety algorithm has high computational overhead.",
                "explanation": "Focus on the constraint of knowing 'maximum demands in advance' and the performance cost."
            },
            {
                "question": "Can page size be arbitrary? Why or why not?",
                "sample_answer": "No, page sizes must be powers of 2 (typically 4KB to 64KB) because it simplifies hardware address translation—allowing bitwise shifts instead of division.",
                "explanation": "Point out 'powers of 2' and the hardware convenience of separating page number and offset without arithmetic."
            },
            {
                "question": "What is a context switch?",
                "sample_answer": "It is the process of storing the state of a CPU process/thread so that it can be restored and execution resumed later, enabling multiple processes to share a single CPU.",
                "explanation": "Highlight saving/restoring CPU state (registers, program counter) and enabling concurrency."
            },
            {
                "question": "What is the difference between preemptive and non-preemptive scheduling?",
                "sample_answer": "In preemptive scheduling, the OS can interrupt a running process and reallocate the CPU to another process. In non-preemptive scheduling, once a process gets the CPU, it holds it until it voluntary releases it or terminates.",
                "explanation": "Use terms like 'forcibly interrupt' vs 'runs to completion/voluntary yield'."
            }
        ]

        # Select corresponding list
        if quiz_type.lower() == "mcq":
            return mcq_questions[:count]
        elif quiz_type.lower() == "short":
            return short_questions[:count]
        else:
            return viva_questions[:count]
