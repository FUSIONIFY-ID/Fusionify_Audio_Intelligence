"""Generate/merge MCP client config without copying an API token into the file."""
import argparse
import json
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlsplit


CLIENTS=('claude-code','claude-desktop','cursor','kiro','vscode')


def server_key(client):
    if client not in CLIENTS:raise ValueError('Unsupported client.')
    return 'servers' if client=='vscode' else 'mcpServers'


def config(mode, project_root, media_root=None, state_root=None, url=None, uv_command='uv',
           client='claude-code', launcher='checkout', uvx_command='uvx'):
    server_key(client)
    if mode not in ('local','remote'):raise ValueError('Mode must be local or remote.')
    if launcher not in ('checkout','portable'):raise ValueError('Launcher must be checkout or portable.')
    if mode=='remote':
        if client=='claude-desktop':
            raise ValueError('Add remote Claude Desktop/web connectors in the client UI; see the deployment guide.')
        parsed=urlsplit(url or '')
        if parsed.scheme!='https' and not(parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost')):
            raise ValueError('Remote MCP requires HTTPS, except loopback HTTP for testing.')
        if not parsed.hostname or parsed.path!='/mcp' or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError('Provide the exact /mcp URL without credentials or query parameters.')
        reference='${env:FAI_API_TOKEN}' if client=='cursor' else '${FAI_API_TOKEN}'
        entry={'url':url,'headers':{'Authorization':'Bearer '+reference}}
        if client not in ('cursor','kiro'):entry['type']='http'
        return entry
    if not media_root:raise ValueError('Local mode requires --media-root.')
    media=Path(media_root).expanduser().resolve(strict=True)
    if not media.is_dir():raise ValueError('Media root must be an existing directory.')
    env={'FAI_MEDIA_ROOT':str(media)}
    if state_root:env['FAI_STATE_ROOT']=str(Path(state_root).expanduser().resolve())
    if launcher=='portable':
        template=json.loads((Path(project_root)/'mcp.json').read_text(encoding='utf-8'))['mcpServers']['fusionify-audio']
        args=template['args']
        if (template['command']!='uvx' or not isinstance(args,list) or len(args)!=4 or args[0]!='--from'
                or args[-2:]!=['fusionify-audio','serve'] or not isinstance(args[1],str)
                or not re.fullmatch(r'git\+https://github\.com/FUSIONIFY-ID/Fusionify_Audio_Intelligence@[a-f0-9]{40}',args[1])):
            raise ValueError('Portable launcher must use the documented commit-pinned Fusionify engine.')
        entry={'command':uvx_command,'args':list(args),'env':env}
    else:
        entry={'command':uv_command,'args':['run','--frozen','--directory',str(Path(project_root).resolve()),'fusionify-audio','serve'],'env':env}
    if client in ('claude-code','cursor','vscode'):entry['type']='stdio'
    return entry


def write_config(target: Path, entry: dict, replace: bool=False, client='claude-code'):
    key=server_key(client)
    data=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    if not isinstance(data,dict) or not isinstance(data.get(key,{}),dict):raise ValueError('Existing config is not a valid MCP JSON object.')
    other='mcpServers' if key=='servers' else 'servers'
    if key not in data and other in data:raise ValueError('Existing config uses a different client format; select the intended file/client.')
    servers=data.setdefault(key,{})
    if 'fusionify-audio' in servers and not replace:raise ValueError('Entry already exists; inspect it and use --replace if intended.')
    servers['fusionify-audio']=entry
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():shutil.copy2(target,target.with_name(target.name+'.bak-'+uuid.uuid4().hex[:8]))
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=target.parent,delete=False) as handle:
        json.dump(data,handle,indent=2);handle.write('\n');temporary=handle.name
    try:os.replace(temporary,target)
    finally:Path(temporary).unlink(missing_ok=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',choices=['local','remote'],default='local')
    ap.add_argument('--client',choices=CLIENTS,default='claude-code')
    ap.add_argument('--launcher',choices=['checkout','portable'],default='checkout',help='Portable reuses the commit pin in mcp.json.')
    ap.add_argument('--project-root',default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument('--media-root');ap.add_argument('--state-root');ap.add_argument('--url')
    ap.add_argument('--uv-command',default='uv');ap.add_argument('--uvx-command',default='uvx')
    ap.add_argument('--write',type=Path,help='Explicit destination, strict JSON only; existing JSONC is not rewritten.')
    ap.add_argument('--replace',action='store_true')
    args=ap.parse_args()
    if args.mode=='remote' and args.client=='claude-desktop':
        ap.error('For remote Claude Desktop/web, add a custom connector in the Claude UI; use the deployment guide.')
    try:
        value=config(args.mode,args.project_root,args.media_root,args.state_root,args.url,args.uv_command,
                     args.client,args.launcher,args.uvx_command)
        if args.write:write_config(args.write,value,args.replace,args.client);print(f'Updated {args.write}')
        else:print(json.dumps({server_key(args.client):{'fusionify-audio':value}},indent=2))
    except OSError:ap.error('A required directory or configuration file is unavailable; inspect your paths and permissions.')
    except (KeyError,TypeError):ap.error('Portable launcher manifest is malformed.')
    except ValueError as exc:ap.error(str(exc))


if __name__=='__main__':main()
