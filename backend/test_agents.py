import os
import sys
from pathlib import Path

# Add project root to sys.path so we can import backend packages
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.services.doc_processor import DocumentProcessor
from backend.database.chroma_store import VectorStoreManager
from backend.services.study_agent import StudyAssistantAgent
from backend.services.quiz_generator import QuizGenerator
from backend.services.pyq_analyzer import PYQAnalyzer

def test_document_processor(temp_file: Path):
    print("\n--- Testing Document Processor ---")
    result = DocumentProcessor.process_document(str(temp_file))
    print(f"Extraction successful: {result['success']}")
    print(f"File size: {result['file_size']} bytes")
    print(f"Text snippet: {result['text'][:150]}...")
    return result['text']

def test_vector_store(doc_text: str):
    print("\n--- Testing ChromaDB Vector Store ---")
    db_manager = VectorStoreManager()
    doc_id = "test_doc_123"
    meta = {
        "filename": "test_lecture.txt",
        "file_size": len(doc_text),
        "extension": ".txt",
        "uploaded_at": "2026-06-24 12:00:00",
        "is_pyq": False
    }
    
    # Add to store
    add_success = db_manager.add_document(doc_id, doc_text, meta)
    print(f"Successfully added document to vector store: {add_success}")
    
    # Query store
    query_text = "What are the Coffman conditions for deadlock?"
    print(f"Querying vector store for: '{query_text}'...")
    results = db_manager.query(query_text, n_results=2)
    print(f"Found {len(results)} matching chunks.")
    for i, res in enumerate(results):
        print(f" Chunk {i+1} (dist={res['distance']:.4f}): {res['text'][:100]}...")
        
    return db_manager, results

def test_study_agent(db_manager, chunks):
    print("\n--- Testing Study Assistant Agent ---")
    query_text = "What is Mutual Exclusion in operating systems?"
    print(f"Answering query: '{query_text}'...")
    res = StudyAssistantAgent.answer_question(query_text, chunks)
    print(f"Agent response mode: {res['mode']}")
    print(f"Response sources: {res['sources']}")
    print(f"Response preview:\n{res['answer'][:300]}...")

def test_quiz_generator(chunks):
    print("\n--- Testing Quiz Generator ---")
    print("Generating MCQ Quiz (3 questions)...")
    quiz = QuizGenerator.generate_quiz(chunks, "mcq", "medium", 3)
    print(f"Quiz Mode: {quiz['mode']}")
    questions = quiz['questions']
    print(f"Generated {len(questions)} questions.")
    for i, q in enumerate(questions):
        print(f"  Q{i+1}: {q['question']}")
        if 'options' in q:
            print(f"    Options: {q['options']}")
            print(f"    Correct: {q['correct_answer']}")

def test_pyq_analyzer(chunks):
    print("\n--- Testing PYQ Analyzer ---")
    pyq_sample_text = """
    Operating Systems Semester Exam
    Q1. Define Deadlock. List and explain the Coffman conditions in detail. (8 marks)
    Q2. Discuss Paging and explain how it solves external fragmentation. (6 marks)
    Q3. What is page fault? Explain LRU replacement. (6 marks)
    """
    print("Analyzing PYQ content against notes...")
    analysis = PYQAnalyzer.analyze_pyq(pyq_sample_text, chunks)
    print(f"Analysis Mode: {analysis['mode']}")
    topics = analysis['analysis']
    print(f"Discovered {len(topics)} core topics:")
    for t in topics[:3]:
        print(f"  - {t['topic']} (Freq: {t['frequency']}, Importance: {t['importance']})")

def main():
    print("====================================================")
    print("         AI Lecture Companion test script           ")
    print("====================================================")
    
    # Create a temporary dummy lecture note file
    temp_file = Path(__file__).resolve().parent / "test_lecture.txt"
    sample_notes = """
    Operating Systems Lecture Notes - Unit 3: Deadlocks and Memory
    
    A Deadlock occurs when processes hold resources and wait for other resources in a circular chain.
    The four necessary conditions for deadlocks are:
    1. Mutual Exclusion: resources cannot be shared.
    2. Hold and Wait: processes hold resources while waiting.
    3. No Preemption: resources cannot be forcibly taken.
    4. Circular Wait: a cycle of processes waiting.
    
    We can avoid deadlocks using the Banker's Algorithm which checks for safe state execution.
    
    Memory management uses Paging to split logical memory into pages and physical memory into frames.
    Paging prevents external fragmentation but can cause small internal fragmentation.
    """
    
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(sample_notes.strip())
        
    try:
        # Run tests
        doc_text = test_document_processor(temp_file)
        db_manager, chunks = test_vector_store(doc_text)
        test_study_agent(db_manager, chunks)
        test_quiz_generator(chunks)
        test_pyq_analyzer(chunks)
        
        # Clean up database test entries
        print("\n--- Cleaning up Vector Store entries ---")
        db_manager.delete_document("test_doc_123")
        
        print("\nAll agent and RAG module tests completed successfully!")
    finally:
        # Remove temp file
        if temp_file.exists():
            os.remove(temp_file)

if __name__ == "__main__":
    main()
