# Configure an editor and verify a full render

Use `scripts/configure_client.py` from a repository checkout to print or explicitly merge a Fusionify MCP configuration. Engine v0.7.0 and bundle v0.7.1 add this setup path for Cursor, Kiro and VS Code alongside the existing Claude options. The helper does not install editor applications or create a curated marketplace listing.

The default `checkout` launcher uses `uv run --frozen --directory` with this checkout. Select `--launcher portable` to reuse the exact `uvx` engine pin from `mcp.json`, so the configured server can start without a runtime checkout. Its first launch requires network access, uvx, Git and the existing FFmpeg/ffprobe prerequisites. No speech model or provider key is bundled.

## Choose a client and destination

| `--client` | Project configuration destination | Server collection |
| --- | --- | --- |
| `cursor` | `YOUR_PROJECT/.cursor/mcp.json` | `mcpServers` |
| `kiro` | `YOUR_PROJECT/.kiro/settings/mcp.json` | `mcpServers` |
| `vscode` | `YOUR_PROJECT/.vscode/mcp.json` | `servers` |
| `claude-code` | `YOUR_PROJECT/.mcp.json` | `mcpServers` |
| `claude-desktop` | The actual Claude Desktop configuration file | `mcpServers` |

Cursor and VS Code receive explicit `type: stdio`. Kiro and Claude Desktop use their command/args format. These formats follow the [Cursor MCP guide](https://cursor.com/docs/mcp), [Kiro configuration guide](https://kiro.dev/docs/mcp/configuration/) and [VS Code MCP reference](https://code.visualstudio.com/docs/agents/reference/mcp-configuration). UI discovery, organization policy and trust prompts remain client responsibilities.

Example PowerShell, run from the Fusionify checkout after choosing your real folders:

```powershell
python scripts/configure_client.py --client cursor --launcher portable --media-root 'C:\Media' --state-root 'C:\FusionifyState\cursor'
```

This prints JSON only. Inspect it, then add an explicit destination to merge it:

```powershell
python scripts/configure_client.py --client cursor --launcher portable --media-root 'C:\Media' --state-root 'C:\FusionifyState\cursor' --write 'C:\MyProject\.cursor\mcp.json'
```

For Kiro or VS Code, change the client and destination to the corresponding table row, and use a separate state folder if clients run independent processes. The same command accepts ordinary POSIX paths on Linux/macOS. `--uv-command` or `--uvx-command` can specify an absolute executable path if the editor's PATH differs from your terminal.

Existing unrelated servers and top-level fields are retained. A backup with a unique name is created before replacing an existing file. Replacing an existing `fusionify-audio` entry requires `--replace`; review its old settings first. The helper accepts strict JSON only. It refuses existing JSONC comments or a mismatched client format without rewriting the file; merge the printed entry manually in the editor instead. It does not grant blanket tool approvals.

## Verify from your editor

1. Open the configured project and inspect the Fusionify MCP entry. Complete the editor's normal server-trust/tool approval flow. Avoid duplicate plugin and manually configured entries.
2. Call `get_workspace` and check engine version/capabilities. Register or select a file inside the configured media directory; chat attachments are not automatically accessible.
3. Call `analyze_audio`, read the timing evidence and call `create_music_direction` with the actual content goal.
4. Create a saved project, inspect `review_content_fit` and `review_music_sync`, then queue `render_video_project` with `preview: false` for the saved full duration. Poll `get_job_status` to completion and inspect the actual artifact.

If startup fails, check the client process's PATH, selected media folder, FFmpeg/ffprobe and state-directory ownership. Separate processes need separate state directories. A configured entry alone does not establish a working tool call.

## Remote configuration

`--mode remote --url https://YOUR_HOST/mcp` prints an entry for an already deployed authenticated endpoint. Cursor uses `${env:FAI_API_TOKEN}`; Kiro, Claude Code and the current VS Code configuration use `${FAI_API_TOKEN}`. Set the value in the actual client host environment. The helper never copies the live environment token into its output. Remote Claude Desktop/web is configured in the client UI, subject to its supported authentication methods; the helper rejects that file-based route. See [deployment](deployment.md). Generating a URL configuration does not deploy a server or provide OAuth.

## Reproducible protocol check

```bash
uv run --frozen python tests/editor_config_smoke.py
```

The check writes three isolated editor-format configurations, reads them back and launches each exact pinned command using the MCP SDK. It discovers 37 tools, analyzes a synthetic 12-second track, selects source seconds 1–11, creates a project, reviews timing and renders the saved ten seconds in full. It probes video/audio streams and compares decoded audio with the correct source range. `--client cursor|kiro|vscode` selects one format; `--artifact-dir PATH` optionally retains synthetic QA videos.

These are generated-config and real protocol/render checks. They do **not** run Cursor, Kiro or VS Code, complete account sign-in or validate a native GUI session. Those checks and public marketplace submission remain open. Synthetic correlation does not establish perceptual beat accuracy on every real soundtrack.

For a real Claude Code CLI connection check, run `uv run --frozen python tests/claude_connection_smoke.py`. It uses the pinned npm CLI, a temporary Claude configuration directory and the generated portable server entry, then requires the client's actual `Connected` status. It does not use a model session or personal credentials. See Anthropic's [MCP quickstart](https://code.claude.com/docs/en/mcp-quickstart) and [configuration environment reference](https://code.claude.com/docs/en/env-vars) for the underlying client commands.
