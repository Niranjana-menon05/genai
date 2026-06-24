# AI Lecture Companion

AI Lecture Companion is a modern, student-focused educational web application that helps students learn, revise, and test themselves using their own academic materials. It uses a Retrieval-Augmented Generation (RAG) pipeline to extract knowledge from uploaded files (PDFs, slide presentations, word documents) and answer student questions, generate custom summaries/revision aids, analyze previous year question papers, and build practice quizzes.

## Key Features

1. **Academic Document Library**: Upload and manage PDFs, PPTX slides, DOCX files, and TXT notes.
2. **AI Study Assistant**: Chat with your materials in a RAG-based chatbot interface, scoping queries to specific files or the entire library.
3. **Smart Revision Aids**: Instantly generate structured summaries, exam preparation guides, or concise cheat sheets.
4. **PYQ Topic Weightage Analyzer**: Upload previous-year question papers to automatically match concepts and identify high-frequency topics.
5. **Interactive Practice Quizzes**: Generate MCQs, short answer questions, or viva cards at Easy, Medium, or Hard difficulty levels.
6. **Pastel Educational UI**: A responsive, soothing pastel theme with support for light and dark modes.

---

## Technical Architecture

- **Backend**: Python, FastAPI, LangChain, ChromaDB (Vector Store), Groq API, and HuggingFace SentenceTransformers (`all-MiniLM-L6-v2` local embeddings).
- **Frontend**: Single Page App using HTML5, modern Tailwind CSS v4 via CDN, Lucide Icons, and client-side JavaScript.
- **RAG Execution**: Chunks document text, embeds them locally on CPU, stores them in ChromaDB, retrieves context on search, and uses Groq's high-speed models (`llama-3.3-70b-versatile`) to compile educational responses.
- **Mock Mode**: Fully operational off-the-grid simulation that triggers when no API key is specified, allowing instant review of the application's visual features and user flows.

---

## Setup and Running

### 1. Prerequisites
- **Python 3.9+** installed on your system.

### 2. Installation
Clone or navigate to the project directory and install the required Python packages:

```bash
# Navigate to the project root
cd C:\Users\manoj\.gemini\antigravity\scratch\ai_lecture_companion

# Install dependencies
pip install -r backend/requirements.txt
```

### 3. Environment Configuration
Copy the sample environment file to `.env`:

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` in your editor:
- **Mock Mode (Default)**: If you leave `GROQ_API_KEY` blank or set to the placeholder `your_groq_api_key_here`, the application runs in a simulated **Mock Mode**. This is highly recommended for initial testing, as it works instantly without needing any internet connection or API setup!
- **Groq Mode**: To run with a live LLM, get a free API key from [Groq Console](https://console.groq.com/) and update:
  ```env
  GROQ_API_KEY=gsk_your_actual_groq_key_here
  ```

### 4. Running the Application
Start the FastAPI server:

```bash
# Start uvicorn server from the root directory
python -m uvicorn backend.main:app --reload --port 8000
```

Once running:
- Open your browser and navigate to: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**
- The frontend dashboard will load, serving all controls.

---

## Testing Backend Modules
A testing script is provided to verify document parsing, local indexing, and agent generation pipelines:

```bash
python backend/test_agents.py
```
This runs a simulated workflow from start to finish on a temporary text file, validating ChromaDB persistency and study agents.
