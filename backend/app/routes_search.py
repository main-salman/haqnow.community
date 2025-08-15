import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from .db import get_db
from .models import Document
from .schemas import DocumentOut

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/", response_model=List[DocumentOut])
def search_documents(
    q: str = Query(..., description="Search query"),
    source: Optional[str] = Query(None, description="Filter by source"),
    language: Optional[str] = Query(None, description="Filter by language"),
    status: Optional[str] = Query(None, description="Filter by status"),
    date_from: Optional[str] = Query(
        None, description="Filter by date from (YYYY-MM-DD)"
    ),
    date_to: Optional[str] = Query(None, description="Filter by date to (YYYY-MM-DD)"),
    limit: int = Query(50, le=100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
    db: Session = Depends(get_db),
):
    """
    Search documents with full-text search and filters
    """
    query = db.query(Document)

    # Full-text search on title and description
    if q:
        search_filter = or_(
            Document.title.ilike(f"%{q}%"), Document.description.ilike(f"%{q}%")
        )
        query = query.filter(search_filter)

    # Apply filters
    if source:
        query = query.filter(Document.source.ilike(f"%{source}%"))

    if language:
        query = query.filter(Document.language == language)

    if status:
        query = query.filter(Document.status == status)

    if date_from:
        query = query.filter(Document.created_at >= date_from)

    if date_to:
        query = query.filter(Document.created_at <= date_to)

    # Order by relevance (created_at desc for now)
    query = query.order_by(Document.created_at.desc())

    # Apply pagination
    documents = query.offset(offset).limit(limit).all()

    return documents


@router.get("/facets")
def get_search_facets(db: Session = Depends(get_db)):
    """
    Get available facets for search filtering
    """
    # Get unique sources
    sources = (
        db.query(Document.source).distinct().filter(Document.source.isnot(None)).all()
    )
    sources = [s[0] for s in sources if s[0]]

    # Get unique languages
    languages = db.query(Document.language).distinct().all()
    languages = [l[0] for l in languages if l[0]]

    # Get unique statuses
    statuses = db.query(Document.status).distinct().all()
    statuses = [s[0] for s in statuses if s[0]]

    # Get date range
    date_range = db.query(
        text("MIN(created_at) as min_date, MAX(created_at) as max_date")
    ).first()

    return {
        "sources": sources,
        "languages": languages,
        "statuses": statuses,
        "date_range": {
            "min": date_range.min_date.isoformat() if date_range.min_date else None,
            "max": date_range.max_date.isoformat() if date_range.max_date else None,
        },
    }


@router.post("/ask")
async def ask_question(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Ask a question about a document using RAG with Ollama
    """
    document_id = payload.get("document_id")
    question = payload.get("question")

    if not document_id or not question:
        raise HTTPException(
            status_code=400, detail="document_id and question are required"
        )

    # Get document
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        import time

        from .rag import get_rag_service

        start_time = time.time()
        rag_service = get_rag_service()

        # Ensure document is indexed
        await rag_service.ensure_document_indexed(document_id, document.title)

        # Ask the question
        result = await rag_service.ask_question(document_id, question)

        processing_time = time.time() - start_time

        response = {
            "document_id": document_id,
            "question": question,
            "answer": result["answer"],
            "sources": result["sources"],
            "confidence": result.get("confidence", 0.0),
            "model": result.get("model", "ollama"),
            "processing_time": processing_time,
        }

        return response

    except ImportError:
        # Fallback if RAG dependencies are not available
        return {
            "document_id": document_id,
            "question": question,
            "answer": "RAG functionality is not available. Please ensure Ollama is running and all dependencies are installed.",
            "sources": [],
            "confidence": 0.0,
            "model": "unavailable",
            "processing_time": 0.0,
            "error": "RAG service unavailable",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG processing failed: {str(e)}")


@router.get("/suggestions")
def get_search_suggestions(
    q: str = Query(..., description="Partial search query"),
    limit: int = Query(10, le=20, description="Maximum number of suggestions"),
    db: Session = Depends(get_db),
):
    """
    Get search suggestions based on partial query
    """
    if len(q) < 2:
        return {"suggestions": []}

    # Get title suggestions
    title_suggestions = (
        db.query(Document.title)
        .filter(Document.title.ilike(f"%{q}%"))
        .limit(limit // 2)
        .all()
    )

    # Get source suggestions
    source_suggestions = (
        db.query(Document.source)
        .distinct()
        .filter(and_(Document.source.isnot(None), Document.source.ilike(f"%{q}%")))
        .limit(limit // 2)
        .all()
    )

    suggestions = []

    # Add title suggestions
    for title in title_suggestions:
        suggestions.append({"text": title[0], "type": "title", "category": "Documents"})

    # Add source suggestions
    for source in source_suggestions:
        suggestions.append({"text": source[0], "type": "source", "category": "Sources"})

    return {"suggestions": suggestions[:limit]}
