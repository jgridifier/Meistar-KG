# Meistar-KG — Claude Code Context

## What this project is

An agentic learning system that transforms academic papers into personalized, interactive audio learning sessions. Users give a paper URL; the system builds a Feynman-style lecture script using a personal knowledge graph, generates audio, and provides a real-time Q&A agent during playback.

See ARCHITECTURE.md for full system design.

## Stack

- **Backend:** Python 3.11+ with FastAPI, Polars (not pandas)
- **PDF parsing:** OpenParse + markdownify, vision model fallback
- **LLM routing:** OpenRouter, NVIDIA hosted models, OpenAI API
- **TTS:** Provider-agnostic abstraction (OpenAI TTS / ElevenLabs / Kokoro)
- **Graph:** Grafeo
- **Frontend:** React PWA (mobile-optimized for iPhone/iPad)

## Key conventions

- Use Polars, not pandas, for all dataframe operations
- All LLM and TTS calls go through the cost tracking gateway in `backend/pipeline/cost_tracker.py`
- Agents are custom ReAct agents (not LangChain unless there's a compelling reason)
- KG agent and script writing agent run in parallel (asyncio)
- Pydantic models for all API schemas
- Type hints everywhere

## Environment

Copy `.env.example` to `.env` and fill in keys. Never commit `.env`.

## Running locally

```bash
# Backend
cd backend
pip install -e ".[dev]"
uvicorn api.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Testing

```bash
pytest backend/tests/
```
