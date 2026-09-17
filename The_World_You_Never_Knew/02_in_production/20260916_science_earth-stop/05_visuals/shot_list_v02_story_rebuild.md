# Shot List V2 — Story Rebuild

> 9:16 vertical. The sequence follows one event, one screen direction, and one recurring red object. Exact edit points are taken from the new voice ASR, not from proportional stretching.

## Continuity anchors

- **Location anchor:** one broad equatorial city road at late afternoon, pale concrete buildings, dark asphalt, long shadows, open eastward vanishing line.
- **Human proxy:** one solitary adult seen mostly from behind or in silhouette; charcoal jacket, dark trousers, no facial close-up, no identity-dependent dialogue.
- **Object anchor:** one small red paper receipt on the road; it always moves toward screen right/east.
- **Motion anchor:** thin cyan eastward trace appears only when a new scale of the event is revealed.
- **Screen direction:** all inertia and loose material travel screen right; do not reverse direction between shots.

## Director handoff

| ID | Approx. beat | Task | State in | Vector / action markers | Final state | Risk / editor note |
|---|---|---|---|---|---|---|
| 01 | 0–6s | Establish ordinary ground, then lock it | Person standing at crosswalk; receipt near right shoe | `action_start`: normal wind; `impact_peak`: road and shadows freeze; `action_release`: receipt begins to slide right | Fixed road, person just beginning to lose balance, receipt leaving the shoe | Avoid traffic montage and extra people. This is the hook, not an establishing postcard. |
| 02 | 6–12s | Show “you do not stop” | Same road, same person, receipt in same screen area | `action_start`: pavement markings fixed; `impact_peak`: torso and receipt travel right; `action_release`: dust trail extends right | Road/buildings remain geometrically fixed; person and receipt are displaced right | No flying upward, no planted boots, no camera shake; the conflict is horizontal. |
| 03 | 12–20s | Turn speed into a visible distance | Aerial view of the same road grid with the red receipt's start point | `action_start`: red origin point; `impact_peak`: cyan line draws across several blocks; `action_release`: destination point holds | A clean 465 m path remains readable | Use deterministic line and number overlays; generated image supplies only the road geometry. |
| 04 | 20–30s | Expand from person to atmosphere/ocean | Coastline connected to the same city direction | `action_start`: city and land fixed; `impact_peak`: cloud band, sea surface, and spray move right at related but different speeds; `action_release`: three traces hold | Land is fixed while air and water visibly carry momentum | One crane/pull-back only. Do not cut to an unrelated scenic coast. |
| 05 | 30–40s | Deliver the restart consequence | Clean scientific cutaway: land slab, air band, ocean layer | `action_start`: three layers aligned; `impact_peak`: land restarts first, air and ocean lag right; `action_release`: offset remains visible | A stable, legible misalignment; no explosion montage | This is an inference model, not documentary footage; keep the geometry clean. |
| 06 | 40–45s | Correct “fly into space” intuition | Graphic silhouette over the same road texture | `action_start`: downward gravity vector and rightward velocity vector appear; `impact_peak`: rightward vector dominates; `action_release`: both vectors hold | Down arrow stays attached; eastward arrow is the threat | Short graphic beat; do not return to the old fixed-boots image. |
| 07 | 45–52s | Close the loop and invite comments | Same crosswalk as Shot 01, receipt now far to the right | `action_start`: dust settles; `impact_peak`: final cyan trace fades; `action_release`: question card holds | Same road, changed receipt position, clean negative space for CTA | Match the first frame's direction and light; final question must be earned by the callback. |

## Generation boundary

ImageGen creates the street, aerial road grid, connected coastline, scientific cutaway, and callback plate. Local graphics create only precise vectors, distance labels, captions, and the gravity/sideways diagram. Google Flow animates the generated plates; it does not invent a new story inside a shot.
