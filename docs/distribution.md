# Install through plugins, marketplaces, or skills.sh

[← Overview](../README.md) · [Deployment](deployment.md) · [Verification](verification.md)

Plugin bundle **v0.7.2** packages the three skills and the tested **v0.7.0 engine** launcher together for native plugin clients. The skills CLI can also install the instructions separately.

| Route | Files in this repository | What is available |
| --- | --- | --- |
| Claude Code | `.claude-plugin/`, `.mcp.json` | Repository marketplace and local plugin installation. |
| Cursor | `.cursor-plugin/`, `plugin.json`, `mcp.json` | Cursor-native and Agent Plugins package formats, plus a repository marketplace index. |
| Kiro | `plugin.json`, `mcp.json`, `skills/` | Agent Plugins power package for GitHub/folder import. |
| VS Code + Copilot | `plugin.json`, `mcp.json`, existing marketplace index | Agent Plugins source package and custom-marketplace route in compatible clients. |
| skills.sh / skills CLI | `skills/*/SKILL.md` and their references | Three individually installable instruction packages. Connect an MCP runtime for audio tools. |

These are source packages. A valid package or repository marketplace does not establish acceptance into a curated public catalog. The classic VS Code Extension Marketplace/VSIX is a separate publication channel; this repository currently ships an Agent Plugins package.

The strict Claude package validator passes, while its separate directory-submission profile still reports the missing owner-selected license and warns about a listing icon. This adapter update does not choose a license or claim official directory approval. Live editor GUI verification remains pending.

## Prepare the local runtime

Have **Python 3.11+**, **uv/uvx**, **Git**, **FFmpeg**, and **ffprobe** available to the editor. Pick an existing media folder. Supply `FAI_MEDIA_ROOT` through the client's plugin/MCP environment settings, or set it before starting the editor:

```bash
export FAI_MEDIA_ROOT="/absolute/path/to/media"
```

PowerShell:

```powershell
$env:FAI_MEDIA_ROOT = 'C:\Media'
```

An already running GUI process may retain its old environment. Verify the value in the actual MCP process rather than assuming it inherited a later shell change. Cursor's native manifest declares this configurable variable.

The portable launcher uses `uvx --from` with a full Git commit pin for engine v0.7.0. Its first start fetches that engine package and dependencies; subsequent starts can use the tool cache. Source audio is processed locally. No speech model is bundled or downloaded. The launcher avoids plugin-root placeholders, so it does not depend on each client implementing the same directory variables.

The existing Claude plugin still runs the engine from its checkout with the frozen project environment. It retains its established installation behavior.

## Cursor plugin

For a local source install, place a complete repository checkout inside Cursor's documented local-plugin directory, for example `~/.cursor/plugins/local/fusionify-audio-intelligence`. Reload the client and inspect the plugin in Customize. The package contains both the portable and Cursor-native manifests; the latter also declares the media-folder variable.

For a team/custom repository marketplace, use the root `.cursor-plugin/marketplace.json` index through the client's supported marketplace configuration. Availability can depend on client version and organization policy.

For a public Cursor Marketplace listing, the repository must be submitted through [Cursor's publication page](https://cursor.com/marketplace/publish) and reviewed. No approved public listing is claimed here.

[Official Cursor plugin documentation](https://cursor.com/docs/plugins) · [Manifest reference](https://cursor.com/docs/reference/plugins)

## Kiro power

In a compatible Kiro client, open Powers, choose Add Custom Power, and import the repository from GitHub or a local folder. Use this repository URL:

```text
https://github.com/FUSIONIFY-ID/Fusionify_Audio_Intelligence
```

Inspect the imported skills and MCP server, complete the media-folder setup, then try `get_workspace` and an actual accessible soundtrack. Importing a repository does not mean the power is listed in Kiro's curated gallery.

[Official power creation/import guide](https://kiro.dev/docs/powers/create/)

## VS Code agent plugin

With agent plugins enabled and a compatible Copilot harness, run **Chat: Install Plugin from Source**, then supply the repository URL or checkout folder. The root `plugin.json` targets Agent Plugins 1.0.0; skills and MCP definitions use their standard locations.

Alternatively, add `FUSIONIFY-ID/Fusionify_Audio_Intelligence` as a custom plugin marketplace in Agent Customizations. The repository includes the existing Claude-format marketplace index, which compatible VS Code clients can consume. Inspect the detected components and perform a tool call after installation. Organization policy and the selected harness can change available installation actions.

This route is in Agent Customizations. A classic editor extension listing is a different package/publication mechanism.

[Official VS Code plugin guide](https://code.visualstudio.com/docs/agent-customization/agent-plugins) · [Authoring reference](https://code.visualstudio.com/docs/agents/reference/agent-plugin-reference)

## skills.sh and the skills CLI

With Node.js/npm available, list the repository's skills without installing:

```bash
npx skills add FUSIONIFY-ID/Fusionify_Audio_Intelligence --list
```

Install with the interactive agent/skill selector:

```bash
npx skills add FUSIONIFY-ID/Fusionify_Audio_Intelligence
```

For example, install all three to a Cursor project:

```bash
npx skills add FUSIONIFY-ID/Fusionify_Audio_Intelligence --agent cursor --skill '*'
```

The available names are `audio-intelligence`, `music-driven-video`, and `workspace-setup`. Their local references stay inside each skill, so installing just one does not require a sibling skill directory. Installing instructions does not start an MCP server or install FFmpeg/model weights.

According to the [skills.sh FAQ](https://skills.sh/docs/faq), directory visibility/ranking is driven by anonymous CLI installation telemetry. A GitHub push or successful discovery is not proof that a directory page is already indexed. There is no approval claim or guaranteed ranking here. Telemetry can be disabled with `DISABLE_TELEMETRY=1`; use that for automated CI checks.

[Skills CLI documentation](https://skills.sh/docs/cli) · [Skills FAQ](https://skills.sh/docs/faq)

## Verify the connection

For an existing editor MCP setup, use the [client-specific configuration generator](editor-setup.md). It supports Cursor, Kiro and VS Code formats, preserves unrelated entries and can reuse the portable engine pin. This is an alternative to native plugin installation; avoid configuring duplicate servers in the same client.

After source installation:

1. Confirm that the client discovers three skills and the `fusionify-audio` MCP entry. Client prefixes may change the displayed server/tool names.
2. Call `get_workspace`, then `analyze_audio` on a real file inside the configured media folder.
3. Use the returned analysis ID to inspect timing or create a project. Do not claim analysis from a filename or an unavailable attachment.

The repository checks canonical JSON schemas, standalone skill references, and a real MCP handshake/audio call through the exact portable launcher. These checks do not replace actual Cursor/Kiro/VS Code UI sessions. No public HTTPS service is provisioned by installing this plugin.

One local process owns each state directory. Set separate `FAI_STATE_ROOT` directories for independent simultaneous clients, or use one shared authenticated HTTP server when clients need the same workspace.

## Engine updates and optional speech

The native launcher currently pins engine code to `910832dc8cf48847384c4f2a4414a0c3b27d9f7f`. Skill-text updates and engine updates are separate: `npx skills update` updates instructions, while changing the engine pin is an explicit release-maintenance action. Dependency versions in uvx's isolated environment are resolved from the package requirements; the code pin is not a complete dependency lock.

For local ASR, configure an operator-prepared `FAI_WHISPER_MODEL_DIR` and include the speech dependency in the actual launcher. A uvx launcher can add `--with "faster-whisper>=1.1,<2"` before `fusionify-audio`; a checkout launcher uses `uv run --frozen --extra speech`. See [voice review](voice-review.md). No provider key or audio upload is needed for the base local workflow.
