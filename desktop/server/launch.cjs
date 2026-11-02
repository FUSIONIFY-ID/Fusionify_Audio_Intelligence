const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const env = { ...process.env };
if (!env.FAI_MEDIA_ROOT || !path.isAbsolute(env.FAI_MEDIA_ROOT) ||
    !fs.statSync(env.FAI_MEDIA_ROOT, { throwIfNoEntry: false })?.isDirectory()) {
  console.error("Choose an existing music and video folder in the Fusionify extension settings.");
  process.exit(1);
}

const engine = path.resolve(__dirname, "..", "engine");
const desktopRoot = path.join(os.homedir(), ".fusionify-audio-desktop");
env.FAI_STATE_ROOT ||= path.join(desktopRoot, "state");
env.UV_PROJECT_ENVIRONMENT = path.join(env.FAI_STATE_ROOT, "runtime");
if (env.FAI_FFMPEG_DIR && path.isAbsolute(env.FAI_FFMPEG_DIR)) {
  const pathKey = Object.keys(env).find(key => key.toUpperCase() === "PATH") || "PATH";
  env[pathKey] = [env.FAI_FFMPEG_DIR, env[pathKey]].filter(Boolean).join(path.delimiter);
}

const child = spawn(env.FAI_UV_COMMAND || "uv", [
  "run", "--frozen", "--directory", engine, "fusionify-audio", "serve"
], { env, stdio: "inherit", windowsHide: true });
child.on("error", error => {
  console.error("Could not launch uv. Check the uv executable in Fusionify settings.", error.message);
  process.exitCode = 1;
});
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => child.kill(signal));
}
child.on("exit", (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
