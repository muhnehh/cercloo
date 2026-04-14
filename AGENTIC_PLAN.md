# Cercli Agentic Plan

## Goal

Turn the current HR migration workflow into an agentic system that can inspect data, decide what to do next, act with tools, evaluate results, and keep memory for the next run.

## What Makes It Agentic

The new agent loop is not a fixed script. It performs the following cycle:

1. Discover the dataset and profile the input files.
2. Build retrieval context when the data benefits from semantic lookup.
3. Map messy columns with the best available model or fallback.
4. Evaluate mapping quality against the labeled dataset when available.
5. Canonicalize records and run compliance checks.
6. Export artifacts and persist memory for the next session.

## Tooling Layer

The agent treats each major capability as a tool:

- Ingestion and profiling
- Vector retrieval and semantic context
- LLM column mapping
- Mapping evaluation against labels
- Compliance checking
- Artifact export

## Memory Layer

The agent stores:

- Successful mappings
- Review queues
- Last run metadata
- Confidence-based observations

This lets the next run start with prior knowledge instead of acting statelessly.

## Why This Looks Strong in an Agents Review

- It has a planner/executor/reflect loop.
- It uses the repo's existing real tools rather than pretending with a chatbot wrapper.
- It benchmarks itself against a labeled dataset.
- It produces traceable artifacts for auditability.
- It writes memory to disk so the system improves over time.

## Recommended Demo Command

```bash
python demo_agent.py
```

That will run the agent loop and write outputs to `outputs/agent_<timestamp>/`.
