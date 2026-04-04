from fastapi import APIRouter

router = APIRouter()


@router.post("/entries")
async def create_entry():
    return {"message": "Create knowledge entry -- not yet implemented"}


@router.get("/entries")
async def list_entries():
    return {"message": "List knowledge entries -- not yet implemented"}


@router.get("/entries/{entry_id}")
async def get_entry(entry_id: str):
    return {"message": f"Get entry {entry_id} -- not yet implemented"}


@router.put("/entries/{entry_id}")
async def update_entry(entry_id: str):
    return {"message": f"Update entry {entry_id} -- not yet implemented"}


@router.delete("/entries/{entry_id}")
async def delete_entry(entry_id: str):
    return {"message": f"Delete entry {entry_id} -- not yet implemented"}
