# Orchestration Evidence

`.amv/project-state.json` follows the Resolve orchestrator state contract. It
records mode, phase, accepted render, hashes, findings, skipped gates, and one
next action. `analysis/`, `previews/`, and `comparisons/` are reserved for
compact evidence, never full-frame agent dumps.
