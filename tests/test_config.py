import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('configure_client',Path(__file__).parents[1]/'scripts/configure_client.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class ConfigTests(unittest.TestCase):
    def test_client_formats_and_pinned_portable_launcher(self):
        repo=Path(__file__).parents[1]
        template=json.loads((repo/'mcp.json').read_text())['mcpServers']['fusionify-audio']
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for client in module.CLIENTS:
                with self.subTest(client=client):
                    entry=module.config('local',repo,root,root/'state',client=client,launcher='portable')
                    self.assertEqual(entry['args'],template['args'])
                    self.assertEqual(entry['command'],'uvx')
                    self.assertEqual(entry['env']['FAI_MEDIA_ROOT'],str(root.resolve()))
                    self.assertEqual(entry['env']['FAI_STATE_ROOT'],str((root/'state').resolve()))
                    self.assertNotIn('${',json.dumps(entry))
                    self.assertNotIn('autoApprove',entry)
                    self.assertEqual(module.server_key(client),'servers' if client=='vscode' else 'mcpServers')
                    if client in ('cursor','vscode','claude-code'):self.assertEqual(entry['type'],'stdio')
                    else:self.assertNotIn('type',entry)

    def test_each_client_merge_and_explicit_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            for client in module.CLIENTS:
                with self.subTest(client=client):
                    target=Path(tmp)/client/'config.json';target.parent.mkdir()
                    key=module.server_key(client)
                    original={'inputs':[{'id':'keep-this','type':'promptString'}],key:{'other':{'command':'existing'}}}
                    target.write_text(json.dumps(original))
                    entry={'command':'uv','args':['serve']}
                    module.write_config(target,entry,client=client)
                    first=target.read_bytes()
                    with self.assertRaises(ValueError):module.write_config(target,entry,client=client)
                    self.assertEqual(target.read_bytes(),first)
                    module.write_config(target,{'command':'new'},True,client)
                    data=json.loads(target.read_text())
                    self.assertEqual(data['inputs'],original['inputs'])
                    self.assertEqual(data[key]['other'],original[key]['other'])
                    self.assertEqual(data[key]['fusionify-audio'],{'command':'new'})
                    self.assertEqual(len(list(target.parent.glob('config.json.bak-*'))),2)

    def test_malformed_or_wrong_format_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'mcp.json'
            for text in ('[]','{"servers":[]}','{ // comment\n"servers":{}}','{"mcpServers":{}}'):
                with self.subTest(text=text):
                    target.write_text(text)
                    with self.assertRaises(ValueError):module.write_config(target,{},client='vscode')
                    self.assertEqual(target.read_text(),text)
                    self.assertEqual(list(Path(tmp).glob('*.bak-*')),[])

    def test_remote_references_and_invalid_setup(self):
        for client in ('claude-code','cursor','kiro','vscode'):
            entry=module.config('remote','.',url='https://audio.example.com/mcp',client=client)
            expected='Bearer ${env:FAI_API_TOKEN}' if client=='cursor' else 'Bearer ${FAI_API_TOKEN}'
            self.assertEqual(entry['headers']['Authorization'],expected)
        with self.assertRaises(ValueError):module.config('remote','.',url='https://audio.example.com/mcp',client='claude-desktop')
        with self.assertRaises(ValueError):module.config('local','.',media_root='.',client='unknown')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'file').write_text('not a folder')
            with self.assertRaises(ValueError):module.config('local',root,root/'file')
            (root/'mcp.json').write_text(json.dumps({'mcpServers':{'fusionify-audio':{
                'command':'uvx','args':['--from','git+https://invalid.example/repo@main','fusionify-audio','serve']}}}))
            with self.assertRaises(ValueError):module.config('local',root,root,launcher='portable')

    def test_cli_prints_without_writing_or_copying_live_token(self):
        repo=Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);env=dict(os.environ,FAI_API_TOKEN='synthetic-token-must-not-be-copied')
            for client in module.CLIENTS:
                result=subprocess.run([sys.executable,str(repo/'scripts/configure_client.py'),'--client',client,
                    '--launcher','portable','--media-root',str(root)],cwd=root,env=env,text=True,capture_output=True,check=True)
                data=json.loads(result.stdout)
                self.assertIn('fusionify-audio',data[module.server_key(client)])
                self.assertNotIn(env['FAI_API_TOKEN'],result.stdout+result.stderr)
                self.assertEqual(list(root.iterdir()),[])

    def test_merge_preserves_servers_and_backs_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/'config.json'
            target.write_text(json.dumps({'theme':'dark','mcpServers':{'other':{'command':'existing'}}}))
            entry=module.config('local',root,root)
            module.write_config(target,entry)
            data=json.loads(target.read_text())
            self.assertEqual(data['theme'],'dark')
            self.assertEqual(data['mcpServers']['other']['command'],'existing')
            self.assertEqual(len(list(root.glob('config.json.bak-*'))),1)
            with self.assertRaises(ValueError):module.write_config(target,entry)

    def test_remote_config_references_secret_and_rejects_unsafe_url(self):
        entry=module.config('remote','.',url='https://audio.example.com/mcp')
        self.assertEqual(entry['headers']['Authorization'],'Bearer ${FAI_API_TOKEN}')
        for url in ['http://audio.example.com/mcp','https://audio.example.com/','https://x:y@audio.example.com/mcp']:
            with self.assertRaises(ValueError):module.config('remote','.',url=url)


if __name__=='__main__':unittest.main()
