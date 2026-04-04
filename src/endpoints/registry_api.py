from fastapi import APIRouter

router = APIRouter()


@router.get("/proposals")
async def list_proposals():
    return {"message": "List registry proposals -- not yet implemented"}


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: str):
    return {"message": f"Approve proposal {proposal_id} -- not yet implemented"}


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: str):
    return {"message": f"Reject proposal {proposal_id} -- not yet implemented"}


@router.get("/endpoints")
async def list_endpoints():
    return {"message": "List active dynamic endpoints -- not yet implemented"}
