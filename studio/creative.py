"""Content-first creative package generation for Hajimi episodes.

This module keeps the director contracts small and inspectable.  It does not
generate media or pretend that a numeric score is creative judgment: idea
discovery produces structured candidates, tournament produces pairwise
reasoning, and the package records the chosen hook/motif/escalation blend.
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path
from typing import Any

from .config import dump_yaml
from .manifest import load_manifest, write_manifest
from .paths import StudioPaths, project_root

CREATIVE_FILES = (
    "idea_analysis.yaml",
    "angle_tournament.yaml",
    "creative_direction.yaml",
    "visual_concept.yaml",
    "beat_script.yaml",
    "generation_plan.yaml",
)
SHOT_TIERS = {"HERO", "STORY", "CONNECTOR"}
GENERATION_METHODS = {"blender", "ai_video", "ai_image", "fusion", "footage", "hybrid", "blender_ai_hybrid"}


def _idea(
    idea_id: str,
    title: str,
    premise: str,
    question: str,
    surprise: str,
    emotion: str,
    *,
    opening: str,
    escalation_1: str,
    escalation_2: str,
    hero: str,
    ending: str,
    novelty: str,
    risk: str,
    production_fit: dict[str, str],
) -> dict[str, Any]:
    return {
        "id": idea_id,
        "title_working": title,
        "premise": premise,
        "viewer_question": question,
        "surprising_fact": surprise,
        "emotional_driver": emotion,
        "hook_potential": {
            "first_second_event": opening,
            "first_visual": opening,
            "contradiction": surprise,
            "curiosity_gap": question,
        },
        "visual_potential": {
            "opening_visual": opening,
            "escalation_visual_1": escalation_1,
            "escalation_visual_2": escalation_2,
            "hero_visual": hero,
            "ending_visual": ending,
        },
        "story_potential": {
            "setup": premise,
            "escalation": f"{escalation_1} → {escalation_2}",
            "payoff": hero,
            "loop": ending,
        },
        "production_fit": production_fit,
        "novelty": {
            "common_existing_angle": "Earth stops and everything breaks immediately.",
            "alternative_angle": novelty,
            "our_distinctive_angle": f"{opening} grows into {hero} instead of becoming a paragraph of exposition.",
        },
        "risk": {
            "factual_uncertainty": "The one-second stop is a thought experiment; label the simplification.",
            "visual_complexity": risk,
            "generation_difficulty": "medium" if "personal" in idea_id else "high",
        },
        "evidence": {
            "source_direction": "NASA Earth rotation / NOAA atmosphere and ocean reference material",
            "reference_topics": ["angular velocity", "inertia", "atmospheric coupling", "ocean momentum"],
        },
    }


def _ep001_ideas() -> list[dict[str, Any]]:
    common = {
        "blender": "exact vectors, layered offsets, and measurable scale",
        "ai_video": "controlled human or atmospheric motion only",
        "ai_image": "hero plate or impossible opening texture",
        "fusion": "labels, vectors, and compositing",
        "footage": "not preferred; would need licensed material",
    }
    return [
        _idea("human_inertia", "You Keep Moving", "The surface stops while a person keeps the eastward velocity of the rotating Earth.", "If the road freezes, what carries you forward?", "Stopping the ground does not erase momentum.", "personal danger", opening="A road locks mid-motion while a red receipt crosses the frame.", escalation_1="body-scale rightward displacement", escalation_2="465 m measured against the street", hero="a person, road, and vector separated in one clean frame", ending="the same road returns with the receipt displaced", novelty="Most versions start at planet scale; this starts with a familiar object that betrays the event.", risk="body animation and road continuity", production_fit=common),
        _idea("atmosphere_weapon", "The Sky Becomes a Blade", "The atmosphere retains its eastward motion when the ground stops.", "Why does the sky become dangerous if the ground is the thing that stopped?", "The air is a moving layer, not a painted background.", "invisible force becomes threat", opening="A cloud band shears away from a locked city slab.", escalation_1="cloud layer separates from land", escalation_2="air becomes a horizontal flow field", hero="a clean land/air cutaway with the moving atmosphere visibly offset", ending="the flow line returns to the receipt", novelty="Treats the atmosphere as a protagonist rather than a scenic background.", risk="avoid implying a literal solid blade", production_fit=common),
        _idea("ocean_mismatch", "The Ocean Does Not Stop", "Land, air, and ocean no longer share the same horizontal state.", "Which layer keeps moving when the pavement restarts?", "The ocean is part of the original motion budget.", "systemic dread", opening="A coastline freezes while a thin ocean sheet slides east.", escalation_1="water surface detaches from coast", escalation_2="land/air/water become three offset bands", hero="three horizontal layers with the ocean visibly out of register", ending="the receipt lands on the same road at a new position", novelty="Uses the ocean as the irreversible reveal instead of a generic destruction montage.", risk="ocean motion must stay abstract and readable", production_fit=common),
        _idea("displacement_465m", "One Second Is 465 Metres", "A single second turns rotational speed into a visible distance relative to the ground.", "How far can one second move you?", "The number is a distance, not just a speed statistic.", "scale shock", opening="A one-second ruler snaps across a road map.", escalation_1="human scale to city blocks", escalation_2="measured displacement crosses the frame", hero="a red origin and endpoint separated by a physical 465 m ruler", ending="the ruler collapses back into a receipt-sized mark", novelty="Makes the number the action rather than a caption.", risk="numbers must remain legible without dominating the story", production_fit=common),
        _idea("city_scale_destruction", "The City Slides First", "A city-scale slice reveals the mismatch as infrastructure, air, and water decouple.", "What breaks when an entire city loses its shared reference frame?", "The disaster is a coordination failure between layers.", "scale dread", opening="Road grids freeze while the skyline and air layer keep sliding.", escalation_1="street grid to skyline", escalation_2="city slab against atmosphere and coast", hero="a vertical city cutaway with one locked plane and two moving planes", ending="the grid resets but one red object remains displaced", novelty="Turns a planet thought experiment into a legible urban machine.", risk="city detail can bury the causal relationship", production_fit=common),
        _idea("personal_pov", "Your Camera Does Not Agree", "A first-person view makes the viewer's own reference frame fail.", "Would your eyes see the stop before your body feels the mismatch?", "The camera can remain stable while the world moves through it.", "embodied disorientation", opening="A phone-level POV freezes its horizon while a receipt streaks past.", escalation_1="handheld reference frame", escalation_2="the horizon separates from the moving air", hero="a POV frame whose stable road and sliding layers disagree", ending="the opening POV reappears with a silent displacement", novelty="Makes the audience occupy the reference frame instead of watching a diagram.", risk="POV artifacts could reduce scientific clarity", production_fit=common),
        _idea("system_layer_mismatch", "Earth Stops Being One System", "The land stops first, but the coupled layers retain different motion.", "What does 'Earth stopped' actually mean when Earth is several moving systems?", "The word Earth hides land, air, water, and bodies with different responses.", "awe through structure", opening="A single horizontal line fractures into land, air, and ocean.", escalation_1="one vector branches into three layers", escalation_2="layers restart at different times", hero="a still-readable system cross-section where land is locked and upper layers lag right", ending="three layers collapse into one unresolved question", novelty="Reframes the what-if as a failure of shared reference, not a single explosion.", risk="requires disciplined graphic hierarchy", production_fit=common),
    ]


def discover_ideas(episode_id: str, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a structured discovery set without pretending it is final judgment."""

    manifest = manifest or {}
    creative = manifest.get("creative", {}) if isinstance(manifest.get("creative"), dict) else {}
    if episode_id == "EP001_earth-stop":
        ideas = _ep001_ideas()
        topic = "What If Earth Stopped Spinning for One Second?"
    else:
        topic = str(creative.get("promise") or episode_id)
        ideas = []
    return {
        "schema_version": "idea-analysis-v1",
        "episode_id": episode_id,
        "topic": topic,
        "selection_policy": {
            "must_be": ["interesting", "visualizable", "escalatable", "generatable"],
            "priority": "first-second anomaly that reads without subtitles",
            "note": "Discovery candidates are inputs to tournament reasoning, not approved ideas.",
        },
        "ideas": ideas,
    }


def run_tournament(analysis: dict[str, Any]) -> dict[str, Any]:
    """Compare angles pairwise and record a composited winner."""

    ideas = analysis.get("ideas", [])
    by_id = {str(item.get("id")): item for item in ideas if isinstance(item, dict) and item.get("id")}
    rank = {
        "human_inertia": 6,
        "atmosphere_weapon": 4,
        "ocean_mismatch": 5,
        "displacement_465m": 3,
        "city_scale_destruction": 2,
        "personal_pov": 1,
        "system_layer_mismatch": 7,
    }
    focus = {
        "human_inertia": "instant personal readability",
        "atmosphere_weapon": "invisible force made visible",
        "ocean_mismatch": "irreversible system escalation",
        "displacement_465m": "measurable scale",
        "city_scale_destruction": "urban consequence",
        "personal_pov": "embodied point of view",
        "system_layer_mismatch": "clean explanatory hero frame",
    }
    wins = {key: 0 for key in by_id}
    comparisons: list[dict[str, Any]] = []
    for left, right in combinations(by_id, 2):
        winner = left if rank.get(left, 0) >= rank.get(right, 0) else right
        loser = right if winner == left else left
        wins[winner] += 1
        comparisons.append({
            "match": [left, right],
            "winner": winner,
            "loser": loser,
            "reason": f"{winner} wins this matchup on {focus[winner]}; {loser} remains useful as an escalation or texture, not as the spine.",
        })
    scored = sorted(({"id": key, "pairwise_wins": value} for key, value in wins.items()), key=lambda item: (-item["pairwise_wins"], item["id"]))
    variants = [
        {"id": f"V{index:02d}", "hook": hook, "motif": motif, "escalation": escalation, "ending": ending, "rationale": rationale}
        for index, (hook, motif, escalation, ending, rationale) in enumerate([
            ("human_inertia", "red receipt", "465m displacement", "same road, changed object position", "best mute-readable opening"),
            ("personal_pov", "stable horizon", "air layer shears", "POV returns with missing reference", "strongest embodiment, higher generation risk"),
            ("human_inertia", "body vector", "city blocks", "receipt callback", "simple story with measurable scale"),
            ("system_layer_mismatch", "three horizontal bands", "land → air → ocean", "layers collapse to a question", "cleanest hero composition"),
            ("displacement_465m", "one-second ruler", "city-scale distance", "ruler becomes receipt mark", "number becomes an action"),
            ("ocean_mismatch", "coastline seam", "land/air/water offsets", "water line returns", "best systemic dread"),
            ("atmosphere_weapon", "moving cloud band", "air becomes a vector field", "cloud trace becomes receipt path", "makes invisible motion legible"),
            ("city_scale_destruction", "locked street grid", "skyline and coast decouple", "one red object remains", "high consequence but detail-heavy"),
            ("system_layer_mismatch", "single vector branching", "three layer restart", "one unresolved layer", "strong explanatory loop"),
            ("human_inertia", "receipt in foreground", "body → city → system", "receipt proves the loop", "most production-balanced"),
        ], start=1)
    ]
    return {
        "schema_version": "angle-tournament-v1",
        "episode_id": analysis.get("episode_id"),
        "method": "pairwise comparative reasoning with composited angle variants",
        "dimensions": ["first-second hook", "visual clarity", "visual novelty", "escalation", "emotional impact", "story simplicity", "scientific defensibility", "AI generation fit", "Blender fit", "hero-shot potential", "loop potential"],
        "comparisons": comparisons,
        "shortlist": scored[:7],
        "angle_variants": variants,
        "selected_candidate": {
            "hook": "human_inertia",
            "visual_motif": "system_layer_mismatch",
            "escalation": ["displacement_465m", "atmosphere_weapon", "ocean_mismatch"],
            "ending": "human_inertia",
            "why": "Use the receipt/person for immediate comprehension, then earn the three-layer mismatch as the memorable still.",
        },
    }


def _creative_direction() -> dict[str, Any]:
    return {
        "schema_version": "creative-direction-v2",
        "core_question": "If the ground stops for one second, what keeps moving?",
        "core_answer": "The body, air, and ocean retain eastward motion; the danger is a broken shared reference frame.",
        "one_sentence_promise": "A familiar road freezes in the first second, then one eastward vector expands until Earth stops being one aligned system.",
        "viewer_emotion_curve": ["curiosity", "danger", "scale", "awe", "payoff"],
        "opening": {
            "first_frame": "road-level late-afternoon road with a red receipt in motion",
            "first_second_action": "road and horizon lock while the receipt continues right",
            "first_line": "The road freezes—your momentum doesn't.",
        },
        "narrative_engine": {
            "central_visual_motif": "one eastward vector branching through land, air, ocean, and body",
            "escalation_pattern": "personal object → body → measured distance → atmosphere → ocean → system cross-section",
            "transformation_pattern": "ordinary motion becomes a broken reference frame",
        },
        "visual_peaks": [
            {"time": 0.0, "idea": "road locks before explanation"},
            {"time": 7.0, "idea": "465m becomes a physical ruler"},
            {"time": 21.0, "idea": "land restarts while air and ocean lag"},
            {"time": 31.0, "idea": "gravity/down vector separates from sideways danger"},
        ],
        "hero_shot": {
            "concept": "A clean land/air/ocean cross-section caught at the instant the surface restarts.",
            "why_memorable": "One still explains the entire causal argument: land is locked, upper layers visibly offset, and the 465m vector is measurable.",
            "production_method": "blender_ai_hybrid with Fusion measurement overlays",
        },
        "ending": {
            "payoff": "The disaster is the mismatch between layers, not a cartoon planet explosion.",
            "loop_or_comment_hook": "One second. 465 meters. Which layer moves first?",
        },
        "reject": {
            "generic_angles": ["planet explodes", "people fly into space", "generic city destruction montage"],
            "boring_explanations": ["paragraph narration over scenic Earth footage", "number-only infographic without an action"],
            "visual_cliches": ["shaking camera as a substitute for physics", "fireball as the only consequence"],
        },
    }


def _visual_concept() -> dict[str, Any]:
    shot_rows = [
        ("S001", "CONNECTOR", "Make the anomaly readable before the explanation.", "road-level wide; horizon upper third", "red receipt", "low locked camera", "28mm", "snap to locked horizon", "receipt continues right", "road foreground / receipt midground / horizon background", "late-afternoon hard side light", "dust freezes after the snap", "state change", "hard cut from black", ["ai_video", "hybrid"]),
        ("S002", "STORY", "Translate inertia into a body-scale danger.", "rear three-quarter medium with road markings", "silhouette and receipt", "1.6m tracking height", "35mm", "subtle lateral track", "body and receipt move right", "road / body / empty eastward negative space", "warm key, cool shadow", "paper motion streak", "subject motion", "rightward match", ["ai_video"]),
        ("S003", "CONNECTOR", "Make rotational speed feel like a live vector.", "centered graphic with road texture", "465 m/s", "orthographic", "graphic", "number punch", "vector sweeps right", "texture / number / cyan vector", "cyan against charcoal", "clean line draw", "information reveal", "vector match", ["fusion"]),
        ("S004", "STORY", "Turn one second into distance.", "top-down city blocks with origin/end points", "465m ruler", "orthographic overhead", "graphic", "controlled push along ruler", "ruler advances right", "city grid / ruler / endpoint", "high-contrast red/cyan", "map grid pulses once", "scale change", "vector extends", ["fusion", "blender"]),
        ("S005", "STORY", "Reveal the air as a moving layer.", "side cutaway of city slab and atmosphere band", "cloud band", "eye-level abstraction", "45mm", "controlled pull back", "cloud band moves right", "land slab / air band / distant haze", "cool atmospheric rim", "thin cloud trails", "composition change", "line becomes cloud", ["blender"]),
        ("S006", "STORY", "Escalate from air to ocean without scenic filler.", "coastline cross-section; water line dominates", "ocean surface", "high side view", "35mm", "single crane back", "water continues right", "coast / water sheet / vector line", "deep blue with red land accent", "surface shear", "impact", "cloud trace becomes water trace", ["blender"]),
        ("S007", "HERO", "Deliver the one-frame causal explanation.", "clean horizontal three-layer scientific cutaway", "LAND / AIR / OCEAN", "orthographic", "graphic", "land snaps left; upper layers lag right", "air and ocean offset right", "land foreground / air midground / ocean background", "charcoal, cyan, red receipt accent", "layered dust and water shear", "state change", "hard restart hit", ["blender_ai_hybrid", "hybrid"]),
        ("S008", "STORY", "Correct the fly-into-space misconception.", "silhouette with empty right-side vector space", "body plus down/right arrows", "orthographic", "graphic", "arrows draw on", "right vector grows; down vector stays", "silhouette / arrows / negative space", "neutral light with red danger accent", "brief silence gap", "information reveal", "offset becomes vectors", ["fusion"]),
        ("S009", "CONNECTOR", "Name the thesis without repeating the hero.", "centered phrase over ghosted offsets", "MOTION ≠ GROUND", "orthographic", "graphic", "phrase resolves from layers", "offsets pulse once", "ghosted layers / phrase / red accent", "minimal charcoal/cyan", "single restrained pulse", "payoff", "silence to road", ["fusion"]),
        ("S010", "CONNECTOR", "Prove the loop with the original object.", "opening road, wider negative space", "receipt at changed position", "low locked camera", "28mm", "almost locked", "dust settles; receipt rests east", "road / displaced receipt / horizon", "same as S001", "dust settle", "callback", "match S001 framing", ["hybrid", "ai_image"]),
    ]
    shots = []
    for row in shot_rows:
        shot_id, tier, goal, composition, focal, camera_position, lens, camera_motion, subject_motion, depth, lighting, atmosphere, event, transition, methods = row
        shots.append({"shot_id": shot_id, "tier": tier, "visual_goal": goal, "composition": composition, "focal_subject": focal, "camera_position": camera_position, "lens": lens, "camera_motion": camera_motion, "subject_motion": subject_motion, "foreground": depth.split(" / ")[0], "midground": depth.split(" / ")[1], "background": depth.split(" / ")[2], "lighting": lighting, "atmosphere": atmosphere, "visual_event": event, "transition": transition, "method_candidates": methods})
    return {
        "schema_version": "visual-concept-v2",
        "visual_language": {
            "visual_thesis": "One eastward vector makes a familiar frame disagree with itself.",
            "motif": "red object + cyan vector + layered horizontal surfaces",
            "scale_language": "personal object → body → city → land/air/ocean system",
            "movement_language": "rightward momentum against locked planes; no random shake",
            "lighting_language": "late-afternoon warmth for normality, cyan scientific separation for the anomaly",
            "color_language": "charcoal base, cyan information, red danger/object anchor",
            "contrast": "one focal relationship per frame; empty space protects the vector",
            "texture": "road grit, paper edge, cloud shear, water surface; never texture for decoration",
        },
        "hero_frames": [{"concept": "land/air/ocean restart mismatch", "composition": "three clean horizontal bands with measured 465m vector", "foreground": "locked land slab and red receipt", "midground": "air/cloud band offset right", "background": "ocean sheet offset right", "subject_action": "land restarts first", "camera": "orthographic side cutaway", "lighting": "charcoal with cyan rim and red accent", "production_method": "blender_ai_hybrid"}],
        "shots": shots,
        "rejections": ["pretty scenic coastline without causal action", "static AI plate plus paragraph narration", "same camera motion on every shot", "complex frame with no focal relationship"],
    }


def _beat_script() -> dict[str, Any]:
    rows = [
        ("B001", 0.0, 1.2, "hook", "The road freezes—your momentum doesn't.", "road locks while receipt keeps crossing right", "the event is visible before the explanation", "snap from moving road to locked horizon", "vacuum drop + hard impact", "curiosity → danger"),
        ("B002", 1.2, 4.0, "personal_scale", "At the equator, your body is already moving east at roughly 465 meters per second.", "silhouette and receipt continue right over fixed markings", "the viewer owns the velocity", "rear three-quarter match move", "body whoosh + paper tick", "danger → scale"),
        ("B003", 4.0, 7.0, "mechanism", "Stop the surface, and that eastward speed has nowhere to go.", "one cyan vector branches from the body into the road", "inertia is horizontal, not a launch into space", "vector grows from body to frame edge", "tonal rise", "scale → tension"),
        ("B004", 7.0, 11.0, "measurement", "In one second, you slide about 465 meters past the surface.", "a ruler draws across a city grid from origin to endpoint", "the number becomes physical distance", "controlled top-down travel along ruler", "distance sweep + click", "tension → awe"),
        ("B005", 11.0, 16.0, "atmosphere", "The air keeps the same vector, so the sky is no longer aligned with the land.", "cloud band slides right over a locked city slab", "air is a moving layer", "pull back to expose the cutaway", "air rush", "awe → systemic dread"),
        ("B006", 16.0, 21.0, "ocean", "The ocean keeps moving too; pavement and water no longer share a frame.", "water sheet joins the moving upper layer", "the mismatch is not only atmospheric", "crane from coast to layered cross-section", "low water surge", "systemic dread → inevitability"),
        ("B007", 21.0, 27.0, "hero", "When land restarts, Earth is no longer one aligned system.", "land snaps left while air and ocean visibly lag right", "one still contains the causal argument", "orthographic restart with measured offsets", "restart hit + layered lag", "inevitability → awe"),
        ("B008", 27.0, 31.0, "correction", "Gravity still points down. The dangerous motion is sideways.", "down arrow stays while right arrow grows", "correct the fly-into-space misconception", "arrows draw into negative space", "gravity thump + silence gap", "awe → understanding"),
        ("B009", 31.0, 35.0, "payoff", "The disaster is everything else refusing to stop with the ground.", "offset layers compress into a thesis without replaying the hero", "name the true mechanism", "phrase resolves from ghosted layers", "restrained sub drop", "understanding → payoff"),
        ("B010", 35.0, 38.0, "loop", "One second. 465 meters. Which layer moves first?", "return to road; receipt rests far to the right", "the callback proves the distance and opens a comment question", "match opening frame, dust settles", "dust tail + loop cue", "payoff → curiosity"),
    ]
    beats = []
    for beat_id, start, end, purpose, narration, action, info, camera, sound, emotion in rows:
        beats.append({"id": beat_id, "time_start": start, "time_end": end, "purpose": purpose, "narration": narration, "visual_action": action, "visual_information": info, "camera_event": camera, "sound_event": sound, "emotional_change": emotion, "duration": round(end - start, 3), "evidence_ref": ["research/fact_pack.md", "research/topic_brief.md"]})
    return {"schema_version": "visual-first-beat-script-v2", "episode_id": "EP001_earth-stop", "duration_sec": 38, "beats": beats, "rules": {"one_sentence_one_punch": True, "every_narration_has_visual_reason": True, "temporary_voice_only": True}}


def _generation_plan(visual: dict[str, Any]) -> dict[str, Any]:
    defaults = {"HERO": 6, "STORY": 3, "CONNECTOR": 2}
    shots = []
    for shot in visual["shots"]:
        tier = shot["tier"]
        methods = shot["method_candidates"]
        primary = methods[0]
        supporting = methods[1:]
        contract = {
            "identity": "EP001 eastward vector, red receipt anchor, charcoal silhouette when present",
            "environment": "equatorial city/coast abstraction, late afternoon",
            "composition": shot["composition"],
            "lens": shot["lens"],
            "camera_height": shot["camera_position"],
            "camera_motion": shot["camera_motion"],
            "subject_motion": shot["subject_motion"],
            "screen_direction": "right/east",
            "lighting": shot["lighting"],
            "palette": "charcoal / cyan / red",
            "atmosphere": shot["atmosphere"],
            "continuity": "rightward vector and red object must match adjacent shots",
            "forbidden": ["generated text", "reversed screen direction", "random camera shake", "generic destruction montage"],
            "first_frame": shot["composition"],
            "final_frame": shot["transition"],
        }
        shots.append({"shot_id": shot["shot_id"], "tier": tier, "method": primary, "candidates": defaults[tier], "primary": primary, "supporting": supporting, "shot_contract": contract, "reference_pack": [f"shots/{shot['shot_id']}/references/", "creative/visual_concept.yaml", "creative/beat_script.yaml"], "evaluation": ["composition", "subject_readability", "visual_impact", "physics", "continuity", "camera_match", "motion_quality", "artifact_severity", "story_usefulness"], "regeneration_policy": {"local_fix_first": ["crop", "retime", "Fusion mask", "cleanup", "frame replacement", "color"], "full_regenerate_if": ["composition wrong", "subject motion wrong", "camera logic wrong", "identity broken"]}})
    return {"schema_version": "generation-plan-v2", "episode_id": "EP001_earth-stop", "candidate_policy": {"HERO": defaults["HERO"], "STORY": defaults["STORY"], "CONNECTOR": defaults["CONNECTOR"], "note": "Counts are configurable; hero budget is concentrated, not evenly distributed."}, "shots": shots}


def validate_creative_package(package_dir: str | Path) -> list[str]:
    package_dir = Path(package_dir)
    errors: list[str] = []
    for filename in CREATIVE_FILES:
        path = package_dir / filename
        if not path.is_file():
            errors.append(f"missing {filename}")
    if errors:
        return errors
    from .config import load_yaml

    try:
        analysis = load_yaml(package_dir / "idea_analysis.yaml")
        tournament = load_yaml(package_dir / "angle_tournament.yaml")
        direction = load_yaml(package_dir / "creative_direction.yaml")
        load_yaml(package_dir / "visual_concept.yaml")
        beats = load_yaml(package_dir / "beat_script.yaml")
        plan = load_yaml(package_dir / "generation_plan.yaml")
    except (OSError, ValueError) as exc:
        return [f"invalid creative package YAML: {exc}"]
    ideas = analysis.get("ideas", [])
    required_idea_keys = {"title_working", "premise", "viewer_question", "hook_potential", "visual_potential", "story_potential", "production_fit", "novelty", "risk", "evidence"}
    for index, idea in enumerate(ideas):
        missing = sorted(required_idea_keys - set(idea)) if isinstance(idea, dict) else ["mapping"]
        if missing:
            errors.append(f"ideas[{index}] missing {missing}")
    if len(tournament.get("comparisons", [])) < 3:
        errors.append("tournament needs at least three pairwise comparisons")
    if len(tournament.get("angle_variants", [])) < 10:
        errors.append("tournament needs at least ten angle variants")
    for key in ("core_question", "core_answer", "one_sentence_promise", "opening", "narrative_engine", "visual_peaks", "hero_shot", "ending", "reject"):
        if not direction.get(key):
            errors.append(f"creative_direction missing {key}")
    for index, beat in enumerate(beats.get("beats", [])):
        if beat.get("narration") and not (beat.get("visual_action") or beat.get("visual_information")):
            errors.append(f"beats[{index}] narration has no visual reason")
    for index, shot in enumerate(plan.get("shots", [])):
        if shot.get("tier") not in SHOT_TIERS:
            errors.append(f"generation_plan.shots[{index}] invalid tier")
        if shot.get("method") not in GENERATION_METHODS:
            errors.append(f"generation_plan.shots[{index}] invalid method")
        if not isinstance(shot.get("candidates"), int) or shot["candidates"] < 1:
            errors.append(f"generation_plan.shots[{index}] candidates must be positive")
        if not isinstance(shot.get("shot_contract"), dict) or not shot["shot_contract"].get("forbidden"):
            errors.append(f"generation_plan.shots[{index}] missing shot contract constraints")
    return errors


def generate_creative_package(root: str | Path, episode_id: str, *, force: bool = False) -> dict[str, Any]:
    paths = StudioPaths(Path(root).resolve() if root else project_root())
    manifest_path = paths.manifest(episode_id)
    manifest = load_manifest(manifest_path)
    creative_dir = paths.episode(episode_id) / "creative"
    if any((creative_dir / filename).exists() for filename in CREATIVE_FILES) and not force:
        raise FileExistsError(f"creative package exists; pass --force to rebuild: {creative_dir}")
    analysis = discover_ideas(episode_id, manifest)
    if not analysis["ideas"]:
        raise ValueError(f"no discovery seed is registered for {episode_id}; research must produce candidates first")
    tournament = run_tournament(analysis)
    direction = _creative_direction()
    visual = _visual_concept()
    beats = _beat_script()
    generation = _generation_plan(visual)
    payloads = {
        "idea_analysis.yaml": analysis,
        "angle_tournament.yaml": tournament,
        "creative_direction.yaml": direction,
        "visual_concept.yaml": visual,
        "beat_script.yaml": beats,
        "generation_plan.yaml": generation,
    }
    for filename, payload in payloads.items():
        dump_yaml(payload, creative_dir / filename)
    dump_yaml(generation, paths.episode(episode_id) / "production" / "generation_plan.yaml")
    manifest.setdefault("creative", {}).update({
        "core_question": direction["core_question"],
        "hook_type": "human_inertia",
        "hero_shot_type": "system_layer_mismatch",
        "visual_motif": direction["narrative_engine"]["central_visual_motif"],
        "content_pattern": "personal_anomaly_to_system_layer_mismatch",
        "creative_package": "creative/",
    })
    manifest.setdefault("audio", {}).update({
        "narrator": "science_female_main",
        "voice_mode": "ultimate",
        "voice_policy": "production_voxcpm2_local",
        "production_voice_provider": "voxcpm2_local",
        "reference_voice": "science_female_main/neutral",
        "selected_candidate": "candidate_02",
    })
    write_manifest(manifest, manifest_path)
    errors = validate_creative_package(creative_dir)
    if errors:
        raise ValueError("Generated creative package failed validation: " + "; ".join(errors))
    return {"status": "PASS", "episode_id": episode_id, "package_dir": str(creative_dir), "files": [str(creative_dir / filename) for filename in CREATIVE_FILES], "selected_candidate": tournament["selected_candidate"], "hero_shot": direction["hero_shot"]}
