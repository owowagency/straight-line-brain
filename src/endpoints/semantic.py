from fastapi import APIRouter

router = APIRouter()


@router.post("/search")
async def search_semantic():
    return {"message": "Semantic search -- not yet implemented"}
