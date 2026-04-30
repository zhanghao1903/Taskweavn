# codeAgent

A code agent with strongly-typed Action/Observation, EventStream-driven ReAct loop,
and pluggable Runtime — built on top of the OpenHands SDK for LLM adaptation.

## Status

Phase 1 (foundation): scaffolding in progress. See [`docs/`](docs/) for the
architecture plan.

## Quick start

```bash
uv sync
export LLM_API_KEY=...   # Anthropic API key
uv run code-agent --help
```

## Layout

```
src/code_agent/
├── types/          # Action / Observation base classes + registry
├── core/           # EventStream + ReAct main loop
├── memory/         # ThoughtStore (rooted out of EventStream)
├── llm/            # LLMClient (wraps openhands-sdk LLM)
├── runtime/        # Runtime Protocol + local-process implementation
├── tools/          # File / shell tools
├── orchestration/  # Multi-agent interface (placeholder)
└── cli/            # Typer entry point
```
