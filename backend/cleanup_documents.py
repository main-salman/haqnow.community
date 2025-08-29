#!/usr/bin/env python3
"""
Script to delete all documents and related data from the database.
This will clean up: documents, comments, redactions, document_shares, document_content, and processing_jobs.

This script runs remotely on the server using SSH connection.
"""

import os
import subprocess
import sys
from pathlib import Path


def load_env_config():
    """Load configuration from .env file"""
    env_path = Path(__file__).parent.parent / ".env"

    if not env_path.exists():
        raise FileNotFoundError(f"❌ .env file not found at {env_path}")

    config = {}
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()

    return config


def run_remote_cleanup():
    """Run the cleanup script on the remote server via SSH"""
    try:
        # Load configuration
        config = load_env_config()
        server_ip = config.get("SERVER_IP")

        if not server_ip:
            raise ValueError("❌ SERVER_IP not found in .env file")

        print(f"🌐 Connecting to server: {server_ip}")

        # SSH key path
        ssh_key_path = Path.home() / ".ssh" / "haqnow_deploy_key"

        if not ssh_key_path.exists():
            raise FileNotFoundError(f"❌ SSH key not found at {ssh_key_path}")

        # Create the cleanup script content to run on the server
        cleanup_script = '''
import sys
sys.path.insert(0, '/app')

from app.models import Comment, Document, DocumentContent, DocumentShare, ProcessingJob, Redaction, DocumentText
from app.db import SessionLocal
from sqlalchemy import text

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
        print("\\n🔄 Deleting related data...")

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

        # Delete OCR text (they reference documents)
        deleted_doc_text = db.query(DocumentText).delete(synchronize_session=False)
        print(f"   ✅ Deleted {deleted_doc_text} document OCR text entries")

        # Delete processing jobs (they reference documents)
        deleted_jobs = db.query(ProcessingJob).delete(synchronize_session=False)
        print(f"   ✅ Deleted {deleted_jobs} processing jobs")

        # Commit deletions of related records first
        db.commit()
        print("   ✅ Committed deletion of related records")

        # Finally delete documents
        print("\\n🗂️  Deleting documents...")
        deleted_docs = db.query(Document).delete(synchronize_session=False)
        print(f"   ✅ Deleted {deleted_docs} documents")

        # Commit document deletions
        db.commit()
        print("   ✅ Committed document deletions")

        # Reset auto-increment sequences (PostgreSQL specific)
        print("\\n🔄 Resetting ID sequences...")
        sequences = [
            "documents_id_seq",
            "comments_id_seq",
            "redactions_id_seq",
            "document_shares_id_seq",
            "document_content_id_seq",
            "document_texts_id_seq",
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

        print(f"\\n🔍 Verification:")
        print(f"   - Remaining documents: {final_doc_count}")
        print(f"   - Remaining comments: {final_comment_count}")
        print(f"   - Remaining redactions: {final_redaction_count}")
        print(f"   - Remaining jobs: {final_job_count}")

        if final_doc_count == 0:
            print(f"\\n🎉 Cleanup completed successfully!")
            print(f"   - Total documents deleted: {deleted_docs}")
            print(f"   - Total related records deleted: {deleted_comments + deleted_redactions + deleted_shares + deleted_content + deleted_jobs}")
        else:
            print(f"\\n⚠️  Warning: {final_doc_count} documents still remain!")

    except Exception as e:
        print(f"❌ Error during cleanup: {str(e)}")
        print(f"❌ Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        db.close()

cleanup_all_documents()
'''

        # Create a temporary script file locally
        temp_script_path = Path("/tmp/remote_cleanup.py")

        print("📝 Creating temporary cleanup script...")
        with open(temp_script_path, "w") as f:
            f.write(cleanup_script)

        # Copy the script to the server in the project directory (accessible to Docker)
        scp_command = [
            "scp",
            "-i",
            str(ssh_key_path),
            str(temp_script_path),
            f"ubuntu@{server_ip}:/opt/haqnow-community/remote_cleanup.py",
        ]

        print("📤 Copying script to server...")
        result = subprocess.run(scp_command, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"❌ Failed to copy script to server: {result.stderr}")
            temp_script_path.unlink(missing_ok=True)  # Clean up local temp file
            return False

        # Now run the script on the server (copy it into the container and run it)
        ssh_command = [
            "ssh",
            "-i",
            str(ssh_key_path),
            f"ubuntu@{server_ip}",
            "cd /opt/haqnow-community/deploy && docker-compose cp ../remote_cleanup.py api:/app/remote_cleanup.py && docker-compose exec -T api python3 /app/remote_cleanup.py && rm -f ../remote_cleanup.py",
        ]

        print("🚀 Executing cleanup on remote server...")
        result = subprocess.run(ssh_command, capture_output=True, text=True)

        # Clean up local temp file
        temp_script_path.unlink(missing_ok=True)

        if result.returncode == 0:
            print("✅ Remote cleanup completed successfully!")
            print("\n📋 Server output:")
            print(result.stdout)
        else:
            print("❌ Remote cleanup failed!")
            print(f"Error code: {result.returncode}")
            print(f"Error output: {result.stderr}")
            print(f"Standard output: {result.stdout}")

        return result.returncode == 0

    except Exception as e:
        print(f"❌ Error running remote cleanup: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🚨 WARNING: This will permanently delete ALL documents and related data!")
    print("🌐 This will connect to the remote server and run the cleanup there.")
    response = input("Are you sure you want to continue? Type 'yes' to confirm: ")

    if response.lower() == "yes":
        success = run_remote_cleanup()
        if success:
            print("\n🎉 Remote cleanup completed successfully!")
        else:
            print("\n❌ Remote cleanup failed!")
            sys.exit(1)
    else:
        print("❌ Cleanup cancelled.")
