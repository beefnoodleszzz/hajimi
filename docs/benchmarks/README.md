# Benchmark evidence policy

`config/generated/` contains local runtime evidence and is intentionally
ignored. Versioned benchmark baselines belong here only when they are sanitized
and portable: use repo-relative paths or `${HAJIMI_ASSETS}`, record the hardware
class, Blender version, backend, render profile, measured timing, and date, and
never include usernames, installer paths, cookies, or absolute machine paths.
