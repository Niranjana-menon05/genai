import json
from pathlib import Path
from pypdf import PdfReader

def inspect():
    uploads_dir = Path(r"C:\Users\manoj\.gemini\antigravity\scratch\ai_lecture_companion\backend\uploads")
    metadata_file = Path(r"C:\Users\manoj\.gemini\antigravity\scratch\ai_lecture_companion\backend\chroma_db\documents.json")
    
    if not metadata_file.exists():
        print("Metadata file does not exist.")
        return
        
    with open(metadata_file, "r") as f:
        metadata = json.load(f)
        
    for doc_id, doc in metadata.items():
        print(f"=== Document: {doc['filename']} ({doc_id}) ===")
        file_path = uploads_dir / f"{doc_id}{doc['extension']}"
        if not file_path.exists():
            print(f"File {file_path} not found.")
            continue
            
        try:
            reader = PdfReader(file_path)
            print(f"Total Pages: {len(reader.pages)}")
            
            # Print page 1 and page 2 text snippets
            for page_num in range(min(5, len(reader.pages))):
                text = reader.pages[page_num].extract_text()
                print(f"--- Page {page_num+1} (Length: {len(text)}) ---")
                print(text[:400])
                print("-" * 30)
        except Exception as e:
            print(f"Error reading PDF: {e}")

if __name__ == "__main__":
    inspect()
