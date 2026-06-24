import os
import json
from typing import List, Dict, Any, Optional
from backend import config

# Lazily import LangChain and Groq to avoid overhead or startup errors in mock mode
_chat_model = None

def get_groq_model():
    global _chat_model
    if _chat_model is None:
        if config.IS_MOCK_MODE:
            return None
        try:
            from langchain_groq import ChatGroq
            # Using llama-3.3-70b-versatile as it has high quality and large context
            _chat_model = ChatGroq(
                api_key=config.GROQ_API_KEY,
                model_name="llama-3.3-70b-versatile",
                temperature=0.2,
                max_tokens=4096
            )
            print("ChatGroq Model (llama-3.3-70b-versatile) initialized successfully.")
        except Exception as e:
            print(f"Error initializing ChatGroq: {e}")
            print("Falling back to Mock mode for Study Assistant Agent.")
            _chat_model = None
    return _chat_model


class StudyAssistantAgent:
    @classmethod
    def answer_question(cls, query: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Answers user query based on context retrieved from vector store."""
        # 1. Prepare context text
        context_text = ""
        sources = []
        for chunk in context_chunks:
            source_name = chunk["metadata"].get("filename", "Unknown Document")
            page_info = f" (Page {chunk['metadata'].get('page_number')})" if "page_number" in chunk["metadata"] else ""
            slide_info = f" (Slide {chunk['metadata'].get('slide_number')})" if "slide_number" in chunk["metadata"] else ""
            
            context_text += f"Source: {source_name}{page_info}{slide_info}\nContent: {chunk['text']}\n\n"
            
            # Save unique sources
            source_desc = f"{source_name}{page_info}{slide_info}"
            if source_desc not in sources:
                sources.append(source_desc)

        # 2. Check for Mock Mode
        if config.IS_MOCK_MODE or not get_groq_model():
            if context_chunks:
                simulated_response = cls._generate_dynamic_mock_answer(query, context_chunks, sources)
            else:
                simulated_response = cls._generate_mock_answer(query, context_text, sources)
            return {
                "answer": simulated_response,
                "sources": sources,
                "mode": "mock"
            }

        # 3. Live LLM execution
        try:
            model = get_groq_model()
            from langchain_core.prompts import ChatPromptTemplate
            
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", """You are a helpful, expert AI Study Assistant. Your task is to answer the student's question based strictly on the provided context.
                
Guidelines:
1. Use only the provided context to answer the question. If the answer cannot be found in the context, state that clearly (do not make up information).
2. Answer in a structured, professional, and educational format. Use bullet points, bold text, and numbered lists where appropriate to make the notes easy to study.
3. Keep the answer comprehensive yet concise.
4. Mention the source file name and page/slide details (which will be in the context header) when referencing facts.

Context:
{context}"""),
                ("human", "{question}")
            ])
            
            chain = prompt_template | model
            print(f"Running LLM chain for query: '{query}'...")
            response = chain.invoke({
                "context": context_text if context_text else "No relevant document chunks found in database.",
                "question": query
            })
            
            return {
                "answer": response.content,
                "sources": sources,
                "mode": "live"
            }
        except Exception as e:
            print(f"Error during live query answering: {e}")
            if context_chunks:
                simulated_response = cls._generate_dynamic_mock_answer(query, context_chunks, sources)
            else:
                simulated_response = cls._generate_mock_answer(query, context_text, sources)
            return {
                "answer": f"*[Live API Error: {str(e)}. Falling back to local helper]*\n\n" + simulated_response,
                "sources": sources,
                "mode": "fallback_mock"
            }

    @classmethod
    def generate_summary(cls, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generates a high-level summary of the retrieved document chunks."""
        context_text = "\n\n".join([f"Content Chunk: {c['text']}" for c in context_chunks])
        
        if config.IS_MOCK_MODE or not get_groq_model():
            if context_chunks:
                summary = cls._generate_dynamic_mock_summary_only(context_chunks)
            else:
                summary = cls._generate_mock_summary(context_text)
            return {
                "summary": summary,
                "mode": "mock"
            }
            
        try:
            model = get_groq_model()
            from langchain_core.prompts import ChatPromptTemplate
            
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", """You are an academic study assistant. Generate a clear, structured summary of the lecture notes/materials provided in the context.
                
Structure your response as follows:
- **Title**: A suitable descriptive title for the summarized content.
- **Key Concepts Overview**: A bulleted list outlining 3-5 core themes/concepts.
- **Detailed Summary**: A detailed, cohesive summary of the main points (broken down into subheadings if necessary).
- **Core Takeaways**: 2-3 essential highlights that are highly likely to appear in exams."""),
                ("human", "Summarize this lecture material:\n\n{context}")
            ])
            
            chain = prompt_template | model
            response = chain.invoke({"context": context_text})
            
            return {
                "summary": response.content,
                "mode": "live"
            }
        except Exception as e:
            if context_chunks:
                simulated_summary = cls._generate_dynamic_mock_summary_only(context_chunks)
            else:
                simulated_summary = cls._generate_mock_summary(context_text)
            return {
                "summary": f"*[Live API Error: {str(e)}. Falling back to mock summary]*\n\n" + simulated_summary,
                "mode": "fallback_mock"
            }

    @classmethod
    def generate_revision_notes(cls, topic: str, context_chunks: List[Dict[str, Any]], note_type: str) -> Dict[str, Any]:
        """Generates focused revision notes (e.g. Exam Guide, Cheat Sheet, Short Summary)."""
        context_text = "\n\n".join([f"Content Chunk: {c['text']}" for c in context_chunks])
        
        if config.IS_MOCK_MODE or not get_groq_model():
            if context_chunks:
                notes = cls._generate_dynamic_mock_notes(topic, note_type, context_chunks)
            else:
                notes = cls._generate_mock_revision_notes(topic, note_type)
            return {
                "notes": notes,
                "mode": "mock"
            }
            
        try:
            model = get_groq_model()
            from langchain_core.prompts import ChatPromptTemplate
            
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", """You are an expert tutor creating study materials for students preparing for exams.
                Create a specialized "{note_type}" on the topic of "{topic}" using the uploaded material context below.
                
Styles:
- If 'Exam Guide': Provide deep explanations, typical question patterns, and step-by-step solutions or explanations.
- If 'Cheat Sheet': Keep it extremely concise, list key formulas, terms, quick definitions, and bulleted bullet summaries.
- If 'Short Summary': Provide a high-level executive summary of the concepts, with a 'Quick Recall' section.
                
Use rich formatting: lists, code/equation blocks, bold highlights, and tables where applicable."""),
                ("human", "Topic: {topic}\n\nContext:\n{context}")
            ])
            
            chain = prompt_template | model
            response = chain.invoke({
                "note_type": note_type,
                "topic": topic,
                "context": context_text if context_text else "No specific documents uploaded."
            })
            
            return {
                "notes": response.content,
                "mode": "live"
            }
        except Exception as e:
            if context_chunks:
                simulated_notes = cls._generate_dynamic_mock_notes(topic, note_type, context_chunks)
            else:
                simulated_notes = cls._generate_mock_revision_notes(topic, note_type)
            return {
                "notes": f"*[Live API Error: {str(e)}. Falling back to mock revision notes]*\n\n" + simulated_notes,
                "mode": "fallback_mock"
            }

    # --- Dynamic RAG Helpers for Offline/Mock Mode ---

    @classmethod
    def _generate_dynamic_mock_answer(cls, query: str, chunks: List[Dict[str, Any]], sources: List[str]) -> str:
        text_pieces = []
        for chunk in chunks[:3]:
            text_pieces.append(chunk["text"])
        combined_text = "\n".join(text_pieces)
        
        # Split sentences
        raw_sentences = combined_text.replace("\n", " ").split(".")
        sentences = []
        for s in raw_sentences:
            s_clean = s.strip()
            if len(s_clean) > 20 and not any(x in s_clean.lower() for x in ("page break", "slide break", "table data", "---")):
                sentences.append(s_clean)

        answer = f"### Study Assistant Response (Mock RAG Mode)\n\n"
        answer += f"Based on the content retrieved from your documents for **\"{query}\"**, here are the key highlights:\n\n"
        
        bullets = 0
        for s in sentences:
            if bullets >= 4:
                break
            answer += f"* **Concept Detail**: {s}.\n"
            bullets += 1
            
        if bullets == 0:
            answer += f"* **Context Content**: {combined_text[:300]}...\n"

        snippet = chunks[0]["text"]
        if len(snippet) > 200:
            snippet = snippet[:300].strip() + "..."
        answer += f"\n\n**Direct Extract from source:**\n> {snippet}\n"
        
        sources_text = "\n*Sources used: " + (", ".join(sources) if sources else "Uploaded Materials") + "*"
        answer += sources_text
        answer += "\n\n*Note: Running in offline Mock Mode. Real text extraction was matched using local keyword RAG index.*"
        return answer

    @classmethod
    def _generate_dynamic_mock_summary_only(cls, chunks: List[Dict[str, Any]]) -> str:
        text_pieces = []
        for chunk in chunks[:4]:
            text_pieces.append(chunk["text"])
        combined_text = "\n".join(text_pieces)
        
        raw_sentences = combined_text.replace("\n", " ").split(".")
        sentences = []
        for s in raw_sentences:
            s_clean = s.strip()
            if len(s_clean) > 20 and not any(x in s_clean.lower() for x in ("page break", "slide break", "table data", "---")):
                sentences.append(s_clean)

        summary = "## Dynamic Lecture Summary (Mock Mode)\n\n"
        summary += "### Key Concepts Overview\n"
        
        bullets = 0
        for s in sentences:
            if bullets >= 4:
                break
            summary += f"* {s}.\n"
            bullets += 1
            
        if bullets == 0:
            summary += f"* Found source content length: {len(combined_text)} characters.\n"

        summary += "\n### Detailed Summary Extract\n"
        paragraphs = []
        for c in chunks[:2]:
            cleaned_chunk = c["text"].strip()
            if len(cleaned_chunk) > 100:
                paragraphs.append(cleaned_chunk[:350] + "...")
        summary += "\n\n".join(paragraphs)
        
        summary += "\n\n---\n*Note: Compiled in offline Mock Mode using local text parser.*"
        return summary

    @classmethod
    def _generate_dynamic_mock_notes(cls, topic: str, note_type: str, chunks: List[Dict[str, Any]]) -> str:
        text_pieces = []
        for chunk in chunks[:4]:
            text_pieces.append(chunk["text"])
        combined_text = "\n".join(text_pieces)
        
        raw_sentences = combined_text.replace("\n", " ").split(".")
        sentences = []
        for s in raw_sentences:
            s_clean = s.strip()
            if len(s_clean) > 20 and not any(x in s_clean.lower() for x in ("page break", "slide break", "table data", "---")):
                sentences.append(s_clean)

        notes = f"# Revision Notes ({note_type}): {topic}\n\n"
        notes += f"This summary has been compiled directly from the retrieved sections of your uploaded lecture files.\n\n"
        
        notes += "## Core Concepts Found\n"
        bullets = 0
        for s in sentences:
            if bullets >= 5:
                break
            notes += f"* **Key Point**: {s}.\n"
            bullets += 1
            
        if bullets == 0:
            notes += f"* Context contents: {combined_text[:250]}...\n"

        notes += "\n## Detailed Summary\n"
        paragraphs = []
        for chunk in chunks[:2]:
            cleaned_chunk = chunk["text"].strip()
            if len(cleaned_chunk) > 100:
                paragraphs.append(cleaned_chunk[:400] + "...")
        notes += "\n\n".join(paragraphs)
            
        notes += "\n\n---\n*Note: Since you are running in offline/Mock Mode, this summary was constructed using an on-the-fly keyword extractor from your document.*"
        return notes

    # --- Simulated Responses for Mock Mode ---
    
    @staticmethod
    def _generate_mock_answer(query: str, context: str, sources: List[str]) -> str:
        q = query.lower()
        
        sources_text = "\n*Sources used: " + (", ".join(sources) if sources else "Default Syllabus Guide") + "*"
        
        if "deadlock" in q:
            return f"""### Understanding Deadlocks

Based on your lecture notes, a **Deadlock** is a state in operating systems where a set of processes are blocked because each process is holding a resource and waiting for another resource held by some other process in the set.

#### The 4 Necessary Conditions for Deadlock (Coffman Conditions)
For a deadlock to occur, all four of the following conditions must hold simultaneously:

1. **Mutual Exclusion**: At least one resource must be held in a non-shareable mode (only one process can use the resource at a time).
2. **Hold and Wait**: A process must be holding at least one resource and waiting to acquire additional resources that are currently being held by other processes.
3. **No Preemption**: Resources cannot be preempted; a resource can be released only voluntarily by the process holding it, after that process has completed its task.
4. **Circular Wait**: A closed chain of processes exists, where each process holds one or more resources that are needed by the next process in the chain.

```
Example Cycle:
Process P1 holds Resource R1 and requests Resource R2.
Process P2 holds Resource R2 and requests Resource R1.
--> Both processes are blocked indefinitely!
```

#### How to Handle Deadlocks
Operating systems typically use one of three strategies:
* **Deadlock Prevention**: Design the system to ensure that at least one of the Coffman conditions can never hold.
* **Deadlock Avoidance**: The OS dynamically decides whether to grant a resource request based on whether it keeps the system in a *safe state* (e.g., using the **Banker's Algorithm**).
* **Detection and Recovery**: Allow deadlocks to occur, detect them using a Wait-For Graph, and recover by aborting processes or preempting resources.
{sources_text}"""

        elif "synchronization" in q or "process sync" in q or "critical section" in q:
            return f"""### Process Synchronization & The Critical Section Problem

In multitasking operating systems, **Process Synchronization** is the coordination of execution of multiple processes to ensure that they do not corrupt shared data (leading to race conditions).

#### The Critical Section
A **Critical Section** is a code segment in a process that accesses shared resources (like shared variables, files, or hardware devices) and must not be concurrently accessed by other processes.

#### Requirements for a Valid Solution
Any solution to the Critical Section problem must satisfy three requirements:
1. **Mutual Exclusion**: If process \\(P_i\\) is executing in its critical section, then no other processes can be executing in their critical sections.
2. **Progress**: If no process is executing in its critical section and some processes wish to enter, only those processes that are not executing in their remainder sections can participate in deciding which process enters next, and this selection cannot be postponed indefinitely.
3. **Bounded Waiting**: There must be a limit on the number of times that other processes are allowed to enter their critical sections after a process has made a request to enter and before that request is granted.

#### Standard Synchronization Tools
* **Semaphores**: An integer variable accessed via two standard atomic operations: `wait()` (or `P`) and `signal()` (or `V`).
* **Mutex Locks**: A boolean variable used to protect critical sections by letting a process acquire a lock before entering and release it upon exiting.
* **Monitors**: A high-level programming language construct that provides equivalent functionality with cleaner structure, preventing manual semaphore errors.
{sources_text}"""

        elif "module 3" in q or "mod 3" in q:
            return f"""### Summary of Module 3: Memory Management

Based on standard computer science curricula in your uploaded files, Module 3 covers **Memory Management Strategies** used by operating systems to manage primary memory (RAM).

#### Key Topics Covered

1. **Logical vs. Physical Address Space**
   * **Logical Address**: Generated by the CPU; also referred to as a virtual address.
   * **Physical Address**: The actual address seen by the memory unit (hardware register).
   * **MMU (Memory Management Unit)**: The hardware device that maps logical addresses to physical addresses at runtime.

2. **Swapping**
   * A process can be swapped temporarily out of memory to a backing store (disk) and then brought back into memory for continued execution. This allows the total physical address space of processes to exceed physical memory.

3. **Contiguous Memory Allocation**
   * **Fixed Partitioning**: Memory is divided into fixed-sized blocks. Leads to **Internal Fragmentation** (wasted space inside an allocated block).
   * **Dynamic Partitioning**: Memory is allocated dynamically based on process size. Leads to **External Fragmentation** (total free memory is sufficient, but it is not contiguous).
   * *Allocation Strategies*: First-Fit, Best-Fit, and Worst-Fit.

4. **Paging**
   * A non-contiguous allocation scheme. Physical memory is broken into fixed-sized blocks called **Frames**, and logical memory is divided into blocks of the same size called **Pages**.
   * Eliminates external fragmentation, but can still have small internal fragmentation in the last frame of a process.
   * **Page Table**: Maps page numbers to frame numbers.
{sources_text}"""

        else:
            # General fallback answer
            return f"""### Study Assistant Response

Thank you for your question: **"{query}"**. 

Based on the context retrieved from your uploaded academic documents, here are the key aspects relating to your query:

* **Core Definition**: The materials describe this concept as fundamental to understanding the overall module.
* **Key Components**:
  1. *Resource Constraints*: System configurations require careful scheduling.
  2. *Operation Flows*: Sequential processing avoids data conflicts.
  3. *Optimization*: Proper parameters yield faster execution times.
* **Exam Relevance**: Typical questions on this topic ask to compare alternative approaches or solve numerical problems based on given scheduling timelines.

*Note: For more specific answers, ensure your uploaded documents contain the exact terms and details you are inquiring about.*
{sources_text}"""

    @staticmethod
    def _generate_mock_summary(context: str) -> str:
        return """## Lecture Notes Summary: Operating Systems Overview

### Key Concepts Overview
* **Process Management**: CPU scheduling, states of processes, and thread management.
* **Process Synchronization**: Critical sections, Semaphores, and Mutexes.
* **Deadlock Handling**: Coffman conditions, Prevention, Avoidance, and Detection.
* **Memory Management**: Paging, Segmentation, and Virtual Memory.

### Detailed Summary
The provided academic materials lay out the foundation of modern Operating Systems (OS). An operating system acts as an intermediary between a user of a computer and the computer hardware, with the goal of executing user programs in an efficient and convenient manner.

A significant portion of the materials focuses on concurrency. When multiple processes run concurrently, they may share variables or memory spaces. Without synchronization, this leads to **Race Conditions** where the final output depends on the arbitrary order of execution. Solutions like **Semaphores** (both binary and counting) are explained, detailing the atomic operations of wait and signal.

Furthermore, resource allocation issues are discussed, specifically **Deadlocks**. A deadlock locks the system when processes wait circular-wise for resource releases. The **Banker's Algorithm** is highlighted as a primary mechanism for deadlock avoidance, ensuring the system stays in a "Safe State".

### Core Takeaways
1. **Process Sync**: Mutual exclusion must be guaranteed in critical sections to prevent data corruption.
2. **Coffman Conditions**: Memorize Mutual Exclusion, Hold & Wait, No Preemption, and Circular Wait. If you break even one, deadlock is prevented.
3. **Paging**: Paging solves external fragmentation by dividing physical memory into frames and virtual memory into pages.
"""

    @staticmethod
    def _generate_mock_revision_notes(topic: str, note_type: str) -> str:
        if note_type == "Cheat Sheet":
            return f"""# Quick Revision Cheat Sheet: {topic}

## Core Definitions
* **{topic}**: The primary mechanism/concept discussed in this module.
* **Throughput**: Number of processes completed per unit time.
* **Turnaround Time**: Time interval from submission of a process to its completion.
* **Response Time**: Time from submission until the first response is produced.

## Important Formulas & Algorithms
1. **CPU Scheduling - Turnaround Time Formula**:
   \\\\[ T_{tat} = T_{completion} - T_{arrival} \\\\]
2. **Waiting Time Formula**:
   \\\\[ T_{waiting} = T_{tat} - T_{burst} \\\\]
3. **Safe State Condition (Banker's Algorithm)**:
   \\\\[ \\\\text{Need}[i][j] = \\\\text{Max}[i][j] - \\\\text{Allocation}[i][j] \\\\]
   *Ensure \\\\(\\\\text{Need}[i] \\\\le \\\\text{Available}\\\\) to execute.*

## Must-Remember Checklist
- [x] Context switching overhead is caused by saving and loading registers.
- [x] Semaphores are integer variables, Mutexes are boolean locks.
- [x] Banker's algorithm is resource-allocation state detection.
- [x] Belady's Anomaly occurs in FIFO page replacement, where adding page frames leads to more page faults.
"""
        elif note_type == "Exam Guide":
            return f"""# Exam Prep Guide: {topic}

## Probable Exam Questions

### Question 1: Explain the Banker's Algorithm with an example. (8 Marks)
**Expected Answer Outline**:
1. **Definition**: An algorithm used for deadlock avoidance in resource allocation.
2. **Data Structures**:
   * `Available[m]`: Available resources of each type.
   * `Max[n][m]`: Maximum demand of each process.
   * `Allocation[n][m]`: Resources currently allocated to each process.
   * `Need[n][m]`: Remaining resources needed. Formula: `Need = Max - Allocation`.
3. **Safety Algorithm**: Run simulation to see if there is an execution sequence (Safe Sequence) where all processes can finish.
4. **Example Walkthrough**: (Provide matrix arithmetic showing allocation, availability, and process completion sequence).

---

### Question 2: Differentiate between Paging and Segmentation. (6 Marks)

| Feature | Paging | Segmentation |
| :--- | :--- | :--- |
| **Page/Block Size** | Fixed size (determined by hardware). | Variable size (determined by program structure). |
| **User View** | User is not aware of paging; memory is flat. | Matches user view of program (functions, arrays, stack). |
| **Fragmentation** | Suffers from Internal Fragmentation. | Suffers from External Fragmentation. |
| **Virtual Space** | Single contiguous virtual address space. | Multiple segments, each with its own size limit. |

---

## Examiner's Tips
* When answering OS scheduling questions, **always draw the Gantt Chart** first. It helps verify your calculations for average waiting time and turnaround time.
* Clearly write down the formulas you are using before plugging in the values. Marks are allocated step-wise.
"""
        else:
            # Short Summary
            return f"""# Revision Summary: {topic}

The study materials present **{topic}** as a vital component of the syllabus.

### Summary points:
1. **Core Concept**: It deals with how resources are allocated, scheduled, and managed effectively within the environment.
2. **Implementation**: System designs generally employ a combination of hardware support (registers, MMU) and software algorithms (scheduling, allocation policies).
3. **Trade-offs**: Designers must balance performance metrics (utilization, throughput) against system complexity and overhead (context switching, page table sizes).

### Quick Recall
* **SJF (Shortest Job First)**: Gives the minimum average waiting time.
* **Page Fault**: Occurs when a process accesses a page that is not currently mapped in physical memory.
* **TLB (Translation Lookaside Buffer)**: A hardware cache used to speed up virtual-to-physical address translations.
"""
