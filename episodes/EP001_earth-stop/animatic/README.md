# EP001 Animatic

This folder is the mandatory low-cost gate before production-quality AI video.
The deterministic storyboard cards are deliberately information-first and are
not presented as final generated imagery.

`build_animatic` creates:

- `cards/S001.png` … `cards/S010.png`
- 540p proxy-ready segment renders under `render_work/`
- `EP001_earth-stop_animatic.mp4`
- `gate.json` with deterministic checks

The animatic uses a temporary system voice when macOS `say` is available and
records each sound stem separately under `audio/`. Resolve remains the intended
editor and Fairlight mixer for the production pass.
