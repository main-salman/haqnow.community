#!/usr/bin/env python3
"""
Script to delete all documents and related data from the database.
This will clean up: documents, comments, redactions, document_shares, document_content, and processing_jobs.
"""

import sys
import os
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from app.db import engine, SessionLocal
from app.models import Document, Comment, Redaction, DocumentShare, DocumentContent, ProcessingJob

def cleanup_all_documents():
    """Delete all documents and related data"""
    
    with SessionLocal() as db:
        try:
            print("🗑️  Starting document cleanup...")
            
            # Get count of documents before deletion
            doc_count = db.query(Document).count()
            comment_count = db.query(Comment).count()
            redaction_count = db.query(Redaction).count()
            share_count = db.query(DocumentShare).count()
            content_count = db.query(DocumentContent).count()
            job_count = db.query(ProcessingJob).count()
            
            print(f"📊 Current database state:")
            print(f"   - Documents: {doc_count}")
            print(f"   - Comments: {comment_count}")
            print(f"   - Redactions: {redaction_count}")
            print(f"   - Document Shares: {share_count}")
            print(f"   - Document Content: {content_count}")
            print(f"   - Processing Jobs: {job_count}")
            
            if doc_count == 0:
                print("✅ Database is already clean - no documents found.")
                return
            
            # Delete in order to respect foreign key constraints
            print("\n🔄 Deleting related data...")
            
            # Delete comments
            deleted_comments = db.query(Comment).delete()
            print(f"   ✅ Deleted {deleted_comments} comments")
            
            # Delete redactions
            deleted_redactions = db.query(Redaction).delete()
            print(f"   ✅ Deleted {deleted_redactions} redactions")
            
            # Delete document shares
            deleted_shares = db.query(DocumentShare).delete()
            print(f"   ✅ Deleted {deleted_shares} document shares")
            
            # Delete document content
            deleted_content = db.query(DocumentContent).delete()
            print(f"   ✅ Deleted {deleted_content} document content entries")
            
            # Delete processing jobs
            deleted_jobs = db.query(ProcessingJob).delete()
            print(f"   ✅ Deleted {deleted_jobs} processing jobs")
            
            # Finally delete documents
            print("\n🗂️  Deleting documents...")
            deleted_docs = db.query(Document).delete()
            print(f"   ✅ Deleted {deleted_docs} documents")
            
            # Reset auto-increment sequences (PostgreSQL specific)
            print("\n🔄 Resetting ID sequences...")
            sequences = [
                "documents_id_seq",
                "comments_id_seq", 
                "redactions_id_seq",
                "document_shares_id_seq",
                "document_content_id_seq",
                "processing_jobs_id_seq"
            ]
            
            reset_count = 0
            for seq in sequences:
                try:
                    db.execute(text(f"ALTER SEQUENCE {seq} RESTART WITH 1"))
                    reset_count += 1
                except Exception as e:
                    print(f"   ⚠️  Sequence {seq} not found or already reset")
            
            if reset_count > 0:
                print(f"   ✅ Reset {reset_count} ID sequences to start from 1")
            
            # Commit all changes
            db.commit()
            
            print(f"\n🎉 Cleanup completed successfully!")
            print(f"   - Total documents deleted: {deleted_docs}")
            print(f"   - Total related records deleted: {deleted_comments + deleted_redactions + deleted_shares + deleted_content + deleted_jobs}")
            
        except Exception as e:
            print(f"❌ Error during cleanup: {str(e)}")
            db.rollback()
            raise
            
        finally:
            db.close()

if __name__ == "__main__":
    print("🚨 WARNING: This will permanently delete ALL documents and related data!")
    response = input("Are you sure you want to continue? Type 'yes' to confirm: ")
    
    if response.lower() == 'yes':
        cleanup_all_documents()
    else:
        print("❌ Cleanup cancelled.")