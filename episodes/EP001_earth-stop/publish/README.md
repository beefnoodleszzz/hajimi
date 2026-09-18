# YouTube Publish Handoff

The manifest defaults to `private`. The `youtube-publisher` skill must open a
fresh ego-browser task space, use the live Studio snapshot to locate controls,
read back metadata, wait without blocking on running checks, and record the
result in `youtube.json`.

No cookies, tokens, or private endpoints belong in this repository.
