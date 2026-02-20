"""
Celery tasks for document processing.
Downloads files from MinIO, processes them through the RAG pipeline,
and updates the database with results.
"""

import os
import logging
import tempfile
import shutil

from backend.celery_app import celery_app
from backend.database import SessionLocal
from backend import models
from backend.services import minio_client

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_document_task(self, doc_id: int):
    """
    Async document processing task.
    1. Download file from MinIO to temp dir
    2. Run RAG pipeline (chunk, embed, upload to Qdrant)
    3. Update DB with status and chunk count
    """
    db = SessionLocal()
    temp_dir = None

    try:
        # Load document record
        doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
        if not doc:
            logger.error(f"Document {doc_id} not found in database")
            return {"status": "error", "detail": "Document not found"}

        # Update status to processing
        doc.processing_status = "processing"
        doc.task_id = self.request.id
        db.commit()

        logger.info(f"Processing document {doc_id}: {doc.filename}")

        # Download from MinIO to temp directory
        temp_dir = tempfile.mkdtemp()
        local_path = os.path.join(temp_dir, doc.filename)

        if doc.object_key:
            minio_client.download_file(doc.object_key, local_path)
        elif doc.file_path and os.path.exists(doc.file_path):
            # Fallback to local file if MinIO key not set
            shutil.copy2(doc.file_path, local_path)
        else:
            raise FileNotFoundError(f"No file source for document {doc_id}")

        # Process through RAG pipeline
        from backend.rag import pipeline as rag_pipeline

        num_chunks = rag_pipeline.process_pdf(
            local_path, doc.group_id, {"filename": doc.filename}
        )

        # Update document record
        doc.processing_status = "done"
        doc.chunk_count = num_chunks
        doc.processing_error = None

        db.commit()
        logger.info(f"Document {doc_id} processed successfully: {num_chunks} chunks")

        return {"status": "done", "doc_id": doc_id, "chunks": num_chunks}

    except Exception as exc:
        logger.error(f"Document {doc_id} processing failed: {exc}", exc_info=True)

        # Update DB with failure
        try:
            doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
            if doc:
                doc.processing_status = "failed"
                doc.processing_error = str(exc)[:500]
                db.commit()
        except Exception:
            pass

        # Retry if retries remain
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        return {"status": "failed", "doc_id": doc_id, "error": str(exc)[:200]}

    finally:
        db.close()
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
