#!/usr/bin/env python3
"""
Script to delete all documents and related data from the database.
This will clean up: documents, comments, redactions, document_shares, document_content, and processing_jobs.
"""

import os
import sys

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from app.db import SessionLocal, engine
from app.models import (
    Comment,
    Document,
    DocumentContent,
    DocumentShare,
    ProcessingJob,
    Redaction,
)


def cleanup_all_documents():
    """Delete all documents and related data"""

    db = SessionLocal()
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

        # Delete comments first (they reference documents)
        deleted_comments = db.query(Comment).delete(synchronize_session=False)
        print(f"   ✅ Deleted {deleted_comments} comments")

        # Delete redactions (they reference documents)
        deleted_redactions = db.query(Redaction).delete(synchronize_session=False)
        print(f"   ✅ Deleted {deleted_redactions} redactions")

        # Delete document shares (they reference documents)
        deleted_shares = db.query(DocumentShare).delete(synchronize_session=False)
        print(f"   ✅ Deleted {deleted_shares} document shares")

        # Delete document content (they reference documents)
        deleted_content = db.query(DocumentContent).delete(synchronize_session=False)
        print(f"   ✅ Deleted {deleted_content} document content entries")

        # Delete processing jobs (they reference documents)
        deleted_jobs = db.query(ProcessingJob).delete(synchronize_session=False)
        print(f"   ✅ Deleted {deleted_jobs} processing jobs")

        # Commit deletions of related records first
        db.commit()
        print("   ✅ Committed deletion of related records")

        # Finally delete documents
        print("\n🗂️  Deleting documents...")
        deleted_docs = db.query(Document).delete(synchronize_session=False)
        print(f"   ✅ Deleted {deleted_docs} documents")

        # Commit document deletions
        db.commit()
        print("   ✅ Committed document deletions")

        # Reset auto-increment sequences (PostgreSQL specific)
        print("\n🔄 Resetting ID sequences...")
        sequences = [
            "documents_id_seq",
            "comments_id_seq",
            "redactions_id_seq",
            "document_shares_id_seq",
            "document_content_id_seq",
            "processing_jobs_id_seq",
        ]

        reset_count = 0
        for seq in sequences:
            try:
                db.execute(text(f"ALTER SEQUENCE {seq} RESTART WITH 1"))
                reset_count += 1
            except Exception as e:
                print(f"   ⚠️  Sequence {seq} not found or already reset: {e}")

        if reset_count > 0:
            print(f"   ✅ Reset {reset_count} ID sequences to start from 1")

        # Final commit for sequence resets
        db.commit()
        print("   ✅ Committed sequence resets")

        # Verify cleanup
        final_doc_count = db.query(Document).count()
        final_comment_count = db.query(Comment).count()
        final_redaction_count = db.query(Redaction).count()
        final_job_count = db.query(ProcessingJob).count()

        print(f"\n🔍 Verification:")
        print(f"   - Remaining documents: {final_doc_count}")
        print(f"   - Remaining comments: {final_comment_count}")
        print(f"   - Remaining redactions: {final_redaction_count}")
        print(f"   - Remaining jobs: {final_job_count}")

        if final_doc_count == 0:
            print(f"\n🎉 Cleanup completed successfully!")
            print(f"   - Total documents deleted: {deleted_docs}")
            print(
                f"   - Total related records deleted: {deleted_comments + deleted_redactions + deleted_shares + deleted_content + deleted_jobs}"
            )
        else:
            print(f"\n⚠️  Warning: {final_doc_count} documents still remain!")

    except Exception as e:
        print(f"❌ Error during cleanup: {str(e)}")
        print(f"❌ Error type: {type(e).__name__}")
        import traceback

        traceback.print_exc()
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    print("🚨 WARNING: This will permanently delete ALL documents and related data!")
    response = input("Are you sure you want to continue? Type 'yes' to confirm: ")

    if response.lower() == "yes":
        cleanup_all_documents()
    else:
        print("❌ Cleanup cancelled.")
