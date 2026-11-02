# Installation routes

Use the user's chosen client. The [repository installation guide](https://github.com/FUSIONIFY-ID/Fusionify_Audio_Intelligence/blob/main/docs/distribution.md) has current client steps and publication status.

- Native plugins bundle these instructions and an MCP launcher. The root Agent Plugins package targets compatible Kiro/VS Code/Cursor versions; a Cursor-specific manifest and the existing Claude marketplace are also present. Source-installable does not mean accepted into a curated public marketplace.
- A skills.sh / skills CLI install copies skill instructions and references only. If tools such as `get_workspace` and `analyze_audio` are absent, connect the MCP runtime before claiming audio measurements, transcriptions or renders.
- The portable launcher needs `uvx`, Git, FFmpeg/ffprobe, and an existing absolute media folder supplied as `FAI_MEDIA_ROOT`. Its first run fetches the documented, commit-pinned engine package and dependencies. Audio processing is local. Model weights are never fetched by this launcher.
- Set the media folder in the editor's MCP environment settings or before launching the editor. Keep unrelated client settings and MCP entries. Only run setup utilities if a real repository checkout is present; a standalone skill directory does not contain `scripts/configure_client.py`.
- When the runtime is connected, call `get_workspace` and analyze an accessible file to verify the tool route. A manifest validation or a CLI skill install does not prove a live editor GUI session works.
- Multiple local clients must use separate state directories or one shared authenticated HTTP workspace; a single state directory has one process owner. Read the existing process-lock error rather than deleting its lock.
- For optional local ASR, keep the speech dependency in the actual server launch and use an operator-prepared model directory. For the portable uvx launch, the operator may add `--with "faster-whisper>=1.1,<2"` before the executable name and configure `FAI_WHISPER_MODEL_DIR`. Never enable external audio processing or download a model silently.
- Obtain updates through the user's selected plugin/skills mechanism. The portable engine uses an explicit Git commit; upgrading skill text does not silently repoint that engine. See the guide's pinned-engine note.
