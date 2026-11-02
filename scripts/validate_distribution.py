"""Validate native plugin schemas and standalone skill references. No runtime installs."""
import argparse
import json
import re
import tomllib
from pathlib import Path
from urllib.parse import unquote,urlsplit

from jsonschema import Draft202012Validator


def validate(root,schema_dir):
    engine_version=tomllib.loads((root/'pyproject.toml').read_text())['project']['version']
    version=json.loads((root/'plugin.json').read_text())['version']
    for name in ['plugin','mcp']:
        schema=json.loads((schema_dir/f'{name}.schema.json').read_text())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(json.loads((root/f'{name}.json').read_text()))
    for file in ['plugin.json','.cursor-plugin/plugin.json','.claude-plugin/plugin.json']:
        item=json.loads((root/file).read_text())
        assert item['version']==version,(file,'version mismatch')
        assert item['name']=='fusionify-audio-intelligence',(file,'unexpected plugin')
    cursor=json.loads((root/'.cursor-plugin/plugin.json').read_text())
    for name in ['skills','mcpServers']:
        target=(root/cursor[name]).resolve()
        assert target.is_relative_to(root) and target.exists(),(name,'invalid component path')
    for file in ['.cursor-plugin/marketplace.json','.claude-plugin/marketplace.json']:
        entries=json.loads((root/file).read_text())['plugins']
        assert len({e['name'] for e in entries})==len(entries),'duplicate marketplace entry'
        for entry in entries:
            assert (root/entry['source']).resolve()==root,'unexpected marketplace root'
            assert entry['version']==version,'marketplace version mismatch'
    config=json.loads((root/'mcp.json').read_text())
    server=config['mcpServers']['fusionify-audio']
    assert server['command']=='uvx' and server['args'][-2:]==['fusionify-audio','serve'],'unexpected launcher'
    source=server['args'][server['args'].index('--from')+1]
    assert re.fullmatch(r'git\+https://github\.com/FUSIONIFY-ID/Fusionify_Audio_Intelligence@[a-f0-9]{40}',source),'engine must use a full commit pin'
    documented=re.search(r'currently pins engine code to `([a-f0-9]{40})`',(root/'docs/distribution.md').read_text())
    assert documented and documented.group(1)==source.rsplit('@',1)[1],'documented engine pin differs from mcp.json'
    assert '${PLUGIN_ROOT}' not in json.dumps(config) and '${CURSOR_PLUGIN_ROOT}' not in json.dumps(config),'client-specific root expansion'
    required=set(re.findall(r'\$\{([A-Z_]+)\}',json.dumps(config)))
    assert required.issubset(cursor['variables']['properties']),'undeclared Cursor variable'
    checked=0;names=[]
    for skill in sorted((root/'skills').iterdir()):
        if not (skill/'SKILL.md').exists():continue
        names.append(skill.name)
        for doc in skill.rglob('*.md'):
            for link in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
                url=urlsplit(link)
                if url.scheme or url.netloc or not url.path:continue
                target=(doc.parent/unquote(url.path)).resolve()
                assert target.is_relative_to(skill.resolve()),(doc,'reference escapes standalone skill',link)
                assert target.is_file(),(doc,'missing reference',link)
                checked+=1
    assert names==['audio-intelligence','music-driven-video','workspace-setup'],names
    return {'schemas':'Agent Plugins 1.0.0','plugin_version':version,'engine_package_version':engine_version,'skills':names,'relative_references_checked':checked,
            'engine_source':source,'note':'Schema/path checks do not establish marketplace acceptance or live client UI behavior.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema-dir',type=Path,required=True,help='Directory containing canonical plugin.schema.json and mcp.schema.json')
    args=parser.parse_args()
    print(json.dumps(validate(Path(__file__).resolve().parents[1],args.schema_dir),indent=2))


if __name__=='__main__':main()
