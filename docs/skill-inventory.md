# Hajimi Skill Inventory

盘点范围是本机发现到的 Hajimi 项目 skills、其 6 个共享核心 skills，以及 Codex/Claude/Gemini/Agy 的实际消费入口。其它项目和系统 skills 保留原状。绝对安装路径不进入配置；机器本地根为 `~/.agents/skills`，仅 `.local/skill-lock.json` 记录解析后的实际路径。

## Before cleanup

- Project `.agents/skills` had 24 folders: 23 Hajimi roles/adapters plus a byte-identical vendor copy of official `h3-prompt-writing` already present in the shared store. The project copy is removed; the official version remains shared and pinned.
- Shared Hajimi skills had copied installs under Codex shared and Claude roots; Codex `~/.codex/skills` was an alias to `~/.codex-shared/skills`. Gemini initially lacked five of the six routed shared skills and had nine broken links. The local orchestrator source had no verifiable repository/commit.
- Every scoped skill and symlink target was inspected before changes. Unrelated skills remain untouched. A Gemini runtime listing still reports conflicts for unrelated global skills; those names are outside Hajimi production routing and were preserved.

## Final canonical inventory

Hashes use `studio.skills.skill_tree_hash`: relative file path plus file SHA-256, excluding `.git`, `__pycache__`, and `.pyc`. Global version pins are upstream commits; the local orchestrator is pinned by its content hash. Detailed machine-readable fields live in `config/skill-sources.yaml`.

### Shared skills

| Skill | Path | Consumer | Scope / source | Upstream | Version | Content SHA-256 | Symlink target | Role | Status |
|---|---|---|---|---|---|---|---|---|---|
| creative-video-orchestrator | ~/.agents/skills/creative-video-orchestrator | codex,claude,gemini | global / local | — | local:db1004841d84 | db1004841d84bc08d28d6ecc0cba4f3f2c284fd149a06ea159055beff650cd23 | codex: ~/.agents/skills/creative-video-orchestrator; claude: ~/.agents/skills/creative-video-orchestrator; gemini: direct canonical | Top-level stage router, artifact dependency checker, gate owner; not a creative specialist. | keep |
| gpt-image-2-style-library | ~/.agents/skills/gpt-image-2-style-library | codex,claude,gemini | global / upstream_git | https://github.com/freestylefly/awesome-gpt-image-2.git / `agents/skills/gpt-image-2-style-library` @ `0dc09c46c8a3` | 0dc09c46c8a30b1fdd89c18cc78a894dac2104e3 | c79bcaf88db4b290e1299120fd98657b3cb0fa885bc1143a446c041a6adb103a | codex: ~/.agents/skills/gpt-image-2-style-library; claude: ~/.agents/skills/gpt-image-2-style-library; gemini: direct canonical | Upstream GPT Image style/template expertise; translates approved visual intent into image prompt guidance. | keep |
| short-form-video-script | ~/.agents/skills/short-form-video-script | codex,claude,gemini | global / upstream_git | https://github.com/social-media-skills/skills.git / `skills/short-form-video-script` @ `6e30eeb2f673` | 6e30eeb2f6736bda8683b6bbaa674af3641d7945 | 5cb3f68c3b71799307d7f9d4b934b894f87bb81a5f9f2a5986a93008f5d1be0d | codex: ~/.agents/skills/short-form-video-script; claude: ~/.agents/skills/short-form-video-script; gemini: direct canonical | Upstream retention craft: hooks, open loops, mute-first, payoff, loop, cadence. | keep |
| short-drama-agent | ~/.agents/skills/short-drama-agent | codex,claude,gemini | global / upstream_git | https://github.com/MrMO0802/short-drama-agent.git / `.` @ `ac4a4a92d282` | ac4a4a92d282d3d10fd30d4eb7e0d95359a193f2 | 681e0539a3d57a7e25ea08f0bbdd58513091299cb63ad0fec4705ed4b98f3113 | codex: ~/.agents/skills/short-drama-agent; claude: ~/.agents/skills/short-drama-agent; gemini: direct canonical | Upstream continuity and cinematography methods only; no provider workflow or script ownership. | keep |
| h3-prompt-writing | ~/.agents/skills/h3-prompt-writing | codex,claude,gemini | global / upstream_git | https://github.com/MiniMax-AI/MiniMax-H3.git / `skills/h3-prompt-writing` @ `d21241f0a4b3` | d21241f0a4b3acbb34c97dae47fa417b7065e438 | 754befbf09558ac93d44e57f7a3af3cbd89dfb03f25b06ee8be731f05f5640e6 | codex: ~/.agents/skills/h3-prompt-writing; claude: ~/.agents/skills/h3-prompt-writing; gemini: direct canonical | Official MiniMax H3 mode-specific prompt structure and image alignment rules. | keep |
| video-editing | ~/.agents/skills/video-editing | codex,claude,gemini | global / upstream_git | https://github.com/maxazure/video-editing-skill.git / `.` @ `52ec46319ebe` | 52ec46319ebe916bc4e4ad31aa48f7254201ef85 | c734803583ab9dfdf1adee3df5f87f5fe43b69902c87b19d1d31e81b2dc83f0d | codex: ~/.agents/skills/video-editing; claude: ~/.agents/skills/video-editing; gemini: direct canonical | Upstream general post-production craft; only operations supported by Hajimi roughcut are routed. | keep |

### Project skills and adapters

| Skill | Path | Consumer | Scope / source | Version | Content SHA-256 | Role | Status |
|---|---|---|---|---|---|---|---|
| ai-visual-producer | .agents/skills/ai-visual-producer | codex,claude,gemini | project / project_adapter | local | e68544127e3dcbf46c8f2adf8586b18d63edbea3ab5b326df1920a5980fda58b | Adapt approved Hajimi shot direction and GPT Image skill recommendations into traceable local image prompt and candidate artifacts. | keep |
| analytics-reviewer | .agents/skills/analytics-reviewer | codex,claude,gemini | project / local | local | 47a3ea98b25acda530ee470b51564d111ae5a1f5f64633d3096a976fc47d6a0c | Turn retention and production metrics into reusable learning records. | keep |
| animatic-director | .agents/skills/animatic-director | codex,claude,gemini | project / local | local | c6d0574cfabbfa6c3c4c6524d24e8d80892c2d34db4447e8693670110b083592 | Build and judge the low-cost storyboard animatic before production spend. | keep |
| autodl-h3-worker | .agents/skills/autodl-h3-worker | codex,claude,gemini | project / local | local | 7e7520922bd02faa70ea39a631e427573951eefd85e0c9e7846df0e170893682 | Operate Hajimi's AutoDL ComfyUI MiniMax H3 render worker, including instance inventory, SSH transfer, runtime checks, scoped cleanup, and smoke tests. Use for Hajimi AutoDL/H3 work, not unrelated cloud administration or creative production. | keep |
| beads | .agents/skills/beads | codex,claude,gemini | project / local | local | 68815804c310f62c5b49750e1a39128a04185f4b08234a0bdfcb3fa57df27eb8 | Track durable Hajimi work, blockers, dependencies, and handoffs with bd. | keep |
| creative-director | .agents/skills/creative-director | codex,claude,gemini | project / local | local | 4fecc8322bd184fa73b7a54b1ad64467cc984ac6a8e2228ddc8ce32b4a254d5a | Define the emotional curve, stop-scroll hook, hero shot, and cost-worthy visual thesis. | keep |
| fast-media-qc | .agents/skills/fast-media-qc | codex,claude,gemini | project / local | local | a0c02904ac2bbac674702dc3ad4bbbf6b92764c0349b355298e34d16497bbb2c | Run the cached five-tier media QC funnel without flooding agent context. | keep |
| ffmpeg-rough-editor | .agents/skills/ffmpeg-rough-editor | codex,claude,gemini | project / project_adapter | local | c05a6d2d34cf4ce4e983b7ebec0fb2f2879345cd55c52b8c552e738d7ffac66c | Route Hajimi episode artifacts through the local FFmpeg roughcut contract and verify its output. | keep |
| final-master-qc | .agents/skills/final-master-qc | codex,claude,gemini | project / local | local | b9b8aaf2179eab4eacdfa1cb656f21c92fdaac4b6658bcde46486d60f3788288 | Perform deterministic, visual-sample, subtitle, ASR, audio, and integrity checks on a master. | keep |
| generation-director | .agents/skills/generation-director | codex,claude,gemini | project / local | local | ec57f0d78baae4ff92c1e77467669a17769572dd921b4ac8b0bf675dc17fa984 | Route approved Hajimi shots to image, H3, Fusion, footage, or hybrid production and set bounded candidate budgets. | keep |
| h3-video-director | .agents/skills/h3-video-director | codex,claude,gemini | project / project_adapter | local | f9a13c56c124a62a80b50f5d06b9efbcc746da7a55dac4416d4e5a939e2d5d6a | Prepare, submit, inspect, and hand off locally directed ComfyUI MiniMax H3 jobs. | keep |
| idea-discovery | .agents/skills/idea-discovery | codex,claude,gemini | project / local | local | e364dcd6b93689461648884c3e07dc4ea76c10d49d1b1965033819322804f7dd | Find high-visual, high-retention knowledge story candidates instead of random topic lists. | keep |
| idea-tournament | .agents/skills/idea-tournament | codex,claude,gemini | project / local | local | 98eac08b9eb2fab87c47fb67a6ab13a746b033b6dff3b7a05f6141e51f760cf0 | Compare story candidates through pairwise reasoning and compose stronger hybrid angles. | keep |
| reference-deconstructor | .agents/skills/reference-deconstructor | codex,claude,gemini | project / local | local | f2bcf0f4bdb4290a3df7ea3dc10abfc13d7259bd6a34f86180b2c2a9057de7a5 | Deconstruct high-performing references into reusable shot and sound grammar. | keep |
| research-editor | .agents/skills/research-editor | codex,claude,gemini | project / local | local | 4858776e3b95b151ffa9776a79a4a7f17227fba5c914feb1a8addd74ac5596c9 | Verify facts, separate fact from inference, and maintain source-backed claim maps. | keep |
| resolve-editor | .agents/skills/resolve-editor | codex,claude,gemini | project / local | local | 82b62ce62cb57c6168412dcc6d645f8b42c5972af9f75d5bd95fceb2575fa1cc | Apply optional DaVinci Resolve premium finishing to an existing Hajimi roughcut when the episode needs advanced picture or Fusion work. | keep |
| short-script-editor | .agents/skills/short-script-editor | codex,claude,gemini | project / project_adapter | local | 7cecdddc1115e7b3941df983a9c489062fa6a71b36c3d8cfd2c53f92d1db6eb4 | Convert upstream short-form script craft and Hajimi direction into a validated beat-script-v2 artifact with hook and mute-read decisions. | keep |
| shot-designer | .agents/skills/shot-designer | codex,claude,gemini | project / project_adapter | local | 1ebf19d7287c52447ccc77b46594fdbeddb3cf46b28432e418205407cf717b31 | Author Hajimi Shot Contracts with continuity state and one visible action per shot. | keep |
| sound-designer | .agents/skills/sound-designer | codex,claude,gemini | project / local | local | 597a0e77fcab9a71b77cb6acebd1ef8d58a8dd81ce84cdcbc058162e73c65098 | Turn Hajimi beats and approved picture into sound intent and executable episode cue artifacts. | keep |
| storyboard-director | .agents/skills/storyboard-director | codex,claude,gemini | project / local | local | 59314b77ac55c162b37aa1d7b37d8a9a126112a5b3e783938c2543791d3e8a61 | Turn approved Hajimi beats into an ordered shot board with composition and timing notes. | keep |
| visual-concept-director | .agents/skills/visual-concept-director | codex,claude,gemini | project / local | local | 098fca39ebf47dbf5d778a49554a5cc3add37d2ea4a895d2f74a0a71f00e6593 | Decide what the audience should see before prompts or media generation. | keep |
| voice-director | .agents/skills/voice-director | codex,claude,gemini | project / local | local | 40d4f667888c47e5ce6e94bbebec04bfbe88e8b29a66df48c341b47f0c71411f | Direct narrator performance and candidate selection for local VoxCPM2 production voice. | keep |
| youtube-publisher | .agents/skills/youtube-publisher | codex,claude,gemini | project / local | local | 4df263962ab68dced0b5f53e25d8c90d30123ab51d5f9ada41a597bb60e83152 | Safely prepare and execute YouTube Studio uploads through ego-browser with readback. | keep |

## Runtime resolution

- **Codex**: `~/.codex/skills` resolves through the existing root symlink to `~/.codex-shared/skills`; all six shared Hajimi skills are individual symlinks to `~/.agents/skills/<name>`. `codex debug prompt-input` showed the canonical orchestrator and project adapter entries; a read-only `$creative-video-orchestrator` run loaded and read the skill.
- **Claude**: the six entries under `~/.claude/skills` are symlinks to the canonical store. `claude doctor` passes, but the CLI could not complete a skill-invocation session because of its current account-access state; runtime invocation remains unverified.
- **Gemini CLI**: `gemini skills list` found the six canonical shared skills directly under `~/.agents/skills` and the Hajimi project skills. Redundant copies in `~/.gemini/skills` were removed because they caused conflict warnings. The model call failed with Google license error `#3501`; discovery listing passed.
- **Agy**: explicit `/creative-video-orchestrator` invocation returned the manifest source of truth, `ai-visual-producer`, and Codex `image_gen`; invocation passed. An initial `$skill` form did not invoke correctly; use the slash form for this runtime.
- Gemini reported other conflicts for unrelated skills (including accessibility, agent-reach, archify, book-to-skill, documentation, ego-browser, performance, playwright, python-power, review-local-changes, shadcn, systematic-debugging, UI/UX, Vue, and xiangsu). These are not used by Hajimi routing and were left untouched.

## Deletions and cleanup

- Removed project duplicate `.agents/skills/h3-prompt-writing`; official upstream copy is pinned in the canonical shared store.
- Removed nine confirmed broken Gemini links: `ai-film-director`, `ai-film-editor`, `amv-color-audio`, `amv-editing`, `amv-fusion-fx`, `amv-quality-control`, `amv-reference-analysis`, `resolve-amv-orchestrator`, and `resolve-runtime`.
- Replaced copied Codex/Claude shared skill folders with symlinks; removed six redundant Gemini aliases to prevent the CLI from seeing each canonical skill twice. No managed empty skill folders remain.
- Replaced the untraceable orchestrator’s parallel `.creative-video/run.json` workflow with the Hajimi manifest and removed its unused generic job-state script and conflicting provider/pipeline references.

## Upstream synchronization

`uv run hajimi skills updates` only checks pinned commits. `uv run hajimi skills sync --skill <name>` fetches the exact registered commit into a staging directory, verifies `SKILL.md` and the recursive content hash, refuses if the installed copy differs from the recorded lock, then atomically swaps the result. Updating to newer upstream requires a reviewed commit/hash change in `config/skill-sources.yaml`; no automatic upgrade occurs. Local overlays belong in Hajimi adapters, not upstream copies.
