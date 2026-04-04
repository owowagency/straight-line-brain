import time

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Contact
from src.db.session import get_session
from src.schemas.retrieval import ContactCheckRequest, ContactCheckResponse, ContactResponse
from src.services.query_logger import log_query

router = APIRouter()


@router.post("/check", response_model=ContactCheckResponse)
async def check_contact(
    body: ContactCheckRequest,
    session: AsyncSession = Depends(get_session),
):
    """Check if a contact exists by company name or email (deduplication)."""
    t0 = time.perf_counter()

    conditions = [Contact.company_name.ilike(f"%{body.company_name}%")]
    if body.email:
        conditions.append(Contact.email.ilike(body.email))

    query = select(Contact).where(or_(*conditions)).limit(1)
    result = await session.execute(query)
    contact = result.scalar_one_or_none()

    ms = int((time.perf_counter() - t0) * 1000)
    await log_query(
        session,
        "contacts/check",
        f"company={body.company_name} email={body.email}",
        response_time_ms=ms,
    )
    await session.commit()

    if contact:
        return ContactCheckResponse(
            exists=True,
            contact=ContactResponse.model_validate(contact),
        )
    return ContactCheckResponse(exists=False)
