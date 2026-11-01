# Deployment and client integration

## Supported topology

One Python process owns one workspace. Local Claude Code/Desktop can launch stdio independently with separate state directories. To share assets/projects between clients, run one HTTP workspace and connect the clients to it. This version does not provide user accounts, OAuth, or per-user tenant isolation.

## Local HTTP test

1. Install Python dependencies and FFmpeg, choose an existing media directory, and set `FAI_MEDIA_ROOT`.
2. Run `uv run fusionify-audio generate-token` locally and store its output securely as `FAI_API_TOKEN`. Do not paste it into chat or commit it.
3. Set `FAI_PUBLIC_BASE_URL=http://127.0.0.1:8000` and optionally `FAI_STATE_ROOT`.
4. Run `uv run fusionify-audio serve-http`.
5. Open the root URL for uploads/preview. The MCP endpoint is `/mcp`, requiring `Authorization: Bearer <token>`.

The service fails startup if the token is missing, too short, non-ASCII, or contains whitespace. Health checks are public and disclose only status/version. API/MCP access requires the token. Browser requests with a foreign Origin are rejected. Only the configured hostname is accepted.

## Docker and public HTTPS

```bash
cp .env.example .env
# Edit .env locally with the generated token and actual HTTPS origin.
docker compose up --build -d
docker compose logs --tail=100 audio
```

Docker Compose publishes the application on host loopback port 8000, uses persistent media/state volumes, and runs the app without root privileges. Put Caddy or another TLS reverse proxy in front of it. An example Caddy file is in `deploy/Caddyfile.example`. Point your actual domain's DNS at the server before requesting certificates.

Set `FAI_PUBLIC_BASE_URL` to the exact public HTTPS origin, without a path/query. Preserve the original Host header through the reverse proxy. The browser console, Origin checks, MCP host checks, and signed download URLs use this configured origin. Allow uploads of at least 64 MiB and sufficient response time for audio analysis. Access logging is disabled by the bundled server to avoid logging signed download query strings.

Do not run multiple Uvicorn/Gunicorn workers against the same state directory. A file lock rejects competing processes. SQLite records persist, but in-flight renders are marked interrupted on restart and must be resubmitted. Back up both media and state volumes together.

No host/domain has been automatically provisioned by this repository. Test the authenticated endpoint from outside your server before configuring Claude web. A successful local HTTP smoke test does not prove public network reachability.

## Claude web / remote Desktop

Use Customize → Connectors → Add custom connector. Supply the actual `https://your-domain/mcp` URL. Configure fixed header authentication using `Authorization: Bearer <workspace token>`. Store that value in the client setting, not a prompt. UI labels and availability can vary by client/account; consult [Anthropic's current connector guide](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).

If the client does not expose request-header configuration, this server's bearer-token mode cannot be used directly there. Use local stdio in Desktop/Code or add an independently reviewed OAuth gateway later. Never remove authentication to make connection discovery succeed.

## Claude Code over HTTP

Generate a config referencing the token environment variable:

```bash
python scripts/configure_client.py --mode remote --url https://your-actual-host/mcp
```

The generated config contains `${FAI_API_TOKEN}` rather than a copied credential. Configure that environment variable in the process running Claude. Use `--write` only with the config file you intend to update.

## Direct URL imports

`FAI_IMPORT_HOSTS` is a comma-separated list of exact public hostnames you permit. Default empty means imports are disabled. Include redirect destinations explicitly if your media host redirects downloads. The import client rejects credentials in URLs, non-HTTPS, non-443 ports and any DNS answer containing a non-public address; it pins the selected IP while verifying TLS against the original hostname.

Use actual file URLs ending in supported extensions. Browser uploads are the simplest path for tracks from your own computer. The tool does not extract media from streaming subscription pages.

## Optional Gemini interpretation

Set `GEMINI_API_KEY` and `FAI_GEMINI_MODEL` in server secret settings. Select an audio-capable model available to your provider account; no model ID is silently assumed. `describe_music` sends a compressed mono audio rendition to Google's official GenerateContent endpoint only when `allow_external_processing=true`.

This may incur charges and transfers the audio to an external provider. The skill must obtain the user's explicit agreement before calling it. Do not request API keys in chat. DSP analysis, marker correction, exports and rendering continue to work without this option.

Offline tests mock the provider's response contract. Actual account/model access, cost, rate limits and interpretive quality require live verification by the operator. Approximate musical descriptions do not override measured or manually corrected timing.

## Artifacts and maintenance

MP4/MP3/JSON/CSV/SVG/SRT/VTT artifacts remain in state storage. Download links are bearer capabilities valid for ten minutes; anyone with a still-valid link can fetch that artifact. Rotate the workspace token to invalidate previously signed links. Do not share tokens or signed URLs publicly.

Plan disk capacity and back up before any manual cleanup. The app does not delete user assets automatically. Keep state/media folders operator-controlled; root boundary checks assume other local programs do not maliciously alter files while they are being rendered.

## Optional offline speech review

See [voice-review.md](voice-review.md) for local model requirements, explicit `--extra speech` launch commands and transcript provenance. Default Docker images omit ASR dependencies/model files; build an operator-managed speech image and mount a read-only model directory if needed. Do not install packages at runtime in the read-only container or expose its model directory to tools. Voice DSP, transcript import/checking and subtitle exports need no speech extra.
