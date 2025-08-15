import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
import ollama
from chromadb.config import Settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, OllamaLLM

from .config import get_settings
from .s3_client import get_s3_client

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self):
        self.settings = get_settings()
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "mxbai-embed-large")
        self.llm_model = os.getenv("OLLAMA_MODEL", "llama3.2:1b")

        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path="./chroma_db", settings=Settings(anonymized_telemetry=False)
        )

        # Initialize embeddings and LLM
        self.embeddings = OllamaEmbeddings(
            base_url=self.ollama_base_url, model=self.embedding_model
        )

        self.llm = OllamaLLM(
            base_url=self.ollama_base_url, model=self.llm_model, temperature=0.1
        )

        # Text splitter for chunking documents
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )

    def get_or_create_collection(self, document_id: int):
        """Get or create a ChromaDB collection for a document"""
        collection_name = f"document_{document_id}"
        try:
            collection = self.chroma_client.get_collection(collection_name)
        except Exception:  # Catch any exception when collection doesn't exist
            collection = self.chroma_client.create_collection(
                name=collection_name, metadata={"document_id": document_id}
            )
        return collection

    async def index_document(
        self, document_id: int, text_content: str, metadata: Dict[str, Any] = None
    ) -> bool:
        """Index a document's text content for RAG"""
        try:
            # Split text into chunks
            chunks = self.text_splitter.split_text(text_content)

            if not chunks:
                logger.warning(f"No text chunks found for document {document_id}")
                return False

            # Get or create collection
            collection = self.get_or_create_collection(document_id)

            # Generate embeddings for chunks
            chunk_embeddings = []
            chunk_ids = []
            chunk_metadatas = []

            for i, chunk in enumerate(chunks):
                try:
                    # Generate embedding using Ollama
                    embedding = await self._generate_embedding(chunk)

                    chunk_id = f"chunk_{i}"
                    chunk_metadata = {
                        "chunk_index": i,
                        "document_id": document_id,
                        "text_length": len(chunk),
                        **(metadata or {}),
                    }

                    chunk_embeddings.append(embedding)
                    chunk_ids.append(chunk_id)
                    chunk_metadatas.append(chunk_metadata)

                except Exception as e:
                    logger.error(f"Failed to generate embedding for chunk {i}: {e}")
                    continue

            if not chunk_embeddings:
                logger.error(f"No embeddings generated for document {document_id}")
                return False

            # Store in ChromaDB
            collection.add(
                embeddings=chunk_embeddings,
                documents=chunks,
                metadatas=chunk_metadatas,
                ids=chunk_ids,
            )

            logger.info(
                f"Successfully indexed {len(chunks)} chunks for document {document_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to index document {document_id}: {e}")
            return False

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Ollama"""
        try:
            # Use ollama client directly for embeddings
            response = ollama.embeddings(model=self.embedding_model, prompt=text)
            return response["embedding"]
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            # Fallback to a simple hash-based embedding (for testing)
            return [
                float(hash(text[i : i + 10]) % 1000) / 1000
                for i in range(0, min(len(text), 1000), 10)
            ]

    async def ask_question(
        self, document_id: int, question: str, max_results: int = 5
    ) -> Dict[str, Any]:
        """Ask a question about a document using RAG"""
        try:
            # Get document collection
            collection = self.get_or_create_collection(document_id)

            # Generate embedding for the question
            question_embedding = await self._generate_embedding(question)

            # Search for relevant chunks
            results = collection.query(
                query_embeddings=[question_embedding],
                n_results=max_results,
                include=["documents", "metadatas", "distances"],
            )

            if not results["documents"] or not results["documents"][0]:
                return {
                    "answer": "I couldn't find relevant information in this document to answer your question.",
                    "sources": [],
                    "confidence": 0.0,
                }

            # Prepare context from retrieved chunks
            context_chunks = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0]

            context = "\n\n".join(
                [
                    f"[Chunk {meta['chunk_index']}]: {chunk}"
                    for chunk, meta in zip(context_chunks, metadatas)
                ]
            )

            # Generate answer using LLM
            prompt = self._build_rag_prompt(question, context)

            try:
                answer = await self._generate_answer(prompt)
            except Exception as e:
                logger.error(f"Failed to generate answer: {e}")
                answer = "I'm sorry, I encountered an error while processing your question. Please try again."

            # Calculate confidence based on similarity scores
            avg_distance = sum(distances) / len(distances) if distances else 1.0
            confidence = max(0.0, 1.0 - avg_distance)

            # Prepare sources
            sources = [
                {
                    "chunk_index": meta["chunk_index"],
                    "text": chunk[:200] + "..." if len(chunk) > 200 else chunk,
                    "confidence": max(0.0, 1.0 - distance),
                }
                for chunk, meta, distance in zip(context_chunks, metadatas, distances)
            ]

            return {
                "answer": answer,
                "sources": sources,
                "confidence": confidence,
                "model": self.llm_model,
            }

        except Exception as e:
            logger.error(f"Failed to answer question for document {document_id}: {e}")
            return {
                "answer": "I'm sorry, I encountered an error while processing your question. Please try again.",
                "sources": [],
                "confidence": 0.0,
                "error": str(e),
            }

    def _build_rag_prompt(self, question: str, context: str) -> str:
        """Build a prompt for RAG-based question answering"""
        return f"""You are a helpful AI assistant that answers questions based on the provided document context.

Context from the document:
{context}

Question: {question}

Instructions:
- Answer the question based ONLY on the information provided in the context above
- If the context doesn't contain enough information to answer the question, say so clearly
- Be concise but thorough in your response
- Quote specific parts of the context when relevant
- If you're uncertain about something, express that uncertainty

Answer:"""

    async def _generate_answer(self, prompt: str) -> str:
        """Generate answer using Ollama LLM"""
        try:
            # Use ollama client directly for generation
            response = ollama.generate(
                model=self.llm_model,
                prompt=prompt,
                options={"temperature": 0.1, "top_p": 0.9, "max_tokens": 500},
            )
            return response["response"].strip()
        except Exception as e:
            logger.error(f"Failed to generate answer with Ollama: {e}")
            return "I'm sorry, I'm unable to generate an answer at the moment. Please try again later."

    async def load_document_text(self, document_id: int) -> Optional[str]:
        """Load OCR text for a document from S3 or extract directly from local PDF"""
        try:
            # First try to get OCR results from S3
            try:
                s3_client = get_s3_client()
                ocr_key = f"ocr/{document_id}/text.json"
                response = s3_client.get_object(Bucket="ocr", Key=ocr_key)
                ocr_data = json.loads(response["Body"].read().decode("utf-8"))

                # Extract text from all pages
                text_parts = []
                for page_data in ocr_data.get("pages", []):
                    if page_data.get("text"):
                        text_parts.append(page_data["text"])

                return "\n\n".join(text_parts)
            except Exception as e:
                logger.warning(
                    f"Could not load OCR text from S3 for document {document_id}: {e}"
                )

            # Fallback: Extract text directly from local PDF file
            try:
                import fitz  # PyMuPDF
                from sqlalchemy.orm import Session

                from .db import get_db
                from .models import Document

                # Get document info from database
                db = next(get_db())
                document = db.query(Document).filter(Document.id == document_id).first()
                if not document:
                    logger.error(f"Document {document_id} not found in database")
                    return None

                # Try to find the PDF file locally
                pdf_paths = [
                    f"backend/uploads/{document.title}",
                    f"uploads/{document.title}",
                    f"./{document.title}",
                ]

                pdf_path = None
                for path in pdf_paths:
                    if os.path.exists(path):
                        pdf_path = path
                        break

                if not pdf_path:
                    logger.error(f"Could not find PDF file for document {document_id}")
                    return None

                # Extract text using PyMuPDF
                doc = fitz.open(pdf_path)
                text_parts = []

                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    text = page.get_text()
                    if text.strip():
                        text_parts.append(text)

                doc.close()

                if text_parts:
                    logger.info(
                        f"Extracted text from {len(text_parts)} pages for document {document_id}"
                    )
                    return "\n\n".join(text_parts)
                else:
                    logger.warning(f"No text found in PDF for document {document_id}")
                    return None

            except Exception as e:
                logger.error(
                    f"Failed to extract text from local PDF for document {document_id}: {e}"
                )
                return None

        except Exception as e:
            logger.error(f"Failed to load document text for {document_id}: {e}")
            return None

    async def ensure_document_indexed(
        self, document_id: int, document_title: str = ""
    ) -> bool:
        """Ensure a document is indexed for RAG"""
        try:
            # Check if document is already indexed
            collection = self.get_or_create_collection(document_id)

            # Check if collection has any documents
            try:
                count = collection.count()
                if count > 0:
                    logger.info(
                        f"Document {document_id} already indexed with {count} chunks"
                    )
                    return True
            except:
                pass

            # Load document text
            text_content = await self.load_document_text(document_id)

            if not text_content:
                logger.warning(f"No text content found for document {document_id}")
                return False

            # Index the document
            metadata = {"title": document_title} if document_title else {}
            return await self.index_document(document_id, text_content, metadata)

        except Exception as e:
            logger.error(f"Failed to ensure document {document_id} is indexed: {e}")
            return False


# Global RAG service instance
_rag_service = None


def get_rag_service() -> RAGService:
    """Get the global RAG service instance"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
