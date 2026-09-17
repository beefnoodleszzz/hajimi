# ImageGen Prompts V03 — Story Rebuild

Shared continuity anchor for every plate: a broad equatorial city road at late afternoon, pale concrete buildings, dark asphalt, long side shadows, open screen-right/eastward vanishing line, natural contrast, restrained cyan accents only when requested. Keep the scene editorial and physically legible; no text, captions, logos, watermarks, disaster montage, or extra people.

## Shot 01 — master street plate

```text
Use case: scientific-educational, photorealistic-natural
Asset type: vertical image-to-video master plate
Scene: a broad equatorial city road at late afternoon, one empty crosswalk, pale concrete buildings, dark asphalt, long side shadows, a clear screen-right/eastward vanishing line
Subject: one solitary adult seen from behind in a charcoal jacket and dark trousers, standing at the crosswalk; one small red paper receipt rests near the right shoe
Key details: the person is ordinary and not heroic, the receipt is visibly loose on the asphalt, fine dust sits on the road, the environment feels like a real street before an impossible event
Composition: 9:16 vertical, low ground-level wide shot, person in the lower middle, road leading toward screen right, clean upper negative space for later caption overlay
Lighting/mood: hard late-afternoon side light from screen left, crisp contact shadows, slight dry-air haze, natural contrast, no HDR look
Materials/textures: rough asphalt aggregate, worn white crosswalk paint, dusty paper fibers, concrete facade texture
Constraints: lock the road geometry, building positions, crosswalk, person silhouette, jacket, receipt position, screen-right direction, and lighting; no extra people, cars, signs, readable text, or catastrophe
Avoid: centered postcard composition, empty cosmic background, extreme wide fisheye distortion, planted boots close-up, flying debris, explosions, watermarks
```

## Shot 03 — aerial distance plate

```text
Use case: scientific-educational, photorealistic-natural
Asset type: vertical aerial plate for deterministic distance graphics
Scene: the same equatorial city road and crosswalk seen from a high oblique aerial angle, several connected city blocks leading toward screen right, the coastline barely visible in the far distance
Subject: a small red receipt-sized origin point on the same road, with an empty visible path extending eastward across the blocks
Key details: road lanes and block geometry are clean enough for a later 465-meter measurement line, the red point is the only accent color, no labels are embedded in the image
Composition: 9:16 vertical, high oblique top-down view, origin point in the lower-left third, open road path toward the upper-right third, generous negative space for edit graphics
Lighting/mood: same late-afternoon side light, long shadows aligned consistently toward screen left, clear air
Materials/textures: realistic asphalt, concrete blocks, small trees, subtle road wear
Constraints: preserve a readable straight eastward route and simple block geometry; no in-image numbers, letters, arrows, logos, or extra focal subjects
Avoid: map UI, satellite labels, fantasy city, tangled roads, dense traffic, warped perspective
```

## Shot 04 — connected city/coast plate

```text
Use case: scientific-educational, photorealistic-natural
Asset type: vertical image-to-video plate
Scene: the same city road continuing toward a broad coastline, viewed from a high oblique angle so land, low cloud band, sea surface, and the eastward horizon are visible in one connected space
Subject: fixed city and coastline as the ground reference; a coherent low cloud band, fine sea spray, and long ocean-surface ripples are separate visible layers above and beside it
Key details: land architecture is sharp and fixed, the atmosphere and water have room to move laterally toward screen right, the coast is a continuation of the city rather than an unrelated scenic view
Composition: 9:16 vertical, high wide framing, city in the lower third, coast and ocean receding toward screen right, cloud band crossing the upper middle, clear layer separation
Lighting/mood: late-afternoon light breaking through an overcast cloud deck, restrained blue-gray sea, natural contrast
Materials/textures: concrete buildings, wind-ruffled cloud edges, fine salt spray, layered ocean ripples
Constraints: no giant wave, flooding, storm eye, text, map marks, logos, extra people, or disaster montage; keep the same eastward screen direction
Avoid: generic travel postcard, unrelated coastline, tropical fantasy, dramatic hurricane, excessive motion blur
```

## Shot 05 — restart mismatch model

```text
Use case: scientific-educational, infographic-diagram
Asset type: vertical scientific illustration plate for image-to-video
Scene: a clean dark navy studio background with a three-layer physical cutaway: solid rough land slab at the bottom, a translucent air band above it, and a deep blue ocean layer between them; all three start visibly aligned
Subject: the three material layers are the only focal subjects; a thin cyan eastward trace runs through the air and water layers, with a small red reference mark tied to the land
Key details: land has rough geological texture and a crisp top plane, air has transparent haze, ocean has a clear surface and depth; the graphic must communicate layer separation before motion
Composition: 9:16 vertical, centered stacked layers, clean margins for later labels, no perspective confusion
Lighting/mood: controlled studio illumination, cyan edge light on the moving layers, natural material contrast, educational not apocalyptic
Materials/textures: matte rock, transparent atmospheric haze, deep blue water with visible surface ripples
Constraints: no text, numbers, arrows, cities, people, explosions, cracks, or extra planets; keep the layers geometrically clean and independently readable
Avoid: abstract glowing blobs, fantasy energy beam, cluttered infographic, catastrophic fire montage
```

## Shot 07 — callback plate

Use Shot 01 as the edit target. Change only the state: keep the same road geometry, buildings, lighting, person wardrobe and camera position; move the red receipt far toward screen right and leave a thin settled dust trail. The person is now just outside the frame edge, leaving clean negative space for `WHAT MOVES FIRST?`. Do not change the location into a new street and do not add new objects.
