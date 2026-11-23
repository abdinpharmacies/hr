"""Static addon discovery, including Odoo's implicit built-in addons."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from csv_plan import addon_roots, table_overrides


class DiscoveryTests(unittest.TestCase):
    def config(self, root, paths):
        config = root / 'odoo.conf'
        config.write_text('[options]\naddons_path = ' + ','.join(map(str, paths)) + '\n')
        return config

    def addon(self, root, table='ir_actions'):
        addon = root / 'base'
        addon.mkdir(parents=True)
        (addon / '__manifest__.py').write_text('{}')
        (addon / 'ir_actions.py').write_text(
            "raise RuntimeError('Discovery must never execute addon code')\n"
            "class Actions:\n    _name = 'ir.actions.actions'\n    _table = " + repr(table) + '\n')

    def test_odoo15_and_odoo19_server_layouts_find_core_declarations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for version in ('odoo15', 'odoo19'):
                with self.subTest(version=version):
                    server = root / version / 'server'
                    addons = server / 'addons'
                    addons.mkdir(parents=True)
                    core = server / 'odoo' / 'addons'
                    self.addon(core)
                    config = self.config(root, [addons])
                    self.assertEqual(addon_roots(config), [addons, core])
                    self.assertEqual(table_overrides(config, {'base'}), {'ir.actions.actions': 'ir_actions'})

    def test_explicit_core_and_symlink_duplicates_are_scanned_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            addons = root / 'server' / 'addons'
            addons.mkdir(parents=True)
            core = root / 'server' / 'odoo' / 'addons'
            self.addon(core)
            alias = root / 'alias'
            alias.symlink_to(core, target_is_directory=True)
            config = self.config(root, [addons, core, addons, alias])
            self.assertEqual(addon_roots(config), [addons, core])

    def test_configured_addons_keep_precedence_over_implicit_core(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configured = root / 'server' / 'addons'
            self.addon(configured, 'configured_actions')
            self.addon(root / 'server' / 'odoo' / 'addons')
            config = self.config(root, [configured])
            self.assertEqual(table_overrides(config, {'base'}), {'ir.actions.actions': 'configured_actions'})

    def test_explicit_roots_keep_their_configured_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / 'first', root / 'second'
            self.addon(first, 'first_actions')
            self.addon(second, 'second_actions')
            config = self.config(root, [first, second])
            self.assertEqual(table_overrides(config, {'base'}), {'ir.actions.actions': 'first_actions'})

    def test_unverified_siblings_and_uninstalled_addons_are_not_inferred(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            addons = root / 'server' / 'addons'
            addons.mkdir(parents=True)
            core = root / 'server' / 'odoo' / 'addons'
            self.addon(core)
            (core / 'base' / '__manifest__.py').unlink()
            config = self.config(root, [addons])
            self.assertEqual(addon_roots(config), [addons])
            self.assertEqual(table_overrides(config, {'base'}), {})
            (core / 'base' / '__manifest__.py').write_text('{}')
            self.assertEqual(table_overrides(config, set()), {})


if __name__ == '__main__':
    unittest.main()
