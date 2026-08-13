import uuid
import httpx
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import structlog

from app.core.config import settings
from app.core.supabase import supabase_admin
from app.db.repositories.document_repo import document_repo, DocumentCreate
from app.db.models.document import Document
from app.tasks.document_tasks import process_document

logger = structlog.get_logger(__name__)

class DocumentService:
    @staticmethod
    async def validate_file(file: UploadFile) -> None:
        """Validates file type and size."""
        # Note: file.size might be None in some FastAPI setups before read, 
        # but if populated, we check it.
        if file.size and file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB")
            
        if file.content_type not in settings.parsed_allowed_mime_types:
            raise HTTPException(status_code=415, detail=f"Unsupported file type. Allowed: {settings.ALLOWED_MIME_TYPES}")

    @staticmethod
    async def upload_to_storage(company_id: uuid.UUID, project_id: uuid.UUID, file: UploadFile) -> str:
        """Uploads file to Supabase storage and returns the storage path."""
        file_ext = file.filename.split('.')[-1] if '.' in file.filename else ''
        file_uuid = str(uuid.uuid4())
        storage_path = f"{company_id}/{project_id}/{file_uuid}.{file_ext}"
        
        file_content = await file.read()
        await file.seek(0) # Reset pointer
        
        # Real file size check if file.size was not reliable
        if len(file_content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large")

        # Upload to Supabase using HTTPX client
        bucket = settings.STORAGE_BUCKET_TENDER_DOCS
        upload_url = f"/storage/v1/object/{bucket}/{storage_path}"
        
        async with supabase_admin.get_client(timeout=120.0) as client:
            # We must override Content-Type for binary upload
            headers = client.headers.copy()
            headers["Content-Type"] = file.content_type or "application/octet-stream"
            
            response = await client.post(upload_url, content=file_content, headers=headers)
            
            if response.status_code >= 400:
                logger.error("supabase_storage_upload_failed", status=response.status_code, body=response.text)
                raise HTTPException(status_code=500, detail="Failed to upload file to storage")
                
        return storage_path

    @staticmethod
    async def get_signed_download_url(storage_path: str, expires_in: int = 60) -> str:
        """Create a short-lived signed URL for downloading a stored document."""
        bucket = settings.STORAGE_BUCKET_TENDER_DOCS
        sign_url = f"/storage/v1/object/sign/{bucket}/{storage_path}"
        async with supabase_admin.get_client() as client:
            resp = await client.post(sign_url, json={"expiresIn": expires_in})
            if resp.status_code >= 300:
                logger.warning(
                    "supabase_storage_sign_failed", path=storage_path, bucket=bucket,
                    status=resp.status_code, body=resp.text[:200],
                )
                raise HTTPException(status_code=404, detail="Файл не найден в хранилище")
            data = resp.json()
        signed = data.get("signedURL") or data.get("signedUrl") or ""
        if not signed:
            raise HTTPException(status_code=404, detail="Не удалось получить ссылку на файл")
        base = settings.SUPABASE_URL.rstrip("/")
        return base + (signed if signed.startswith("/") else f"/{signed}")

    @staticmethod
    async def delete_from_storage(storage_path: str, bucket: str = None) -> None:
        """Deletes a file from Supabase storage."""
        bucket = bucket or settings.STORAGE_BUCKET_TENDER_DOCS
        delete_url = f"/storage/v1/object/{bucket}/{storage_path}"
        
        async with supabase_admin.get_client() as client:
            resp = await client.request("DELETE", delete_url, json={})
            if resp.status_code >= 300:
                logger.warning("supabase_storage_delete_failed", path=storage_path, bucket=bucket, status=resp.status_code, body=resp.text[:200])
                return
            logger.info("supabase_storage_file_deleted", path=storage_path, bucket=bucket)

    @staticmethod
    async def create_document(
        db: AsyncSession, 
        project_id: uuid.UUID, 
        company_id: uuid.UUID, 
        user_id: uuid.UUID, 
        file: UploadFile
    ) -> Document:
        """Full flow: Validate, Upload, Database Insert"""
        await DocumentService.validate_file(file)
        
        storage_path = await DocumentService.upload_to_storage(company_id, project_id, file)
        
        doc_in = DocumentCreate(
            filename=file.filename,
            file_size_bytes=file.size or 0,
            mime_type=file.content_type or "application/octet-stream",
            storage_path=storage_path,
            project_id=project_id,
            company_id=company_id,
            uploaded_by=user_id,
            version=(await document_repo.get_max_version(db, project_id=project_id)) + 1,
        )
        # Supersede previously current documents (versioning on re-upload)
        await document_repo.supersede_previous(db, project_id=project_id)
        
        try:
            document = await document_repo.create(db, obj_in=doc_in)
            logger.info("document_created", document_id=str(document.id), project_id=str(project_id))
            
            # Enqueue the background processing task
            process_document.delay(str(document.id))
            logger.info("document_processing_enqueued", document_id=str(document.id))
            
            return document
        except Exception as e:
            # Cleanup orphaned file in storage
            logger.error("document_db_insert_failed", error=str(e), path=storage_path)
            await DocumentService.delete_from_storage(storage_path)
            raise HTTPException(status_code=500, detail="Failed to save document metadata")

    @staticmethod
    async def get_current_documents(db: AsyncSession, project_id: uuid.UUID) -> List[Document]:
        return await document_repo.get_current_documents_for_project(db, project_id=project_id)

    @staticmethod
    async def get_document_history(db: AsyncSession, project_id: uuid.UUID) -> List[Document]:
        return await document_repo.get_all_for_project(db, project_id=project_id)
