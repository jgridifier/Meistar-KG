"""Meistar-KG FastAPI application."""

from __future__ import annotations

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.models.schemas import (
    CreateSessionRequest,
    QARequest,
    QAResponse,
    Session,
)
from backend.pipeline.cost_tracker import get_all_costs, get_session_costs

app = FastAPI(title="Meistar-KG", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store (replace with DB later)
_sessions: dict[str, Session] = {}


@app.post("/sessions", response_model=Session)
async def create_session(
    req: CreateSessionRequest,
    background_tasks: BackgroundTasks,
) -> Session:
    """Start processing a paper from a URL."""
    from backend.agents.ingestion import run_ingestion

    session = Session(paper_url=req.paper_url)
    _sessions[session.id] = session

    background_tasks.add_task(
        run_ingestion,
        session.id,
        _sessions,
        llm_provider=req.llm_provider,
    )

    return session


@app.get("/sessions/{session_id}", response_model=Session)
async def get_session(session_id: str) -> Session:
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/sessions/{session_id}/script")
async def get_script(session_id: str) -> list:
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.script


@app.post("/sessions/{session_id}/qa", response_model=QAResponse)
async def qa(session_id: str, req: QARequest) -> QAResponse:
    """Standby Q&A agent endpoint."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # TODO: invoke Q&A agent with session context + question
    return QAResponse(answer="[Q&A agent not yet implemented]")


@app.get("/sessions/{session_id}/costs")
async def session_costs(session_id: str):
    df = get_session_costs(session_id)
    return {"records": df.to_dicts() if not df.is_empty() else [], "total_usd": df["cost_usd"].sum() if not df.is_empty() else 0.0}


@app.get("/costs")
async def all_costs():
    df = get_all_costs()
    return {"records": df.to_dicts() if not df.is_empty() else [], "total_usd": df["cost_usd"].sum() if not df.is_empty() else 0.0}


@app.get("/health")
async def health():
    return {"status": "ok"}
