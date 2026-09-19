---
name: generation-director
description: Route shots across Codex image_gen, Google Flow, Fusion, footage, and hybrid production.
triggers: generation plan, shot routing, candidate competition, regeneration strategy
---

# Objective

Choose the thinnest real route that protects story, continuity, and information
payload, then concentrate candidate budget on shots worth iterating.

# Current responsibilities

Codex image_gen handles concepts, references, keyframes, and variations.
Google Flow via `ego-browser` handles I2V, native T2V, multi-keyframe, variation,
extension, and repair. Fusion owns exact numbers, labels, arrows, vectors,
masks, and tracked graphics. Resolve owns the final edit, color, Fairlight,
and delivery. `hybrid_ai` combines those responsibilities.

# Routing questions

- Does this shot need a generated keyframe first?
- Is I2V better than text-to-video?
- Does it need multiple state keyframes?
- What exact information must be deferred to Fusion?
- Which continuity references must be passed to Flow?

Generate exactly one image candidate per shot in the first pass, regardless of
shot tier. After director inspection, request only a targeted variation when
the selected frame misses a contract requirement. Choose Flow motion candidates
incrementally after inspecting the keyframe; never launch a mechanical batch.
Use trim, retime, mask, cleanup, or extension before full regeneration. Never
approve a Flow candidate without a local downloaded file and provenance sidecar.
