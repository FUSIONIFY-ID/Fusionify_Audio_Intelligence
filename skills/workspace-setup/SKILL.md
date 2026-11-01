---
name: workspace-setup
description: Set up or troubleshoot Fusionify Audio Intelligence for Claude Code, Desktop, and remote web connectors. Use for plugin/MCP installation, inaccessible uploads, authentication errors, expired downloads, interrupted jobs, or workspace recovery.
---

# Workspace setup and recovery

- Read the repository README and `docs/deployment.md` before configuring a host. Use `fusionify-audio doctor` to inspect FFmpeg availability and documented limits.
- For local Desktop/Code, use `scripts/configure_client.py` to generate JSON with actual absolute paths. It prints a configuration by default; `--write` explicitly merges a file and creates a backup. Do not overwrite other MCP entries. The CLI script is part of the repository, not an MCP tool.
- For the Claude Code plugin, load the repository's marketplace/plugin or use `--plugin-dir`; set the media root in the process environment. Distinguish plugin-root `.mcp.json` from client config containing `mcpServers`.
- For web or a shared Desktop/Code workspace, use one authenticated HTTP server with a public HTTPS origin. Configure the exact `/mcp` URL and authorization request header in the client. Do not use a GitHub URL as an MCP endpoint. If the client's request-header option is unavailable, explain that limitation and use local mode rather than disabling server authentication.
- Generate tokens locally, store them in server/client secret settings, and never ask the user to paste them into chat. This deployment has one trusted owner workspace. Do not advertise it as an isolated multi-user SaaS.
- A chat attachment is not automatically in the workspace. Use the returned upload page or a real accessible local path. Import URLs only from operator-approved hosts; do not bypass allowlists, private-IP checks, authentication or subscription restrictions.
- Read `list_video_projects` and `list_render_jobs` to recover work. Re-read project revisions before updating. Refresh job status for a new expiring download link. Resubmit interrupted jobs after reviewing their project revision.
- One process owns a state directory. If the directory is locked, connect to the running HTTP server or use a separate state directory; never remove an active lock or start competing writers.
- Distinguish repository tests, actual public deployment, and live Claude-client verification. Report only the checks that really ran.

- For local transcription, inspect `get_workspace.speech_review`. Read `docs/voice-review.md`: install the optional `speech` extra, provide a complete converted local model via `FAI_WHISPER_MODEL_DIR`, and keep that extra in the actual launch command (`uv run --frozen --extra speech ...`). A default launch may omit optional dependencies. Never treat configuration as validated inference or download/upload audio silently. Voice DSP and imported-script checking work without ASR.
