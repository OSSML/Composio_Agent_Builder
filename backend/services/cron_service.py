from datetime import datetime, UTC

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from croniter import croniter
from langchain_core.messages import HumanMessage
from sqlalchemy import select
from sqlalchemy.orm import joinedload
import structlog

from core.orm import (
    Assistant as AssistantORM,
    Cron as CronORM,
    CronRun as CronRunORM,
    _get_session_maker,
)
from misc.models import Cron, CronRun
from services.langgraph_service import get_langgraph_service

logger = structlog.getLogger(__name__)


async def run_cron_job(cron_run: CronRun, cron_job: Cron) -> dict:
    """
    Run a cron job based on the provided CronRun and Cron definitions.
    """
    logger.info(
        f"[{datetime.now(UTC)}] Running job for CronRun ID: {cron_run.cron_run_id}"
    )
    logger.info(f"  - Assistant ID: {cron_job.assistant_id}")
    logger.info(f"  - Required Fields: {cron_job.required_fields}")
    try:
        maker = _get_session_maker()
        async with (maker() as session):
            assistant_id = cron_job.assistant_id
            assistant_stmt = select(AssistantORM).where(
                AssistantORM.assistant_id == assistant_id,
            )
            assistant = await session.scalar(assistant_stmt)
            if not assistant:
                raise ("failed", f"Assistant with ID {assistant_id} not found.")

            langgraph_service = get_langgraph_service()
            graph = await langgraph_service.get_graph_raw(assistant.graph_id)

            user_prompt = (
                f"required_fields: {cron_job.required_fields}, \nspecial_instructions: {cron_job.special_instructions}"
                f"\nYou don't need to create the plan for the task, since the plan is already present in the prompt. You can create plan only if you find it necessary to complete the task."
                f"\nPlease complete the task as per the required fields and special instructions. And output if the task was completed successfully or not."
                f"\n Execute the task to completion without any interruptions or requests for clarification. This is a cron job, and you are expected to carry out the entire process independently. " +
                f"Ensure the final output includes the complete status of the task and any relevant details. Do not seek approval or ask for confirmations at any point."
            )
            input = {
                "messages": [HumanMessage(content=user_prompt)],
            }
            context = assistant.context

            context["system_prompt"] = (context["system_prompt"] +
                f"\n Execute the task to completion without any interruptions or requests for clarification. This is a cron job, and you are expected to carry out the entire process independently. " +
                f"Ensure the final output includes the complete status of the task and any relevant details. Do not seek approval or ask for confirmations at any point."
            )

            response = await graph.ainvoke(
                input, {"recursion_limit": 30}, context=assistant.context
            )
            output = response["messages"][-1].content
            for messages in response["messages"]:
                logger.info(f"  - Message: {messages.content}")
            output = {"status": "completed", "output": output}
            logger.info(
                f"[{datetime.now(UTC)}] Finished job for CronRun ID: {cron_run.cron_run_id}"
            )
            return output
    except Exception as e:
        output = {"status": "error", "output": str(e)}
        logger.error(
            f"[{datetime.now(UTC)}] Job failed for CronRun ID: {cron_run.cron_run_id}. Error: {e}"
        )
        return output


async def check_and_schedule_cron_jobs():
    """
    Checks the cron table for jobs whose schedule matches the current minute
    and creates a 'scheduled' CronRun entry.
    """
    maker = _get_session_maker()

    async with maker() as session:
        # Round current time to the beginning of the minute for accurate comparison
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        result = await session.execute(select(CronORM).where(CronORM.enabled))
        crons = result.scalars().all()
        for cron in crons:
            if not croniter.is_valid(cron.schedule):
                continue

            # Check if the cron's previous scheduled time matches the current minute
            base_time = datetime.now(UTC)
            cron_job = croniter(cron.schedule, base_time)
            if cron_job.get_prev(datetime) == now:
                new_cron_run = CronRunORM(cron_id=cron.cron_id, status="scheduled")
                session.add(new_cron_run)
                logger.info(f"[{now}] SCHEDULING cron run for cron_id: {cron.cron_id}")
        await session.commit()


async def run_scheduled_jobs():
    """
    Checks the CronRun table for 'scheduled' jobs and executes them.
    """
    maker = _get_session_maker()

    async with maker() as session:
        # Fetch scheduled jobs and their parent cron info
        stmt = (
            select(CronRunORM)
            .where(CronRunORM.status == "scheduled")
            .join(CronORM, CronRunORM.cron_id == CronORM.cron_id)
            .options(joinedload(CronRunORM.cron))
        )
        result = await session.execute(stmt)
        scheduled_runs = result.scalars().all()

        if not scheduled_runs:
            return

        logger.info(
            f"[{datetime.now(UTC)}] Found {len(scheduled_runs)} scheduled job(s) to run."
        )

        for run in scheduled_runs:
            # Mark the job as 'running' to prevent other workers from picking it up
            run.status = "running"
            run.started_at = datetime.now(UTC)
            await session.commit()

            cron = Cron.model_validate(run.cron)
            cron_run = CronRun.model_validate(run)

            # Execute the placeholder function
            output = await run_cron_job(cron_run, cron)

            # Update the record with the final status and output
            run.status = output["status"]
            run.output = output["output"]
            run.completed_at = datetime.now(UTC)
            await session.commit()


scheduler = AsyncIOScheduler()

# Job 1: Check every minute to see if a cron needs to be scheduled
scheduler.add_job(check_and_schedule_cron_jobs, "interval", minutes=1)

# Job 2: Check every 30 seconds to see if there are scheduled jobs to run
scheduler.add_job(run_scheduled_jobs, "interval", seconds=30)
