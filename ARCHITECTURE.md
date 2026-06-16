# Meistar-KG Architecture

An agentic learning system that transforms academic papers into personalized, interactive audio learning sessions. The goal is not passive listening — it's deep expertise acquisition.

---

## Vision

You give the system a paper URL. An hour later you can discuss that paper like an expert, because you've been through a personalized Feynman-style lecture built around your existing knowledge, with the ability to pause, question, and go deeper at any moment.

---

## System Overview

```
URL → [Ingestion Agent] → Markdown
                              ↓
              ┌───────────────┴────────────────┐
              ▼                                ▼
       [KG Agent]                    [Script Writing Agent]
       Grafeo personal KG            Feynman-style lecture script
              └───────────────┬────────────────┘
                              ▼
                    [TTS Pipeline]
                    Audio chunks + PDF position markers
                              ↓
                    [Playback UI]
                    PDF viewer + audio + sync + supporting content
                              ↓
                    [Standby Q&A Agent]  ← always live during session
```

---

## Agents

### 1. Ingestion Agent

**Purpose:** Fetch a paper and produce clean, structured markdown.

**Steps:**
1. Fetch PDF from URL
2. Run OpenParse with markdownify for PDF → Markdown conversion
3. For each page/section that fails parsing quality checks, pass to vision model (Claude Vision or GPT-4V) for extraction
4. Output: structured markdown with section boundaries, figure references, table data, formula blocks

**Key decisions:**
- If paper < 150k tokens: load full content into context for downstream agents
- If paper ≥ 150k tokens: split by logical sections (abstract, introduction, methods, results, discussion, etc.) — methodology to be experimented with

---

### 2. KG Agent (runs parallel with Script Agent)

**Purpose:** Extract and integrate knowledge from the paper into the personal knowledge graph.

**Inspired by:** Karpathy's LLM-Wiki — each concept gets a structured, accumulating entry rather than a one-off extraction.

**What it extracts:**
- Core concepts and definitions
- Key claims and findings
- Relationships between concepts (builds-on, contradicts, extends, requires)
- Authors, institutions, related works
- Methods and techniques
- Open questions and limitations

**Grafeo integration:**
- Each concept node is matched against existing KG nodes (fuzzy match + embedding similarity)
- New concepts create new nodes; known concepts get the new paper's perspective merged in
- Cross-paper edges are created when this paper references, contradicts, or extends prior knowledge
- Session metadata (date, paper, confidence) attached to all new/updated nodes

**Output:** Updated Grafeo KG + a "session context" object the Script Agent and Q&A Agent can query

---

### 3. Script Writing Agent (runs parallel with KG Agent)

**Purpose:** Write a Feynman-style lecture script that teaches the paper, not just recites it.

**Style:** Feynman method — start with the simplest version of the idea, build up, use analogies, test the listener's understanding, flag when something is genuinely hard vs. just unfamiliar.

**Special handling:**
- **Tables:** Identify which cells/rows are relevant to the surrounding argument. Script narrates only those cells; UI highlights them visually.
- **Formulas:** Each variable is introduced and explained. The script describes how variables interact, not just what the formula states.
- **Citations:** Pull from KG — if the cited work is already in the personal KG, the script can say "this is the same technique used in [paper you've seen]"
- **Figures:** Script references figure number; UI surfaces the figure during playback

**Output format (per paragraph):**
```json
{
  "script_text": "...",
  "source_section": "Methods §3.2",
  "source_page": 7,
  "content_type": "explanation | table | formula | transition | summary",
  "table_highlight": {"table_id": "T2", "rows": [1, 3], "cols": [0, 2]},
  "formula_ref": "eq_3",
  "tts_ssml": "...",
  "estimated_duration_sec": 45
}
```

---

### 4. TTS Pipeline

**Purpose:** Convert the script to audio with markers that sync back to the PDF.

**Design principles:**
- Sentence/paragraph-chunked delivery — audio is generated and played chunk by chunk
- This enables clean interruption between chunks
- Provider-agnostic interface with per-call cost and token tracking

**Providers (switchable at runtime):**
| Provider | Quality | Cost | Notes |
|---|---|---|---|
| OpenAI TTS | Good | ~$15/1M chars | Word-level timestamps available |
| ElevenLabs | Excellent | ~$90/1M chars | Most natural for long-form |
| Kokoro (open source) | Good | Hosting cost only | NVIDIA / RunPod hosted |

**Output per chunk:**
```json
{
  "chunk_id": "p_042",
  "audio_url": "...",
  "duration_sec": 38,
  "word_timestamps": [...],
  "pdf_page": 7,
  "pdf_section": "Methods §3.2",
  "provider": "openai-tts",
  "cost_usd": 0.0012,
  "tokens_chars": 312
}
```

---

### 5. Standby Q&A Agent

**Purpose:** Answer questions in real time during playback with full context.

**Always has access to:**
- Full paper markdown
- Current playback position (chunk_id, pdf_page, script_paragraph)
- Personal KG session context
- Conversation history for the current session

**Handles:**
- **Connections** ("is this similar to X?") → searches KG, confirms/explains the relationship, cites the relevant prior paper if known
- **Confusion** ("I still don't understand") → rephrases using a different Feynman analogy; if still confused, goes one level more basic
- **Visual** ("draw it out") → generates a diagram (Mermaid or SVG), highlights relevant table cells, renders formula with labeled variable annotations
- **Deep dive** ("tell me more about that") → expands on the current topic using the full paper + KG

**Interruption UX:**
- Playback pauses (current chunk completes naturally or user hard-pauses)
- Agent responds with text + optional visual
- User can continue ("ok go on") or keep asking
- Session log records all interruptions and answers as annotations on the paper

---

## Data Models

### Session
```python
@dataclass
class Session:
    id: str
    paper_url: str
    paper_title: str
    paper_markdown: str          # full parsed markdown
    sections: list[Section]      # logical sections with token counts
    script: list[ScriptChunk]    # generated lecture script
    audio_chunks: list[AudioChunk]
    kg_session_context: dict     # what was added/updated in KG this session
    annotations: list[Annotation]  # Q&A interruptions, user notes
    created_at: datetime
    status: Literal["ingesting", "processing", "ready", "playing", "complete"]
```

### KG Node (Grafeo)
```
Node {
  id: uuid
  label: str                  # concept name
  type: concept | claim | method | paper | author | institution
  description: str            # Karpathy-style wiki entry, accumulates
  papers: [paper_id, ...]     # all papers that mention this node
  confidence: float
  last_updated: datetime
}

Edge {
  source: node_id
  target: node_id
  relation: builds_on | contradicts | extends | requires | introduces | uses
  paper: paper_id             # which paper created this edge
  evidence: str               # quote or paraphrase from the paper
}
```

---

## API Design (FastAPI)

```
POST /sessions              — create session from URL
GET  /sessions/{id}         — session status + metadata
GET  /sessions/{id}/script  — full script
GET  /sessions/{id}/audio/{chunk_id}  — audio stream
POST /sessions/{id}/qa      — Q&A agent call (position + question)
GET  /kg/nodes              — browse personal KG
GET  /kg/nodes/{id}         — node detail + connected edges
GET  /costs                 — per-session and cumulative cost breakdown
```

---

## Frontend (React PWA)

**Target:** iPhone and iPad (installable, mobile-optimized)

**Key views:**
1. **Library** — list of processed papers, status, KG nodes added
2. **Session** — the main learning view:
   - PDF viewer (left/top) with current position highlighted
   - Audio controls (play/pause/speed)
   - Script text scrolling in sync
   - Supporting panel: figures, tables (with highlights), formulas
   - Q&A input (always accessible)
3. **Knowledge Graph** — visual browser of Grafeo KG, filterable by topic/paper
4. **Cost Dashboard** — per-session costs, cumulative, provider breakdown

---

## Cost Transparency

Every LLM and TTS call goes through a unified gateway that records:
- Provider and model
- Input/output tokens (or characters for TTS)
- Per-call USD cost
- Session totals
- Cumulative totals

The UI always shows session cost in real time. Provider can be switched per-session or per-call-type.

---

## Repo Structure

```
Meistar-KG/
├── backend/
│   ├── agents/
│   │   ├── ingestion.py       # PDF fetch + OpenParse + vision fallback
│   │   ├── kg_agent.py        # KG extraction + Grafeo integration
│   │   ├── script_agent.py    # Feynman script writing
│   │   └── qa_agent.py        # Standby Q&A agent
│   ├── pipeline/
│   │   ├── tts.py             # TTS provider abstraction
│   │   ├── cost_tracker.py    # Per-call cost logging
│   │   └── session.py         # Session orchestration
│   ├── graph/
│   │   └── grafeo.py          # Grafeo client + KG operations
│   ├── api/
│   │   └── main.py            # FastAPI app + routes
│   └── models/
│       └── schemas.py         # Pydantic models
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── Library.jsx
│   │   │   ├── Session.jsx
│   │   │   ├── KnowledgeGraph.jsx
│   │   │   └── Costs.jsx
│   │   └── components/
│   │       ├── PDFViewer.jsx
│   │       ├── AudioPlayer.jsx
│   │       ├── QAPanel.jsx
│   │       └── SupportingContent.jsx
│   └── public/
│       └── manifest.json      # PWA manifest
├── ARCHITECTURE.md
├── CLAUDE.md
├── pyproject.toml
└── .env.example
```

---

## Open Questions / To Experiment With

1. Section splitting strategy for papers > 150k tokens
2. KG node matching threshold (embedding similarity cutoff for merging vs. creating new nodes)
3. Optimal chunk size for script/TTS (sentence vs. paragraph vs. topic boundary)
4. Visual generation approach for "draw it out" (Mermaid diagrams? SVG? Canvas?)
5. Grafeo API capabilities and schema constraints
