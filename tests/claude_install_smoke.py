"""Exercise MCP launchers from the installed marketplace plugin and the shipped Desktop archive."""
import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from scipy.io import wavfile

from distribution_smoke import payload
from fusionify_audio.engine import SR
from test_engine import click_track

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = "fusionify-audio-intelligence@fusionify-audio"
CLI = ["npx", "--yes", "@anthropic-ai/claude-code@2.1.316"]


def cli(args, root, env):
    return subprocess.check_output([*CLI, *args], cwd=root, env=env, text=True, timeout=180)


async def analyze(entry, variables, env, track):
    def expand(value):
        for key, replacement in variables.items():
            value = value.replace("${" + key + "}", str(replacement))
        return value

    params = StdioServerParameters(
        command=entry["command"],
        args=[expand(value) for value in entry["args"]],
        env={**env, **{key: expand(value) for key, value in entry["env"].items()}},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = (await session.list_tools()).tools
        report = payload(await session.call_tool("analyze_audio", {"audio_path": track}))
        direction = payload(await session.call_tool("create_music_direction", {
            "analysis_id": report["analysis_id"], "section_count": 3,
        }))
        assert report["beat_count"] > 0 and len(direction["sections"]) == 3
        print(f'{track}: {report["duration_s"]} s, {report["tempo_bpm_estimate"]} estimated BPM, '
              f'{report["beat_count"]} beats, {len(tools)} tools.', flush=True)
        return report


def main():
    with tempfile.TemporaryDirectory(prefix="fusionify install ") as tmp:
        root = Path(tmp)
        media = root / "Music folder"
        media.mkdir()
        wavfile.write(media / "click.wav", SR, click_track(128, 16))
        track = "test track.mp3"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(media / "click.wav"),
                        str(media / track)], check=True)
        keep = {"PATH", "HOME", "LANG", "TMPDIR", "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY",
                "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS", "NPM_CONFIG_CACHE"}
        env = {key: value for key, value in os.environ.items() if key.upper() in keep}
        env.update(CLAUDE_CONFIG_DIR=str(root / "config"), FAI_MEDIA_ROOT=str(media),
                   FAI_STATE_ROOT=str(root / "code state"))
        # Stage only repository files, mirroring a marketplace checkout without the dev venv.
        source = root / "marketplace"
        subprocess.run(["git", "checkout-index", "--all", f"--prefix={source}/"], cwd=ROOT, check=True)
        cli(["plugin", "marketplace", "add", str(source)], root, env)
        cli(["plugin", "install", PLUGIN], root, env)
        installed = next(p for p in json.loads(cli(["plugin", "list", "--json"], root, env)) if p["id"] == PLUGIN)
        assert installed["enabled"]
        status = cli(["mcp", "list"], root, env)
        assert any("plugin:fusionify-audio-intelligence:fusionify-audio:" in line and "Connected" in line
                   for line in status.splitlines()), status
        entry = installed["mcpServers"]["fusionify-audio"]
        code = asyncio.run(analyze(entry, {"CLAUDE_PLUGIN_ROOT": installed["installPath"],
                                          "FAI_MEDIA_ROOT": media}, env, track))

        extension = root / "Desktop extension"
        with ZipFile(ROOT / "downloads" / "fusionify-audio.mcpb") as archive:
            archive.extractall(extension)
        manifest = json.loads((extension / "manifest.json").read_text())
        assert manifest["version"] == installed["version"]
        assert manifest["user_config"]["media_root"]["required"]
        env.pop("FAI_MEDIA_ROOT")
        env["FAI_STATE_ROOT"] = str(root / "desktop state")
        desktop = asyncio.run(analyze(manifest["server"]["mcp_config"], {
            "__dirname": extension, "user_config.media_root": media,
            "user_config.uv_command": shutil.which("uv"),
            "user_config.ffmpeg_dir": Path(shutil.which("ffmpeg")).parent,
        }, env, track))
        assert abs(code["duration_s"] - 16) < 0.1
        assert code["duration_s"] == desktop["duration_s"]
        assert code["beat_count"] == desktop["beat_count"]
        assert abs(code["tempo_bpm_estimate"] - 128) < 4


if __name__ == "__main__":
    main()
