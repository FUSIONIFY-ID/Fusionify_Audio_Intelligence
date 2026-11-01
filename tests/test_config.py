import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('configure_client',Path(__file__).parents[1]/'scripts/configure_client.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class ConfigTests(unittest.TestCase):
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
