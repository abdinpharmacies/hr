import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def launcher(tmp_path):
    path = Path(__file__).parents[1] / 'scripts/dev_services.py'
    spec = importlib.util.spec_from_file_location('dev_services', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RUNTIME = tmp_path
    module.STATE = tmp_path / 'services.json'
    module.CONFIG = tmp_path / 'config.json'
    return module


def test_disabled_reception_fails_before_network(launcher, monkeypatch):
    values = {
        'database_url': 'postgresql://crm_messaging_callcenter:test@127.0.0.1/crm_messaging_callcenter',
        'odoo_url': 'http://127.0.0.1:4092',
        'odoo_database': 'callcenter',
        'odoo_key': 'test-key',
        'allow_loopback_http': True,
        'odoo_transport': 'controller_v1',
        'accounts': {'tg-callcenter': {
            'provider': 'telegram', 'provider_account': '8933526980',
            'token_source': 'odoo', 'webhook_secret': 'test-secret-123456',
            'enabled': False, 'reception': 'polling',
        }},
    }
    launcher.CONFIG.write_text(json.dumps(values))
    launcher.CONFIG.chmod(0o600)

    def unexpected_network(*args, **kwargs):
        pytest.fail('Disabled reception must not request credentials or contact providers')

    monkeypatch.setattr('httpx.Client', unexpected_network)
    with pytest.raises(launcher.StartupBlocked, match='explicitly enabled'):
        launcher.preflight()


def test_pid_from_previous_boot_is_not_owned(launcher, monkeypatch):
    monkeypatch.setattr(launcher, 'boot_identity', lambda: 'current-boot')
    monkeypatch.setattr(launcher, 'process_identity', lambda pid: 'same-start-tick')
    assert not launcher.running({'pid': 42, 'identity': 'same-start-tick', 'boot': 'previous-boot'})
    assert launcher.running({'pid': 42, 'identity': 'same-start-tick', 'boot': 'current-boot'})


@pytest.mark.parametrize('failed_service,exit_status', [('api', 1), ('receiver', 1), ('worker', 1), ('receiver', 75)])
def test_service_failure_cleanup_and_restart_classification(launcher, monkeypatch, failed_service, exit_status):
    children = []

    class Child:
        def __init__(self, name):
            self.pid = 100 + len(children)
            self.result = exit_status if name == failed_service else None
            self.waited = False

        def poll(self):
            return self.result

        def terminate(self):
            self.result = -15

        def wait(self, timeout=None):
            self.waited = True
            return self.result

    def launch(command, **kwargs):
        name = ['api', 'receiver', 'worker'][len(children)]
        child = Child(name)
        children.append(child)
        return child

    monkeypatch.setattr(launcher.subprocess, 'Popen', launch)
    monkeypatch.setattr(launcher.signal, 'signal', lambda *args: None)
    expected = launcher.StartupBlocked if failed_service == 'receiver' and exit_status != 75 else launcher.StartupUnavailable
    with pytest.raises(expected):
        launcher.supervise()
    assert len(children) == 3
    assert all(child.result is not None and child.waited for child in children)
    assert not launcher.STATE.exists()
