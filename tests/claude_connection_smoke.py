"""Real Claude Code CLI connection check, isolated from personal settings and credentials."""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    repo=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='fai-claude-connection-') as tmp:
        root=Path(tmp);media=root/'media';media.mkdir()
        # Keep runtime/network plumbing, not model keys, account tokens or personal Claude config.
        safe_keys={'PATH','HOME','LANG','TMPDIR','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY',
                   'SSL_CERT_FILE','SSL_CERT_DIR','NODE_EXTRA_CA_CERTS','NPM_CONFIG_CACHE','npm_config_cache'}
        env={k:v for k,v in os.environ.items() if k in safe_keys}
        env['CLAUDE_CONFIG_DIR']=str(root/'claude-config')
        generated=subprocess.check_output([sys.executable,str(repo/'scripts/configure_client.py'),
            '--launcher','portable','--media-root',str(media),'--state-root',str(root/'state')],text=True)
        entry=json.loads(generated)['mcpServers']['fusionify-audio']
        cli=['npx','--yes','@anthropic-ai/claude-code@2.1.316']
        added=subprocess.run([*cli,'mcp','add-json','--scope','user','fusionify-audio',json.dumps(entry)],
                             env=env,cwd=root,text=True,capture_output=True,timeout=60)
        assert added.returncode==0,(added.stdout,added.stderr)
        listed=subprocess.run([*cli,'mcp','list'],env=env,cwd=root,text=True,capture_output=True,timeout=60)
        assert listed.returncode==0,(listed.stdout,listed.stderr)
        clean=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',listed.stdout)
        assert re.search(r'^fusionify-audio:.* - [✔✓√] Connected\s*$',clean,re.MULTILINE),clean
        print('PASS: Claude Code 2.1.316 registers the isolated server and reports Connected. '
              'This checks client connection health, not a model conversation or native editor GUI.')


if __name__=='__main__':main()
