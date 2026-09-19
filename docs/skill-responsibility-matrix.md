# Hajimi Skill Responsibility Matrix

| Skill | Knowledge owner | Project role | Input | Output | Next | Keep/Delete |
|---|---|---|---|---|---|---|
| creative-video-orchestrator | Local, untraceable | Stage selection, artifact dependency, gate/recovery routing | Episode manifest, registered artifacts/gates | Select next specialist and verify handoff | Stage specialist | Keep |
| idea-discovery | Hajimi project skill | Find high-visual story/topic candidates | Channel, audience, topic constraints | Idea candidates and evidence trail | idea-tournament | Keep |
| idea-tournament | Hajimi project skill | Compare candidate angles and select a winner | Idea candidates, viewer promise | Angle tournament and chosen direction | creative-director | Keep |
| research-editor | Hajimi project skill | Verify claims and maintain source-backed fact map | Selected topic and claims | Fact pack and claim references | reference-deconstructor / creative-director | Keep |
| reference-deconstructor | Hajimi project skill | Extract reusable reference grammar | Verified facts and reference assets | Reference analysis artifact | creative-director | Keep |
| creative-director | Hajimi project skill | Own audience promise, emotional curve, hook choice, hero shot | Research and angle tournament | Creative direction artifact | short-form-video-script | Keep |
| short-form-video-script | Upstream retention craft | Hooks, mute-first, open loops, payoff, loop and cadence | Fact pack, brief, selected direction | Script craft result and distinct hook concepts | short-script-editor | Keep |
| short-script-editor | Hajimi adapter | Map upstream craft into beat-script-v2 and validate gates | Research/brief, craft result, episode timing | hook_competition.yaml, mute_read.yaml, beat_script.yaml | visual-concept-director / voice-director | Keep |
| visual-concept-director | Hajimi project skill | Define visual thesis, motif, scale, light and escalation | Locked beat script and creative direction | Visual concept artifact | storyboard-director | Keep |
| storyboard-director | Hajimi project skill | Decompose beats into ordered shot cards and composition | Beat script and visual concept | Storyboard and connection notes | shot-designer | Keep |
| short-drama-agent | Upstream continuity/cinematography methods | Provide continuity, causality, screen direction and start/end state methods | Storyboard and shot sequence | Method guidance recorded in continuity review/contracts | shot-designer | Keep |
| shot-designer | Hajimi contract adapter | Author Shot Contract, state handoff and one visible action | Storyboard, continuity and visual direction | shots/Sxxx/shot.yaml; continuity_receive/handoff | generation-director | Keep |
| animatic-director | Hajimi project skill | Build low-cost animatic and enforce production gate | Storyboard and shot contracts | animatic plus machine-readable gate | generation-director | Keep |
| generation-director | Hajimi project skill | Choose supported image/H3/Fusion/footage route and duration/budget | Approved animatic, Shot Contract, capability limits | Per-shot generation plan | ai-visual-producer / h3-video-director | Keep |
| gpt-image-2-style-library | Upstream image style expertise | Select matching style/template and provide prompt guidance | Shot Contract, visual concept, references | Style/template decision | ai-visual-producer | Keep |
| ai-visual-producer | Hajimi image adapter | Compose agent prompt, record provenance, coordinate candidate review | Shot Contract plus upstream style decision | prompt.md/json, image job/candidates/provenance | Codex image_gen → local selection | Keep |
| h3-prompt-writing | Official MiniMax upstream | Write official mode structure and image alignment | Shot Contract, motion, images, continuity, audio intent, generation duration | shots/Sxxx/h3/prompt.txt/json | h3-video-director | Keep |
| h3-video-director | Hajimi H3 adapter | Validate/package/submit/pull/inspect/select H3 results | Approved keyframes and final H3 prompt artifact | Remote job/results and local candidate handoff | AutoDL worker then Fast QC | Keep |
| autodl-h3-worker | Hajimi infrastructure skill | Operate SSH-only remote H3 render infrastructure | Validated remote job package | Rendered/probed result for verified pull | h3-video-director | Keep |
| voice-director | Hajimi project skill | Plan narrator performance and select local voice takes | Locked beat narration and voice policy | VoxCPM2 voice plan/approved narration | sound-designer | Keep |
| sound-designer | Hajimi project skill | Design narration/ambience/music/SFX cue intent | Beats, approved picture, H3 native ambience, VoxCPM2 | Sound plan and supported roughcut cues | ffmpeg-rough-editor | Keep |
| video-editing | Upstream editing expertise | Supply only relevant clip/audio/render/QA craft | Approved clips, timeline, voice, native ambience, optional music/SFX/subtitles | Guidance constrained to Hajimi roughcut schema | ffmpeg-rough-editor | Keep |
| ffmpeg-rough-editor | Hajimi thin edit adapter | Map episode artifacts to FFmpeg roughcut and verify output | Manifest timeline and selected approved assets | Roughcut master and roughcut_manifest.json | final-master-qc | Keep |
| fast-media-qc | Hajimi project skill | Run deterministic/cached candidate and shot QC | Selected image/video candidates and provenance | Shot QC report and review decision | shot approval / roughcut | Keep |
| resolve-editor | Hajimi optional finish skill | Apply advanced Resolve/Fusion/color/Fairlight after FFmpeg roughcut | Optional premium-finishing request and roughcut | Render plus Resolve readback if used | final-master-qc | Keep |
| final-master-qc | Hajimi project skill | Validate exact active master and human playback/hash evidence | FFmpeg or Resolve master, provenance, audio/subtitles/shot QC | PASS/FAIL report bound to active hash | youtube-publisher | Keep |
| youtube-publisher | Hajimi delivery skill | Run local publish preflight and YouTube Studio workflow | Master-specific gates, QC, review, valid metadata | Private upload/readback/checks | analytics-reviewer | Keep |
| analytics-reviewer | Hajimi project skill | Turn published performance into learning records | YouTube analytics and episode context | Analytics record and next-cycle learning | idea-discovery | Keep |
| beads | Hajimi project skill | Track durable blockers and handoffs | Task/production state | Issue state and next action | orchestrator | Keep |

## Ownership boundaries

- `creative-video-orchestrator` routes and gates; `creative-director` decides what creative direction is strongest.
- `short-form-video-script` owns general retention craft; `short-script-editor` owns the Hajimi schema and gate records.
- `gpt-image-2-style-library` owns general GPT Image style knowledge; `ai-visual-producer` adapts an approved shot into Hajimi prompt/job/provenance artifacts; `studio/generation/image.py` packages and validates; Codex `image_gen` executes.
- `short-drama-agent` supplies continuity/cinematography methods; `storyboard-director` owns board order; `shot-designer` owns Shot Contract; `generation-director` owns production route.
- `h3-prompt-writing` owns H3 prompt syntax; `generation-director` chooses method/duration; `h3-video-director` owns job operations; Python validates/packages; AutoDL executes unchanged prompt.
- `video-editing` owns general post-production guidance; `ffmpeg-rough-editor` owns Hajimi mapping; `studio.roughcut` executes FFmpeg; Resolve is an optional premium finish.
- Upstream skills are not copied into project `.agents/skills`; project adapters contain Hajimi contracts only.
