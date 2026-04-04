from fastapi import APIRouter

router = APIRouter()


@router.get("/query")
async def query_structured():
    return {"message": "Structured query -- not yet implemented"}
