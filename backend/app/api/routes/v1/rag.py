"""RAG API routes for collection management, search, document upload, and deletion."""

import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse

from app.api.deps import (
    CurrentAdmin,
    CurrentUser,
    IngestionSvc,
    RAGDocumentSvc,
    RAGSyncSvc,
    RetrievalSvc,
    SyncSourceSvc,
    VectorStoreSvc,
)
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.schemas.rag import (
    RAGCollectionInfo,
    RAGCollectionList,
    RAGDocumentItem,
    RAGDocumentList,
    RAGIngestResponse,
    RAGMessageResponse,
    RAGRetryResponse,
    RAGSearchRequest,
    RAGSearchResponse,
    RAGSearchResult,
    RAGSyncLogItem,
    RAGSyncLogList,
    RAGSyncRequest,
    RAGSyncResponse,
    RAGTrackedDocumentItem,
    RAGTrackedDocumentList,
)
from app.schemas.sync_source import (
    ConnectorConfigField,
    ConnectorInfo,
    ConnectorList,
    SyncSourceCreate,
    SyncSourceList,
    SyncSourceRead,
    SyncSourceUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/supported-formats")
async def get_supported_formats_endpoint() -> Any:
    """Return file formats supported by the current PDF parser configuration."""
    from app.rag.config import get_supported_formats

    parser_name = "pymupdf"
    return {"parser": parser_name, "formats": sorted(get_supported_formats(parser_name))}


@router.get("/collections", response_model=RAGCollectionList)
async def list_collections(
    vector_store: VectorStoreSvc,
    _: CurrentAdmin,
) -> Any:
    """List all available collections in the vector store."""
    names = await vector_store.list_collections()
    return RAGCollectionList(items=names)


@router.post(
    "/collections/{name}", status_code=status.HTTP_201_CREATED, response_model=RAGMessageResponse
)
async def create_collection(
    name: str,
    vector_store: VectorStoreSvc,
    _: CurrentAdmin,
) -> Any:
    """Create and initialize a new collection."""
    import re

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$", name):
        raise HTTPException(
            status_code=400,
            detail="Collection name must start with a letter and contain only letters, numbers, and underscores (max 64 chars)",
        )
    if name.lower() == "all":
        raise HTTPException(status_code=400, detail="'all' is a reserved collection name")
    await vector_store._ensure_collection(name)  # type: ignore[attr-defined]
    return RAGMessageResponse(message=f"Collection '{name}' created successfully.")


@router.delete("/collections/{name}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def drop_collection(
    name: str,
    vector_store: VectorStoreSvc,
    rag_doc_svc: RAGDocumentSvc,
    _: CurrentAdmin,
) -> None:
    """Drop an entire collection — vectors and all SQL document records."""
    await vector_store.delete_collection(name)
    await rag_doc_svc.delete_by_collection(name)


@router.get("/collections/{name}/info", response_model=RAGCollectionInfo)
async def get_collection_info(
    name: str,
    vector_store: VectorStoreSvc,
    _: CurrentAdmin,
) -> Any:
    """Retrieve stats for a specific collection."""
    return await vector_store.get_collection_info(name)


@router.get("/collections/{name}/documents", response_model=RAGDocumentList)
async def list_documents(
    name: str,
    vector_store: VectorStoreSvc,
    _: CurrentAdmin,
) -> Any:
    """List all documents in a specific collection."""
    documents = await vector_store.get_documents(name)
    return RAGDocumentList(
        items=[
            RAGDocumentItem(
                document_id=doc.document_id,
                filename=doc.filename,
                filesize=doc.filesize,
                filetype=doc.filetype,
                chunk_count=doc.chunk_count,
                additional_info=doc.additional_info,
            )
            for doc in documents
        ],
        total=len(documents),
    )


@router.post("/search", response_model=RAGSearchResponse)
async def search_documents(
    request: RAGSearchRequest,
    retrieval_service: RetrievalSvc,
    current_user: CurrentUser,
    use_reranker: bool = Query(False, description="Whether to use reranking (if configured)"),
) -> Any:
    """Search for relevant document chunks. Supports multi-collection search."""
    if request.collection_names and len(request.collection_names) > 1:
        results = await retrieval_service.retrieve_multi(
            query=request.query,
            collection_names=request.collection_names,
            limit=request.limit,
            min_score=request.min_score,
            use_reranker=use_reranker,
        )
    else:
        collection = (
            request.collection_names[0] if request.collection_names else request.collection_name
        )
        results = await retrieval_service.retrieve(
            query=request.query,
            collection_name=collection,
            limit=request.limit,
            min_score=request.min_score,
            filter=request.filter or "",
            use_reranker=use_reranker,
        )
    api_results = [RAGSearchResult(**hit.model_dump()) for hit in results]
    return RAGSearchResponse(results=api_results)


@router.delete(
    "/collections/{name}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_document(
    name: str,
    document_id: str,
    ingestion_service: IngestionSvc,
    _: CurrentAdmin,
) -> None:
    """Delete a specific document by its ID from a collection."""
    success = await ingestion_service.remove_document(name, document_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


@router.post(
    "/collections/{name}/ingest", response_model=RAGIngestResponse, response_model_exclude_none=True
)
async def ingest_file(
    name: str,
    background_tasks: BackgroundTasks,
    rag_doc_svc: RAGDocumentSvc,
    ingestion_service: IngestionSvc,
    vector_store: VectorStoreSvc,
    _: CurrentAdmin,
    file: UploadFile = File(...),
    replace: bool = Query(False),
) -> Any:
    """Upload and ingest a file into a collection. Tracks status in DB."""

    from app.core.config import settings as app_settings
    from app.rag.config import get_supported_formats

    ALLOWED = get_supported_formats("pymupdf")
    max_size = app_settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not supported. Allowed: {', '.join(sorted(ALLOWED))}",
        )

    data = await file.read()
    if len(data) > max_size:
        raise HTTPException(
            status_code=413, detail=f"File too large. Maximum {app_settings.MAX_UPLOAD_SIZE_MB}MB."
        )

    from app.services.file_storage import get_file_storage

    storage = get_file_storage()
    storage_path = await storage.save(f"rag/{name}", filename, data)
    rag_doc = await rag_doc_svc.create_document(
        collection_name=name,
        filename=filename,
        filesize=len(data),
        filetype=ext.lstrip("."),
        storage_path=storage_path,
    )
    doc_id = rag_doc.id

    await vector_store._ensure_collection(name)  # type: ignore[attr-defined]

    import os

    tmp_dir = os.path.join(tempfile.gettempdir(), "rag_ingest")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, f"{doc_id!s}{ext}")
    with open(tmp_path, "wb") as f:
        f.write(data)

    async def _ingest_in_background(
        doc_id_str: str, collection: str, fpath: str, source: str, do_replace: bool
    ) -> None:
        """Run ingestion via FastAPI BackgroundTasks."""
        from app.db.session import get_db_context
        from app.rag.documents import DocumentProcessor
        from app.rag.embeddings import EmbeddingService
        from app.rag.ingestion import IngestionService
        from app.rag.vectorstore import PgVectorStore
        from app.services.rag_document import RAGDocumentService

        try:
            embedder = EmbeddingService(settings=settings.rag)
            vector_store = PgVectorStore(settings=settings.rag, embedding_service=embedder)
            svc = IngestionService(
                processor=DocumentProcessor(settings=settings.rag), vector_store=vector_store
            )
            result = await svc.ingest_file(
                filepath=Path(fpath),
                collection_name=collection,
                replace=do_replace,
                source_path=source,
            )
            async with get_db_context() as bg_db:
                bg_doc_svc = RAGDocumentService(bg_db)
                await bg_doc_svc.complete_ingestion(
                    doc_id_str,
                    vector_document_id=result.document_id,
                    chunk_count=result.chunk_count,
                )
        except Exception as exc:
            logger.error(f"Background ingestion failed: {exc}")
            async with get_db_context() as bg_db:
                bg_doc_svc = RAGDocumentService(bg_db)
                await bg_doc_svc.fail_ingestion(doc_id_str, error_message=str(exc))
        finally:
            Path(fpath).unlink(missing_ok=True)

    background_tasks.add_task(_ingest_in_background, str(doc_id), name, tmp_path, filename, replace)

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "id": str(doc_id),
            "status": "processing",
            "filename": filename,
            "collection": name,
            "message": "File accepted. Processing in background.",
        },
    )


@router.get("/documents", response_model=RAGTrackedDocumentList)
async def list_rag_documents(
    rag_doc_svc: RAGDocumentSvc,
    _: CurrentAdmin,
    collection_name: str | None = Query(None),
) -> Any:
    """List tracked RAG documents."""
    docs = await rag_doc_svc.list_documents(collection_name)
    return RAGTrackedDocumentList(
        items=[
            RAGTrackedDocumentItem(
                id=str(d.id),
                collection_name=d.collection_name,
                filename=d.filename,
                filesize=d.filesize,
                filetype=d.filetype,
                status=d.status,
                error_message=d.error_message,
                vector_document_id=d.vector_document_id,
                chunk_count=d.chunk_count,
                has_file=bool(d.storage_path),
                created_at=d.created_at.isoformat() if d.created_at else None,
                completed_at=d.completed_at.isoformat() if d.completed_at else None,
            )
            for d in docs
        ],
        total=len(docs),
    )


@router.get("/documents/{doc_id}/download")
async def download_rag_document(
    doc_id: str,
    rag_doc_svc: RAGDocumentSvc,
    _: CurrentAdmin,
) -> Any:
    """Download the original file."""

    from fastapi.responses import FileResponse

    try:
        file_path, filename, mime_type = await rag_doc_svc.get_download_info(doc_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
    return FileResponse(path=file_path, filename=filename, media_type=mime_type)


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_rag_document(
    doc_id: str,
    rag_doc_svc: RAGDocumentSvc,
    ingestion_service: IngestionSvc,
    _: CurrentAdmin,
) -> None:
    """Delete a document from SQL, vector store, and file storage."""

    try:
        await rag_doc_svc.delete_document(doc_id, ingestion_service)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@router.post("/documents/{doc_id}/retry", response_model=RAGRetryResponse)
async def retry_ingestion(
    doc_id: str,
    rag_doc_svc: RAGDocumentSvc,
    _: CurrentAdmin,
) -> Any:
    """Retry a failed document ingestion."""

    try:
        doc = await rag_doc_svc.retry_ingestion(doc_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return RAGRetryResponse(id=str(doc.id), status="processing", message="Retry queued")


@router.get("/sync/logs", response_model=RAGSyncLogList)
async def list_sync_logs(
    rag_sync_svc: RAGSyncSvc,
    _: CurrentAdmin,
    collection_name: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> Any:
    """List sync operation logs."""
    logs = await rag_sync_svc.list_sync_logs(collection_name=collection_name, limit=limit)
    return RAGSyncLogList(
        items=[
            RAGSyncLogItem(
                id=str(log.id),
                source=log.source,
                collection_name=log.collection_name,
                status=log.status,
                mode=log.mode,
                total_files=log.total_files,
                ingested=log.ingested,
                updated=log.updated,
                skipped=log.skipped,
                failed=log.failed,
                error_message=log.error_message,
                started_at=log.started_at.isoformat() if log.started_at else None,
                completed_at=log.completed_at.isoformat() if log.completed_at else None,
            )
            for log in logs
        ],
        total=len(logs),
    )


@router.post("/sync/local", response_model=RAGSyncResponse)
async def trigger_local_sync(
    request: RAGSyncRequest,
    background_tasks: BackgroundTasks,
    rag_sync_svc: RAGSyncSvc,
    _: CurrentAdmin,
) -> Any:
    """Trigger a local directory sync via background task."""
    sync_log = await rag_sync_svc.create_sync_log(
        source="local",
        collection_name=request.collection_name,
        mode=request.mode,
    )
    from app.db.session import get_db_context

    async def _sync_in_background(log_id: str, collection: str, mode: str, path: str) -> None:
        """Run sync via FastAPI BackgroundTasks."""
        from app.rag.documents import DocumentProcessor
        from app.rag.embeddings import EmbeddingService
        from app.rag.ingestion import IngestionService
        from app.rag.vectorstore import PgVectorStore
        from app.services.rag_sync import RAGSyncService

        embedder = EmbeddingService(settings=settings.rag)
        vector_store = PgVectorStore(settings=settings.rag, embedding_service=embedder)
        svc = IngestionService(
            processor=DocumentProcessor(settings=settings.rag), vector_store=vector_store
        )
        ingested = skipped = failed = total = 0

        try:
            target = Path(path)
            files = list(target.rglob("*")) if target.is_dir() else [target]
            files = [f for f in files if f.is_file()]
            total = len(files)

            for filepath in files:
                try:
                    await svc.ingest_file(
                        filepath=filepath,
                        collection_name=collection,
                        replace=(mode == "full"),
                        source_path=str(filepath),
                    )
                    ingested += 1
                except Exception as e:
                    logger.warning(f"Failed to ingest {filepath}: {e}")
                    failed += 1
        except Exception as e:
            logger.error(f"Sync failed: {e}")

        async with get_db_context() as bg_db:
            bg_sync_svc = RAGSyncService(bg_db)
            try:
                await bg_sync_svc.complete_sync(
                    log_id,
                    status="done" if not failed else "error",
                    total_files=total,
                    ingested=ingested,
                    skipped=skipped,
                    failed=failed,
                )
            except NotFoundError:
                logger.error(f"Sync log {log_id} not found during background update")

    background_tasks.add_task(
        _sync_in_background, str(sync_log.id), request.collection_name, request.mode, request.path
    )

    return RAGSyncResponse(
        id=str(sync_log.id),
        status="running",
        message=f"Sync started for '{request.collection_name}' (mode={request.mode})",
    )


@router.delete("/sync/{sync_id}", response_model=RAGMessageResponse)
async def cancel_sync(
    sync_id: str,
    rag_sync_svc: RAGSyncSvc,
    _: CurrentAdmin,
) -> Any:
    """Cancel a running sync operation."""

    try:
        await rag_sync_svc.cancel_sync(sync_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return RAGMessageResponse(message="Sync cancelled")


# --- Sync Source CRUD ---


@router.get("/sync/sources", response_model=SyncSourceList)
async def list_sync_sources(
    sync_source_svc: SyncSourceSvc,
    _: CurrentAdmin,
) -> Any:
    """List all configured sync sources."""
    sources = await sync_source_svc.list_sources()
    return SyncSourceList(
        items=[
            SyncSourceRead(
                id=str(s.id),
                name=s.name,
                connector_type=s.connector_type,
                collection_name=s.collection_name,
                config=s.config
                if isinstance(s.config, dict)
                else json.loads(s.config)
                if s.config
                else {},
                sync_mode=s.sync_mode,
                schedule_minutes=s.schedule_minutes,
                is_active=s.is_active,
                last_sync_at=s.last_sync_at.isoformat() if s.last_sync_at else None,
                last_sync_status=s.last_sync_status,
                last_error=s.last_error,
                created_at=s.created_at.isoformat() if s.created_at else None,
            )
            for s in sources
        ],
        total=len(sources),
    )


@router.post("/sync/sources", response_model=SyncSourceRead, status_code=status.HTTP_201_CREATED)
async def create_sync_source(
    data: SyncSourceCreate,
    sync_source_svc: SyncSourceSvc,
    _: CurrentAdmin,
) -> Any:
    """Create a new sync source configuration."""

    try:
        source = await sync_source_svc.create_source(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return SyncSourceRead(
        id=str(source.id),
        name=source.name,
        connector_type=source.connector_type,
        collection_name=source.collection_name,
        config=source.config
        if isinstance(source.config, dict)
        else json.loads(source.config)
        if source.config
        else {},
        sync_mode=source.sync_mode,
        schedule_minutes=source.schedule_minutes,
        is_active=source.is_active,
        last_sync_at=None,
        last_sync_status=None,
        last_error=None,
        created_at=source.created_at.isoformat() if source.created_at else None,
    )


@router.patch("/sync/sources/{source_id}", response_model=SyncSourceRead)
async def update_sync_source(
    source_id: str,
    data: SyncSourceUpdate,
    sync_source_svc: SyncSourceSvc,
    _: CurrentAdmin,
) -> Any:
    """Update an existing sync source configuration."""

    try:
        source = await sync_source_svc.update_source(source_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
    return SyncSourceRead(
        id=str(source.id),
        name=source.name,
        connector_type=source.connector_type,
        collection_name=source.collection_name,
        config=source.config
        if isinstance(source.config, dict)
        else json.loads(source.config)
        if source.config
        else {},
        sync_mode=source.sync_mode,
        schedule_minutes=source.schedule_minutes,
        is_active=source.is_active,
        last_sync_at=source.last_sync_at.isoformat() if source.last_sync_at else None,
        last_sync_status=source.last_sync_status,
        last_error=source.last_error,
        created_at=source.created_at.isoformat() if source.created_at else None,
    )


@router.delete(
    "/sync/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def delete_sync_source(
    source_id: str,
    sync_source_svc: SyncSourceSvc,
    _: CurrentAdmin,
) -> None:
    """Delete a sync source configuration."""

    try:
        await sync_source_svc.delete_source(source_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@router.post("/sync/sources/{source_id}/trigger", response_model=RAGSyncResponse)
async def trigger_sync_source(
    source_id: str,
    background_tasks: BackgroundTasks,
    sync_source_svc: SyncSourceSvc,
    _: CurrentAdmin,
) -> Any:
    """Trigger a manual sync for a configured source."""

    try:
        sync_log = await sync_source_svc.trigger_sync(source_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e

    # Dispatch background task to execute the sync
    async def _run_source_sync_bg(src_id: str, log_id: str) -> None:
        """Execute sync via FastAPI BackgroundTasks."""
        import tempfile
        from pathlib import Path

        from app.db.session import get_db_context
        from app.rag.connectors import CONNECTOR_REGISTRY
        from app.rag.documents import DocumentProcessor
        from app.rag.embeddings import EmbeddingService
        from app.rag.ingestion import IngestionService
        from app.rag.vectorstore import PgVectorStore
        from app.services.sync_source import SyncSourceService

        async with get_db_context() as bg_db:
            svc = SyncSourceService(bg_db)
            try:
                source = await svc.get_source(src_id)
                connector_cls = CONNECTOR_REGISTRY.get(source.connector_type)
                if not connector_cls:
                    await svc.complete_sync(
                        log_id,
                        status="error",
                        error_message=f"Unknown connector: {source.connector_type}",
                    )
                    return
                connector = connector_cls()
                config = source.config if isinstance(source.config, dict) else {}
                files = await connector.list_files(config)
                _embedder = EmbeddingService(settings=settings.rag)
                _vstore = PgVectorStore(settings=settings.rag, embedding_service=_embedder)
                ingestion = IngestionService(
                    processor=DocumentProcessor(settings=settings.rag), vector_store=_vstore
                )
                ingested = failed = 0
                with tempfile.TemporaryDirectory() as tmp_dir:
                    for f in files:
                        try:
                            local_path = await connector.download_file(f, Path(tmp_dir))
                            await ingestion.ingest_file(
                                filepath=local_path,
                                collection_name=source.collection_name,
                                replace=(source.sync_mode == "full"),
                                source_path=f.source_path,
                            )
                            ingested += 1
                        except Exception as e:
                            logger.warning(f"Sync file failed {f.name}: {e}")
                            failed += 1
                await svc.complete_sync(
                    log_id,
                    status="done" if not failed else "error",
                    total_files=len(files),
                    ingested=ingested,
                    failed=failed,
                )
            except Exception as e:
                logger.error(f"Source sync failed: {e}")
                await svc.complete_sync(log_id, status="error", error_message=str(e))

    background_tasks.add_task(_run_source_sync_bg, source_id, str(sync_log.id))

    return RAGSyncResponse(
        id=str(sync_log.id),
        status="running",
        message=f"Sync triggered for source '{source_id}'",
    )


@router.get("/sync/connectors", response_model=ConnectorList)
async def list_connectors(
    _: CurrentAdmin,
) -> Any:
    """List available sync connector types with their config schemas."""
    from app.rag.connectors import CONNECTOR_REGISTRY

    items = []
    for _connector_type, connector_cls in CONNECTOR_REGISTRY.items():
        schema_fields = {}
        for field_name, field_spec in connector_cls.CONFIG_SCHEMA.items():
            schema_fields[field_name] = ConnectorConfigField(**field_spec)
        items.append(
            ConnectorInfo(
                type=connector_cls.CONNECTOR_TYPE,
                name=connector_cls.DISPLAY_NAME,
                config_schema=schema_fields,
                enabled=True,
            )
        )
    return ConnectorList(items=items)
