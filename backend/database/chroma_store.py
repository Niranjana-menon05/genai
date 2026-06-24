import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from backend import config

# Defensive Imports
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except ImportError:
    RecursiveCharacterTextSplitter = None

try:
    import chromadb
except ImportError:
    chromadb = None

# Embeddings model loading
_embeddings_model = None

def get_embeddings_model():
    global _embeddings_model
    if _embeddings_model is None:
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            print("Loading HuggingFaceEmbeddings (all-MiniLM-L6-v2) on CPU...")
            _embeddings_model = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'}
            )
            print("HuggingFaceEmbeddings loaded successfully.")
        except Exception as e:
            print(f"HuggingFaceEmbeddings not available: {e}. Using mock embeddings.")
            _embeddings_model = MockEmbeddings()
    return _embeddings_model


class MockEmbeddings:
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [[0.1] * 384 for _ in texts]
        
    def embed_query(self, text: str) -> List[float]:
        return [0.1] * 384


class VectorStoreManager:
    def __init__(self):
        self.db_path = str(config.DB_DIR)
        self.collection_name = "lecture_companion_chunks"
        
        # Local mock index fallback if chromadb is not installed
        self.use_mock_db = (chromadb is None)
        self.mock_db = {}  # doc_id -> {"text": text, "metadata": metadata}
        
        if self.use_mock_db:
            print("ChromaDB is not installed. Using in-memory fallback RAG store.")
        else:
            self._init_db()

    def _init_db(self):
        try:
            self.client = chromadb.PersistentClient(path=self.db_path)
            print(f"ChromaDB Persistent Client initialized at: {self.db_path}")
        except Exception as e:
            print(f"Failed to initialize ChromaDB Persistent Client: {e}. Falling back to in-memory store.")
            self.use_mock_db = True

    def get_collection(self):
        if self.use_mock_db or not self.client:
            return None
        try:
            return self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            print(f"Error getting ChromaDB collection: {e}. Falling back to in-memory store.")
            self.use_mock_db = True
            return None

    def add_document(self, doc_id: str, text: str, metadata: Dict[str, Any]) -> bool:
        """Splits document text and registers it. Uses ChromaDB or in-memory fallback."""
        if self.use_mock_db:
            # Store in in-memory dict
            self.mock_db[doc_id] = {
                "text": text,
                "metadata": metadata
            }
            print(f"[Memory DB] Successfully stored document: {doc_id} (size: {len(text)} chars)")
            return True

        collection = self.get_collection()
        if not collection:
            # Fallback to memory
            self.use_mock_db = True
            return self.add_document(doc_id, text, metadata)

        try:
            # Split text using LangChain if available, else simple character chunks
            if RecursiveCharacterTextSplitter:
                splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
                chunks = splitter.split_text(text)
            else:
                # Simple fallback splitter
                chunks = [text[i:i+1000] for i in range(0, len(text), 800)]
            
            if not chunks:
                print(f"No text chunks created for document: {doc_id}")
                return False

            ids = []
            embeddings = []
            metadatas = []
            documents = []

            embeddings_model = get_embeddings_model()
            
            # Compute embeddings for all chunks in batch
            print(f"Embedding {len(chunks)} chunks for document {metadata.get('filename', doc_id)}...")
            chunk_embeddings = embeddings_model.embed_documents(chunks)

            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i}"
                ids.append(chunk_id)
                embeddings.append(chunk_embeddings[i])
                documents.append(chunk)
                
                # Copy metadata and add chunk index
                chunk_meta = metadata.copy()
                chunk_meta["chunk_index"] = i
                chunk_meta["doc_id"] = doc_id
                
                # Clean metadata types
                cleaned_meta = {}
                for k, v in chunk_meta.items():
                    if isinstance(v, (str, int, float, bool)):
                        cleaned_meta[k] = v
                    else:
                        cleaned_meta[k] = str(v)
                metadatas.append(cleaned_meta)

            collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )
            print(f"Successfully added {len(chunks)} chunks for {doc_id} to ChromaDB.")
            return True
        except Exception as e:
            print(f"Error adding to ChromaDB: {e}. Falling back to in-memory store.")
            self.use_mock_db = True
            return self.add_document(doc_id, text, metadata)

    def query(self, query_text: str, doc_filter: Optional[List[str]] = None, n_results: int = 5) -> List[Dict[str, Any]]:
        """Queries vector store. Uses word overlap keyword matcher if in-memory fallback is active."""
        if self.use_mock_db:
            print(f"[Memory DB] Querying {len(self.mock_db)} documents for: '{query_text}'...")
            query_words = set(query_text.lower().split())
            scored_chunks = []
            
            for doc_id, doc in self.mock_db.items():
                if doc_filter and doc_id not in doc_filter:
                    continue
                text = doc["text"]
                # Chunk simple split
                chunks = [text[i:i+1000] for i in range(0, len(text), 800)]
                for idx, chunk in enumerate(chunks):
                    chunk_words = set(chunk.lower().replace("\n", " ").split())
                    # Intersection score
                    overlap = len(query_words.intersection(chunk_words))
                    # Normalise overlap
                    score = overlap / (len(query_words) + 1.0)
                    scored_chunks.append({
                        "id": f"{doc_id}_chunk_{idx}",
                        "text": chunk,
                        "metadata": {**doc["metadata"], "chunk_index": idx, "doc_id": doc_id},
                        "distance": 1.0 - score  # lower distance is better
                    })
            
            # Sort by distance ascending
            scored_chunks.sort(key=lambda x: x["distance"])
            print(f"[Memory DB] Found {len(scored_chunks)} matching chunks. Returning top {n_results}.")
            return scored_chunks[:n_results]

        collection = self.get_collection()
        if not collection:
            self.use_mock_db = True
            return self.query(query_text, doc_filter, n_results)

        try:
            embeddings_model = get_embeddings_model()
            query_embedding = embeddings_model.embed_query(query_text)

            where_clause = None
            if doc_filter:
                if len(doc_filter) == 1:
                    where_clause = {"doc_id": doc_filter[0]}
                elif len(doc_filter) > 1:
                    where_clause = {"doc_id": {"$in": doc_filter}}

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_clause
            )

            formatted_results = []
            if results and results.get("documents"):
                docs = results["documents"][0]
                metas = results["metadatas"][0]
                dists = results["distances"][0] if "distances" in results else [0.0] * len(docs)
                ids = results["ids"][0]

                for i in range(len(docs)):
                    formatted_results.append({
                        "id": ids[i],
                        "text": docs[i],
                        "metadata": metas[i],
                        "distance": dists[i]
                    })
            return formatted_results
        except Exception as e:
            print(f"Error querying ChromaDB: {e}. Falling back to in-memory search.")
            self.use_mock_db = True
            return self.query(query_text, doc_filter, n_results)

    def delete_document(self, doc_id: str) -> bool:
        """Deletes document chunks from ChromaDB or in-memory dictionary."""
        if self.use_mock_db:
            if doc_id in self.mock_db:
                del self.mock_db[doc_id]
                print(f"[Memory DB] Deleted document: {doc_id}")
            return True

        collection = self.get_collection()
        if not collection:
            return False
        try:
            collection.delete(where={"doc_id": doc_id})
            return True
        except Exception as e:
            print(f"Error deleting from ChromaDB: {e}")
            return False
            
    def list_all_documents(self) -> List[str]:
        """Lists document IDs registered in vector store."""
        if self.use_mock_db:
            return list(self.mock_db.keys())

        collection = self.get_collection()
        if not collection:
            return []
        try:
            result = collection.get(include=["metadatas"])
            if not result or not result.get("metadatas"):
                return []
            doc_ids = set()
            for meta in result["metadatas"]:
                if meta and "doc_id" in meta:
                    doc_ids.add(meta["doc_id"])
            return list(doc_ids)
        except Exception as e:
            print(f"Error listing from ChromaDB: {e}")
            return []
