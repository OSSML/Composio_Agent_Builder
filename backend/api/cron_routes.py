from datetime import datetime, UTC
from typing import List

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from core.orm import Cron as CronORM, CronRun as CronRunORM, get_session
from misc.models import Cron, CronCreate, CronUpdate, CronRun

router = APIRouter()

logger = structlog.getLogger(__name__)


@router.post("/cron", response_model=Cron)
async def create_cron(
    cron_data: CronCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new cron job."""
    try:
        new_cron = CronORM(
            assistant_id=cron_data.assistant_id,
            schedule=cron_data.schedule,
            required_fields=cron_data.required_fields,
            special_instructions=cron_data.special_instructions,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(new_cron)
        await session.commit()
        await session.refresh(new_cron)
        return Cron.model_validate(new_cron, from_attributes=True)
    except Exception as e:
        raise HTTPException(500, f"Failed to create cron job: {str(e)}") from e


@router.post("/cron/{cron_id}", response_model=Cron)
async def update_cron(
    cron_id: str,
    cron_data: CronUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update an existing cron job."""
    try:
        result = await session.execute(
            select(CronORM).where(CronORM.cron_id == cron_id)
        )
        cron = result.scalars().first()
        if not cron:
            raise HTTPException(404, "Cron job not found")

        if cron_data.schedule is not None:
            cron.schedule = cron_data.schedule
        if cron_data.required_fields is not None:
            cron.required_fields = cron_data.required_fields
        if cron_data.special_instructions is not None:
            cron.special_instructions = cron_data.special_instructions
        if cron_data.enabled is not None:
            cron.enabled = cron_data.enabled

        cron.updated_at = datetime.now(UTC)

        session.add(cron)
        await session.commit()
        await session.refresh(cron)
        return Cron.model_validate(cron, from_attributes=True)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to update cron job: {str(e)}") from e


@router.delete("/cron/{cron_id}", response_model=dict)
async def delete_cron(
    cron_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete a cron job."""
    try:
        result = await session.execute(
            select(CronORM).where(CronORM.cron_id == cron_id)
        )
        cron = result.scalars().first()
        if not cron:
            raise HTTPException(404, "Cron job not found")

        await session.delete(cron)
        await session.commit()
        return {"message": "Cron job deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to delete cron job: {str(e)}") from e


@router.get("/cron", response_model=List[Cron])
async def list_crons(
    assistant_id: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """List all cron jobs."""
    try:
        stmt = select(CronORM)
        if assistant_id:
            stmt = stmt.where(CronORM.assistant_id == assistant_id)

        result = await session.execute(stmt)
        crons = result.scalars().all()
        return [Cron.model_validate(cron, from_attributes=True) for cron in crons]
    except Exception as e:
        raise HTTPException(500, f"Failed to list cron jobs: {str(e)}") from e


@router.get("/cron/{cron_id}", response_model=Cron)
async def get_cron(
    cron_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a cron job by ID."""
    try:
        result = await session.execute(
            select(CronORM).where(CronORM.cron_id == cron_id)
        )
        cron = result.scalars().first()
        if not cron:
            raise HTTPException(404, "Cron job not found")
        return Cron.model_validate(cron, from_attributes=True)

    except Exception as e:
        raise HTTPException(500, f"Failed to get cron job: {str(e)}") from e


@router.post("/cron/{cron_id}/run", response_model=CronRun)
async def run_cron_now(cron_id: str, session: AsyncSession = Depends(get_session)):
    """Trigger a cron job to run immediately."""
    try:
        result = await session.execute(
            select(CronORM).where(CronORM.cron_id == cron_id)
        )
        cron = result.scalars().first()
        if not cron:
            raise HTTPException(404, "Cron job not found")

        new_cron_run = CronRunORM(
            cron_id=cron.cron_id,
            status="scheduled",
            scheduled_at=datetime.now(UTC),
        )
        session.add(new_cron_run)
        await session.commit()
        await session.refresh(new_cron_run)

        return CronRun.model_validate(new_cron_run, from_attributes=True)
    except Exception as e:
        raise HTTPException(500, f"Failed to run cron job: {str(e)}") from e


@router.get("/cron/{cron_id}/runs", response_model=List[CronRun])
async def list_cron_runs(
    cron_id: str,
    session: AsyncSession = Depends(get_session),
):
    """List all runs for a specific cron job."""
    try:
        result = await session.execute(
            select(CronRunORM).where(CronRunORM.cron_id == cron_id)
        )
        cron_runs = result.scalars().all()
        return [
            CronRun.model_validate(cron_run, from_attributes=True)
            for cron_run in cron_runs
        ]
    except Exception as e:
        raise HTTPException(500, f"Failed to list cron runs: {str(e)}") from e
