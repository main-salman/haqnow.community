#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.db import SessionLocal
from app.models import Document, ProcessingJob

with SessionLocal() as db:
    recent_docs = db.query(Document).filter(Document.id >= 316).all()
    updated_count = 0
    
    for doc in recent_docs:
        jobs = db.query(ProcessingJob).filter(ProcessingJob.document_id == doc.id).all()
        all_completed = all(job.status == 'completed' for job in jobs)
        
        if all_completed and len(jobs) > 0 and doc.status != 'ready':
            doc.status = 'ready'
            updated_count += 1
            print(f'Updated document {doc.id}: {doc.title} to ready status')
    
    if updated_count > 0:
        db.commit()
        print(f'Updated {updated_count} document statuses')
    else:
        print('All document statuses are correct')