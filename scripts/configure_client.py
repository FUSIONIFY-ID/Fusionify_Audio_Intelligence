"""Generate/merge MCP client config without copying an API token into the file."""
import argparse
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlsplit


def config(mode, project_root, media_root=None, state_root=None, url=None, uv_command='uv'):
    if mode=='remote':
        parsed=urlsplit(url or '')
        if parsed.scheme!='https' and not(parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost')):
            raise ValueError('Remote MCP requires HTTPS, except loopback HTTP for testing.')
        if parsed.path!='/mcp' or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError('Provide the exact /mcp URL without credentials or query parameters.')
        return {'type':'http','url':url,'headers':{'Authorization':'Bearer ${FAI_API_TOKEN}'}}
    if not media_root:raise ValueError('Local mode requires --media-root.')
    env={'FAI_MEDIA_ROOT':str(Path(media_root).expanduser().resolve())}
    if state_root:env['FAI_STATE_ROOT']=str(Path(state_root).expanduser().resolve())
    return {'command':uv_command,'args':['run','--frozen','--directory',str(Path(project_root).resolve()),'fusionify-audio','serve'],'env':env}


def write_config(target: Path, entry: dict, replace: bool=False):
    data=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    if not isinstance(data,dict) or not isinstance(data.get('mcpServers',{}),dict):raise ValueError('Existing config is not a valid MCP JSON object.')
    servers=data.setdefault('mcpServers',{})
    if 'fusionify-audio' in servers and not replace:raise ValueError('Entry already exists; inspect it and use --replace if intended.')
    servers['fusionify-audio']=entry
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():shutil.copy2(target,target.with_name(target.name+'.bak-'+uuid.uuid4().hex[:8]))
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=target.parent,delete=False) as handle:
        json.dump(data,handle,indent=2);handle.write('\n');temporary=handle.name
    os.replace(temporary,target)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',choices=['local','remote'],default='local')
    ap.add_argument('--client',choices=['claude-code','claude-desktop'],default='claude-code')
    ap.add_argument('--project-root',default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument('--media-root');ap.add_argument('--state-root');ap.add_argument('--url')
    ap.add_argument('--uv-command',default='uv');ap.add_argument('--write',type=Path);ap.add_argument('--replace',action='store_true')
    args=ap.parse_args()
    if args.mode=='remote' and args.client=='claude-desktop':
        ap.error('For remote Claude Desktop/web, add a custom connector in the Claude UI; use the deployment guide.')
    try:
        value=config(args.mode,args.project_root,args.media_root,args.state_root,args.url,args.uv_command)
        if args.write:write_config(args.write,value,args.replace);print(f'Updated {args.write}')
        else:print(json.dumps({'mcpServers':{'fusionify-audio':value}},indent=2))
    except ValueError as exc:ap.error(str(exc))


if __name__=='__main__':main()
