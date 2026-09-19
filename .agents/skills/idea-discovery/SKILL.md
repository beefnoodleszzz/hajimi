---
name: idea-discovery
description: Find high-visual, high-retention knowledge story candidates instead of random topic lists.
---

# Objective

Discover topics that are interesting, immediately visualizable, escalatable,
and realistically generatable for `The World You Never Knew` from the supplied
topic, research, references, channel history, capabilities, and constraints.

This is a live agent stage. Never read a fixed winner or copy a previous
episode's answer. Explore mutually different angles before narrowing.

# Required Input

The runtime context must include `topic`, `channel`, `format`, `duration`,
`research`, `references`, `history`, `production_capabilities`, and
`constraints`. Missing context is a research/briefing problem, not a reason to
invent an episode-specific seed in Python.

# Required Output

Emit `schema_version: idea-analysis-v2` and `candidates`. For every candidate
record premise, viewer question, surprising fact, emotional driver,
first-second event, visual escalation, hero frame, ending loop, production fit,
novelty, risk, and evidence direction. Produce 15–30 initial candidates when
the input supports it, then mark clustering/deduplication/rejection evidence;
do not declare a winner here.

# Quality Gate

Prefer anomalies that read without subtitles in the first second. Lower topics
that need narration before anything can be seen. Produce a discovery set for
tournament review; do not declare a winner here.

# Forbidden Patterns

Do not output a random list, copy a proven topic verbatim, present an
unsupported claim as fact, or rely on a Python-registered discovery seed.
