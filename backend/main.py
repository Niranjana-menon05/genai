import os
import json
import uuid
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend import config
from backend.services.doc_processor import DocumentProcessor
from backend.database.chroma_store import VectorStoreManager
from backend.services.study_agent import StudyAssistantAgent
from backend.services.quiz_generator import QuizGenerator
from backend.services.pyq_analyzer import PYQAnalyzer

# Initialize FastAPI
app = FastAPI(
    title="AI Lecture Companion API",
    description="Backend API for RAG-based multi-agent study assistance",
    version="1.0.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database manager
db_manager = VectorStoreManager()

# Paths
DOCS_METADATA_FILE = config.DB_DIR / "documents.json"
STATS_FILE = config.DB_DIR / "stats.json"

# Models for request validation
class ChatRequest(BaseModel):
    query: str
    doc_ids: Optional[List[str]] = None

class RevisionRequest(BaseModel):
    topic: str
    doc_ids: Optional[List[str]] = None
    note_type: str  # "Short Summary", "Exam Guide", "Cheat Sheet"

class QuizRequest(BaseModel):
    doc_ids: Optional[List[str]] = None
    quiz_type: str  # "mcq", "short", "viva"
    difficulty: str  # "easy", "medium", "hard"
    count: int = 5

class PYQRequest(BaseModel):
    pyq_doc_id: str
    notes_doc_ids: Optional[List[str]] = None

# Helper functions to manage persistence

def load_documents_metadata() -> Dict[str, Any]:
    if not DOCS_METADATA_FILE.exists():
        return {}
    try:
        with open(DOCS_METADATA_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading document metadata: {e}")
        return {}

def save_documents_metadata(metadata: Dict[str, Any]):
    try:
        with open(DOCS_METADATA_FILE, "w") as f:
            json.dump(metadata, f, indent=4)
    except Exception as e:
        print(f"Error saving document metadata: {e}")

def load_stats() -> Dict[str, int]:
    default_stats = {
        "documents_uploaded": 0,
        "questions_asked": 0,
        "summaries_generated": 0,
        "quizzes_generated": 0
    }
    if not STATS_FILE.exists():
        return default_stats
    try:
        with open(STATS_FILE, "r") as f:
            stats = json.load(f)
            # Ensure all keys are present
            for k in default_stats:
                stats.setdefault(k, default_stats[k])
            return stats
    except Exception as e:
        print(f"Error loading stats: {e}")
        return default_stats

def update_stat(key: str, increment: int = 1):
    try:
        stats = load_stats()
        if key in stats:
            stats[key] += increment
        else:
            stats[key] = increment
        with open(STATS_FILE, "w") as f:
            json.dump(stats, f, indent=4)
    except Exception as e:
        print(f"Error updating stat {key}: {e}")


# Document processing in background task to avoid blocking API
def process_uploaded_document_task(doc_id: str, file_path: str, filename: str, is_pyq: bool):
    print(f"Starting background processing for {filename}...")
    metadata = load_documents_metadata()
    if doc_id not in metadata:
        return
        
    metadata[doc_id]["status"] = "processing"
    save_documents_metadata(metadata)
    
    try:
        # 1. Parse document text
        parsed_result = DocumentProcessor.process_document(file_path)
        
        if not parsed_result["success"]:
            raise Exception(parsed_result["error"])
            
        doc_text = parsed_result["text"]
        if not doc_text.strip():
            raise Exception("No text content could be extracted from the file.")
            
        # 2. Add to ChromaDB vector store
        db_metadata = {
            "filename": filename,
            "file_size": parsed_result["file_size"],
            "extension": parsed_result["extension"],
            "is_pyq": is_pyq,
            "uploaded_at": metadata[doc_id]["uploaded_at"]
        }
        
        # Save total pages/slides info if available
        if "total_pages" in parsed_result:
            db_metadata["total_pages"] = parsed_result["total_pages"]
        elif "total_slides" in parsed_result:
            db_metadata["total_slides"] = parsed_result["total_slides"]
            
        success = db_manager.add_document(doc_id, doc_text, db_metadata)
        
        if not success:
            raise Exception("Failed to store chunks in vector database.")
            
        # 3. Update status in metadata
        metadata = load_documents_metadata()
        metadata[doc_id]["status"] = "ready"
        metadata[doc_id]["total_pages"] = parsed_result.get("total_pages", parsed_result.get("total_slides", 1))
        save_documents_metadata(metadata)
        
        # Increment document stat
        update_stat("documents_uploaded", 1)
        print(f"Finished background processing for {filename} successfully.")
    except Exception as e:
        print(f"Error processing document {filename}: {e}")
        metadata = load_documents_metadata()
        if doc_id in metadata:
            metadata[doc_id]["status"] = f"error: {str(e)}"
            save_documents_metadata(metadata)


# --- REST API Endpoints ---

@app.get("/api/stats")
def get_stats():
    """Fetch current dashboard counts."""
    stats = load_stats()
    # Recalculate document count from metadata file to be accurate
    docs = load_documents_metadata()
    ready_docs = [d for d in docs.values() if d["status"] == "ready"]
    stats["documents_uploaded"] = len(ready_docs)
    return stats

@app.get("/api/documents")
def list_documents():
    """Returns a list of all uploaded documents."""
    docs = load_documents_metadata()
    return list(docs.values())

@app.post("/api/upload")
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    is_pyq: bool = Form(False)
):
    """Handles file uploads, saves to disk, and triggers RAG indexing in the background."""
    ext = Path(file.filename).suffix.lower()
    if ext not in (".pdf", ".docx", ".pptx", ".ppt", ".txt", ".md"):
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file format '{ext}'. Only PDF, DOCX, PPTX, PPT, TXT, and MD are allowed."
        )
        
    doc_id = str(uuid.uuid4())
    filename = file.filename
    safe_filename = f"{doc_id}{ext}"
    file_path = config.UPLOAD_DIR / safe_filename
    
    try:
        # Save file to upload directory
        with open(file_path, "wb") as buffer:
            content = file.file.read()
            buffer.write(content)
            
        file_size = len(content)
        
        # Save initial metadata (status = queued)
        metadata = load_documents_metadata()
        metadata[doc_id] = {
            "id": doc_id,
            "filename": filename,
            "file_size": file_size,
            "extension": ext,
            "is_pyq": is_pyq,
            "status": "queued",
            "uploaded_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        save_documents_metadata(metadata)
        
        # Queue parsing & vectorization in background
        background_tasks.add_task(
            process_uploaded_document_task,
            doc_id,
            str(file_path),
            filename,
            is_pyq
        )
        
        return {
            "success": True,
            "message": f"File '{filename}' uploaded successfully. Parsing started.",
            "document": metadata[doc_id]
        }
        
    except Exception as e:
        if file_path.exists():
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    """Deletes a document from storage, vector store, and metadata."""
    docs = load_documents_metadata()
    if doc_id not in docs:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    doc_info = docs[doc_id]
    ext = doc_info["extension"]
    file_path = config.UPLOAD_DIR / f"{doc_id}{ext}"
    
    try:
        # 1. Delete physical file
        if file_path.exists():
            os.remove(file_path)
            
        # 2. Delete from ChromaDB
        db_manager.delete_document(doc_id)
        
        # 3. Update documents.json
        del docs[doc_id]
        save_documents_metadata(docs)
        
        return {"success": True, "message": f"Document '{doc_info['filename']}' deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

@app.post("/api/chat")
def chat_with_documents(request: ChatRequest):
    """Q&A endpoint retrieving relevant context from vector store and calling the Study Agent."""
    update_stat("questions_asked", 1)
    
    # 1. Retrieve matching chunks from database
    # If request.doc_ids is provided, filter search to those files. Otherwise search all.
    # n_results is standard 4-5 chunks.
    doc_filter = request.doc_ids
    chunks = db_manager.query(request.query, doc_filter=doc_filter, n_results=5)
    
    # 2. Generate answer using Study Assistant
    result = StudyAssistantAgent.answer_question(request.query, chunks)
    return result

@app.post("/api/revision-notes")
def generate_revision_notes(request: RevisionRequest):
    """Retrieves relevant chunks and generates study guides/cheat sheets."""
    update_stat("summaries_generated", 1)
    
    # Retrieve chunks related to the topic
    chunks = db_manager.query(request.topic, doc_filter=request.doc_ids, n_results=6)
    
    result = StudyAssistantAgent.generate_revision_notes(
        topic=request.topic,
        context_chunks=chunks,
        note_type=request.note_type
    )
    return result

@app.post("/api/quiz")
def generate_quiz(request: QuizRequest):
    """Generates study questions based on selected documents."""
    update_stat("quizzes_generated", 1)
    
    # Query a broad selection of chunks to build questions from
    chunks = db_manager.query(
        query_text="operating system process memory paging deadlock synchronization scheduling", 
        doc_filter=request.doc_ids, 
        n_results=8
    )
    
    result = QuizGenerator.generate_quiz(
        context_chunks=chunks,
        quiz_type=request.quiz_type,
        difficulty=request.difficulty,
        count=request.count
    )
    return result

@app.post("/api/pyq-analysis")
def analyze_pyq(request: PYQRequest):
    """Analyzes a PYQ paper and maps it against study materials."""
    # Find the PYQ document
    docs = load_documents_metadata()
    if request.pyq_doc_id not in docs:
        raise HTTPException(status_code=404, detail="PYQ document not found.")
        
    pyq_info = docs[request.pyq_doc_id]
    pyq_file_path = config.UPLOAD_DIR / f"{request.pyq_doc_id}{pyq_info['extension']}"
    
    try:
        # 1. Parse pyq text directly
        parsed_result = DocumentProcessor.process_document(str(pyq_file_path))
        if not parsed_result["success"]:
            raise Exception(parsed_result["error"])
        pyq_text = parsed_result["text"]
        
        # 2. Retrieve syllabus/notes chunks that correspond to the subjects mentioned in the PYQ
        # Querying with PYQ content preview
        query_text = pyq_text[:1000] if len(pyq_text) > 1000 else pyq_text
        notes_chunks = db_manager.query(
            query_text=query_text,
            doc_filter=request.notes_doc_ids,
            n_results=10
        )
        
        # 3. Generate analysis report
        result = PYQAnalyzer.analyze_pyq(pyq_text, notes_chunks)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze PYQ: {str(e)}")


# --- Serve Frontend SPA ---

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# Check if frontend directories exist, create if missing
(FRONTEND_DIR / "css").mkdir(parents=True, exist_ok=True)
(FRONTEND_DIR / "js").mkdir(parents=True, exist_ok=True)

# Mount static folders
app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")

# Mount index file at root
@app.get("/")
def read_index():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        # Write a basic placeholder if frontend hasn't been written yet
        return JSONResponse(content={"message": "FastAPI is running. Frontend index.html is missing. Please create index.html in the frontend folder."})
    return FileResponse(str(index_path))
