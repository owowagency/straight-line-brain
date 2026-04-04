from fastapi import APIRouter

router = APIRouter()


@router.post("/document")
async def ingest_document():
    return {"message": "Document ingest -- not yet implemented"}


@router.post("/file")
async def ingest_file():
    return {"message": "File ingest -- not yet implemented"}


@router.post("/analytics")
async def ingest_analytics():
    return {"message": "Analytics ingest -- not yet implemented"}
