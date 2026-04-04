from fastapi import APIRouter

router = APIRouter()


@router.post("/query")
async def query_brain():
    return {"message": "Brain query -- not yet implemented"}
