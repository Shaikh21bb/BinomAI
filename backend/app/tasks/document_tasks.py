import asyncio
import uuid
import json
import structlog
from typing import Optional
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import async_task_session_factory as async_session_factory
from app.db.models.document import Document
from app.db.models.project import Project
from app.core.supabase import supabase_admin
from app.core.parsers import DocumentParser
from app.core.config import settings
from app.ai.llm_client import AIQuotaExhaustedError
from app.tasks.analysis_tasks import run_analysis_task

logger = structlog.get_logger(__name__)

async def process_document_async(task, document_id_str: str) -> dict:
    """Async core of the document processing pipeline."""
    document_id = uuid.UUID(document_id_str)
    
    async with async_session_factory() as db:
        try:
            # 1. Fetch document and update status
            stmt = select(Document).where(Document.id == document_id)
            result = await db.execute(stmt)
            doc = result.scalars().first()
            
            if not doc:
                logger.error("process_document_not_found", document_id=str(document_id))
                return {"status": "error", "message": "Document not found"}

            doc.processing_status = "processing"
            await db.commit()
            
            # Progress update
            task.update_state(state="PROGRESS", meta={"step": "Downloading document"})
            
            # 2. Download raw file from Supabase
            bucket = settings.STORAGE_BUCKET_TENDER_DOCS
            download_url = f"/storage/v1/object/{bucket}/{doc.storage_path}"
            
            async with supabase_admin.get_client() as client:
                response = await client.get(download_url)
                if response.status_code != 200:
                    raise Exception(f"Failed to download document from storage: {response.status_code}")
                file_bytes = response.content
                
            # 3. Extract text
            task.update_state(state="PROGRESS", meta={"step": "Extracting text"})
            doc.page_count = DocumentParser.get_page_count(file_bytes, doc.mime_type)
            if doc.mime_type == "application/pdf":
                raw_text = DocumentParser.extract_from_pdf(file_bytes)
            elif doc.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or doc.mime_type == "application/msword":
                raw_text = DocumentParser.extract_from_docx(file_bytes)
            else:
                raise Exception(f"Unsupported MIME type for extraction: {doc.mime_type}")
                
            # 4. Clean text
            task.update_state(state="PROGRESS", meta={"step": "Cleaning text"})
            cleaned_text = DocumentParser.clean_text(raw_text)
            if not cleaned_text.strip():
                raise Exception("No extractable text found in document (possibly a scanned PDF)")
            
            # 4b. Extract metadata (title, number, date) via regex heuristics
            meta = DocumentParser.extract_metadata(cleaned_text)
            if meta.get("title"):
                doc.doc_title = meta["title"]
            elif doc.filename:
                doc.doc_title = doc.filename.rsplit(".", 1)[0][:500]
            doc.doc_number = meta.get("number")
            doc.doc_date = meta.get("date")
            doc.language = DocumentParser.detect_language(cleaned_text)
            
            # 5. Chunking
            task.update_state(state="PROGRESS", meta={"step": "Chunking text"})
            chunks = DocumentParser.chunk_text(cleaned_text)
            
            # 6. Upload extracted content back to Storage
            task.update_state(state="PROGRESS", meta={"step": "Uploading extracted text"})
            extracted_bucket = "extracted-texts" # Hardcoded per schema implication or configurable
            base_path = f"{doc.company_id}/{doc.project_id}/{doc.id}"
            text_path = f"{base_path}.txt"
            chunks_path = f"{base_path}_chunks.json"
            
            async with supabase_admin.get_client() as client:
                # Need to use form-data or binary upload
                # Upload txt
                headers_txt = client.headers.copy()
                headers_txt["Content-Type"] = "text/plain"
                resp_txt = await client.post(
                    f"/storage/v1/object/{extracted_bucket}/{text_path}", 
                    content=cleaned_text.encode("utf-8"), 
                    headers=headers_txt
                )
                if resp_txt.status_code not in (200, 201):
                    raise Exception(f"Failed to upload extracted text: {resp_txt.status_code} {resp_txt.text}")
                
                # Upload json
                headers_json = client.headers.copy()
                headers_json["Content-Type"] = "application/json"
                resp_json = await client.post(
                    f"/storage/v1/object/{extracted_bucket}/{chunks_path}", 
                    content=json.dumps(chunks).encode("utf-8"), 
                    headers=headers_json
                )
                if resp_json.status_code not in (200, 201):
                    raise Exception(f"Failed to upload chunks: {resp_json.status_code} {resp_json.text}")
                
            # 7. Finalize in DB
            doc.extracted_text_path = text_path
            doc.processing_status = "ready"
            # We don't have token count calculation yet without AI/tiktoken, so leave it empty or map to char count / 4 roughly
            doc.token_count = len(cleaned_text) // 4
            await db.commit()
            
            # Update Project status if it's draft
            stmt_proj = select(Project).where(Project.id == doc.project_id)
            res_proj = await db.execute(stmt_proj)
            proj = res_proj.scalars().first()
            if proj and proj.status == "draft":
                proj.status = "analyzing" # Ready for AI
                await db.commit()
                
            # TRIGGER AI ANALYSIS automatically when document reaches ready
            run_analysis_task.delay(str(doc.project_id), str(doc.id), str(doc.company_id))

            return {"status": "success", "document_id": str(document_id)}
            
        except Exception as e:
            logger.error("process_document_failed", document_id=str(document_id), error=str(e))
            # Attempt to save error state
            try:
                # Refresh doc instance or just run update
                stmt_err = select(Document).where(Document.id == document_id)
                res_err = await db.execute(stmt_err)
                doc_err = res_err.scalars().first()
                if doc_err:
                    doc_err.processing_status = "error"
                    doc_err.error_message = str(e)
                    await db.commit()
            except Exception as db_err:
                logger.error("failed_to_save_error_state", error=str(db_err))
                
            raise e # Reraise for Celery retry mechanics

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_document(self, document_id_str: str):
    """
    Celery task wrapper to execute the async processing pipeline.
    """
    logger.info("celery_task_started", task_id=self.request.id, document_id=document_id_str)
    try:
        # Fail fast on malformed payloads (leftover test mocks etc.) — never retry garbage.
        uuid.UUID(document_id_str)
    except (ValueError, TypeError, AttributeError) as exc:
        logger.error("celery_task_invalid_args", task_id=self.request.id, error=str(exc))
        raise exc
    try:
        # Run async function in a new event loop
        result = asyncio.run(process_document_async(self, document_id_str))
        return result
    except AIQuotaExhaustedError as exc:
        # Daily quota exhaustion won't recover in seconds — do not waste retries
        logger.error("process_document_quota_exhausted", error=str(exc))
        raise exc
    except Exception as exc:
        logger.warning("celery_task_failed_retrying", exc=str(exc))
        raise self.retry(exc=exc)
