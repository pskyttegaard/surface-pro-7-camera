#!/usr/bin/python3
"""Non-hardware tests: fake sessions/registry/capture plus a notify-only child."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('rtsp_session', str(ROOT / 'src/sp7-rtsp-session'))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)


def session(**changes):
    value = dict(User=(1000, '/user'), Seat=('seat0', '/seat'), Active=True,
                 Remote=False, Class='user', Type='wayland', State='active')
    return dict(value, **changes)


def node(name=m.NODE, kind='Video/Source'):
    return dict(type='PipeWire:Interface:Node', info=dict(props={
        'node.name': name, 'media.class': kind}))


class Child:
    def __init__(self):
        self.starts = 0
        self.stops = 0
        self.result = None
        self.is_ready = False

    def start(self):
        self.starts += 1

    def stop(self):
        self.stops += 1

    def poll(self):
        return self.result

    def ready(self):
        return self.is_ready


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.backend = Mock()
        self.backend.session.return_value = True
        self.backend.source.return_value = True
        self.child = Child()
        self.now = 0
        self.guard = m.Guard(self.backend, self.child, lambda: self.now)

    def test_local_graphical_predicate(self):
        self.assertTrue(m.eligible_session(session(), 1000))
        self.assertTrue(m.eligible_session(session(Type='x11'), 1000))
        for change in [dict(User=(1001, '/u')), dict(Seat=('', '/s')),
                       dict(Seat=('seat1', '/s')), dict(Active=False),
                       dict(Remote=True), dict(Class='greeter'),
                       dict(Class='manager'), dict(Type='tty'), dict(State='closing')]:
            with self.subTest(change=change):
                self.assertFalse(m.eligible_session(session(**change), 1000))
        self.assertFalse(m.eligible_session({}, 1000))

    def test_exact_logical_source_only(self):
        self.assertTrue(m.has_front_source([node()]))
        for objects in [[], [node('Surface Front Standard')], [node('sp7.front.hq')],
                        [node('ipu4')], [node(kind='Video/Device')],
                        [dict(type='PipeWire:Interface:Device', info=node()['info'])],
                        [dict(type='PipeWire:Interface:Node', info=None)]]:
            self.assertFalse(m.has_front_source(objects))

    def test_no_session_never_queries_pipewire_or_starts(self):
        self.backend.session.return_value = False
        for _ in range(50):
            self.guard.step()
        self.backend.source.assert_not_called()
        self.assertEqual(self.child.starts, 0)
        self.assertEqual(self.guard.state, 'waiting for eligible local session')

    def test_missing_source_waits_without_restarts(self):
        self.backend.source.return_value = False
        for _ in range(50):
            self.guard.step()
        self.assertEqual(self.child.starts, 0)
        self.assertEqual(self.guard.failures, 0)
        self.assertEqual(self.guard.state, 'waiting for Front Standard source')

    def test_ready_notification_required_for_streaming(self):
        self.guard.step()
        self.assertEqual(self.child.starts, 1)
        self.guard.step()
        self.assertNotEqual(self.guard.state, 'streaming')
        self.child.is_ready = True
        self.guard.step()
        self.assertEqual(self.guard.state, 'streaming')

    def test_recheck_session_before_capture(self):
        self.backend.session.side_effect = [True, False]
        self.guard.step()
        self.assertEqual(self.child.starts, 0)

    def test_session_loss_stops_then_waits(self):
        self.guard.step()
        self.backend.session.return_value = False
        self.backend.source.reset_mock()
        self.guard.step()
        self.assertEqual(self.child.stops, 1)
        self.backend.source.assert_not_called()
        self.assertFalse(self.guard.running)
        self.assertEqual(self.guard.state, 'waiting for eligible local session')

    def test_source_loss_stops_and_reappearance_can_start(self):
        self.guard.step()
        self.backend.source.return_value = False
        self.guard.step()
        self.assertEqual(self.child.stops, 1)
        self.assertEqual(self.guard.state, 'waiting for Front Standard source')
        self.backend.source.return_value = True
        self.guard.step()
        self.assertEqual(self.child.starts, 2)

    def test_five_failed_children_exhaust_retries(self):
        for failure in range(1, 6):
            self.child.result = None
            self.guard.step()
            self.child.result = 1
            self.guard.step()
            self.assertEqual(self.guard.failures, failure)
            self.assertEqual(self.guard.state, 'capture child failed/backoff')
            starts = self.child.starts
            self.guard.step()
            self.assertEqual(self.child.starts, starts)
            self.now = self.guard.retry_at
        for _ in range(50):
            self.now += 100
            self.guard.step()
        self.assertEqual(self.child.starts, 5)
        self.backend.session.return_value = False
        self.guard.step()
        self.backend.session.return_value = True
        self.child.result = None
        self.guard.step()
        self.assertEqual(self.child.starts, 6)

    def test_readiness_timeout(self):
        self.guard.step()
        self.now = 46
        self.guard.step()
        self.assertFalse(self.guard.running)
        self.assertEqual(self.guard.failures, 1)
        self.assertEqual(self.child.stops, 1)

    def test_stable_stream_resets_failure_budget(self):
        self.guard.failures = 3
        self.guard.step()
        self.child.is_ready = True
        self.guard.step()
        self.now = 61
        self.guard.step()
        self.assertEqual(self.guard.failures, 0)

    def test_manual_stop_releases_child(self):
        self.guard.step()
        self.guard.stop()
        self.guard.stop()
        self.assertEqual(self.child.stops, 1)
        self.assertFalse(self.guard.running)

    def test_child_spawn_error_enters_backoff(self):
        self.child.start = Mock(side_effect=OSError('simulated spawn error'))
        self.guard.step()
        self.assertEqual(self.guard.failures, 1)
        self.assertFalse(self.guard.running)
        self.assertEqual(self.guard.retry_at, 5)


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.backend = m.Backend.__new__(m.Backend)
        self.backend.uid = 1000
        self.backend.user_bus = object()
        self.backend.system_bus = object()
        self.backend.unit_active = Mock(return_value=True)
        self.backend.call = Mock()

    def test_graphical_target_required(self):
        self.backend.unit_active.return_value = False
        self.assertFalse(self.backend.session())
        self.backend.call.assert_not_called()

    def test_logind_properties_read(self):
        self.backend.call.side_effect = [[('7', 1000, 'peter', 'seat0', '/session7')], session()]
        self.assertTrue(self.backend.session())

    def test_logind_error_fails_closed(self):
        self.backend.call.side_effect = RuntimeError('bus unavailable')
        self.assertFalse(self.backend.session())

    @patch.object(m.subprocess, 'run')
    def test_inactive_media_services_never_connect_or_start(self, run):
        self.backend.unit_active.return_value = False
        self.assertFalse(self.backend.source())
        run.assert_not_called()

    @patch.object(m.subprocess, 'run')
    def test_passive_named_pipewire_registry_query(self, run):
        run.return_value.stdout = json.dumps([node()])
        self.assertTrue(self.backend.source())
        self.assertEqual(run.call_args.args[0], ['/usr/bin/pw-dump', '--remote=pipewire-0'])
        self.assertEqual(run.call_args.kwargs['env']['PIPEWIRE_RUNTIME_DIR'], '/run/user/1000')

    @patch.object(m.subprocess, 'run')
    def test_registry_errors_fail_closed(self, run):
        for error in [subprocess.TimeoutExpired('pw-dump', 2), OSError('missing'),
                      subprocess.CalledProcessError(1, 'pw-dump')]:
            run.side_effect = error
            self.assertFalse(self.backend.source())
        run.side_effect = None
        run.return_value.stdout = 'malformed JSON'
        self.assertFalse(self.backend.source())


class ChildAndUnitTests(unittest.TestCase):
    def test_notify_only_child_and_cleanup(self):
        # A synthetic script sends READY; no GStreamer, PipeWire or devices.
        with tempfile.TemporaryDirectory() as directory:
            server = Path(directory) / 'fake-server.py'
            server.write_text("import os,socket,time\ns=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)\ns.connect(os.environ['NOTIFY_SOCKET'])\ns.send(b'READY=1\\n')\ntime.sleep(20)\n")
            child = m.CaptureChild(server, runtime_dir=directory)
            try:
                child.start()
                deadline = time.monotonic() + 2
                ready = False
                while not ready and time.monotonic() < deadline:
                    ready = child.ready()
                    time.sleep(.01)
                self.assertTrue(ready)
                self.assertIsNone(child.poll())
                notify_dir = Path(child.directory.name)
            finally:
                child.stop()
            self.assertFalse(notify_dir.exists())
            self.assertIsNone(child.process)

    def test_child_pins_target_and_forbids_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            child = m.CaptureChild('/existing-server', runtime_dir=directory)
            with patch.object(m.subprocess, 'Popen') as spawn:
                child.start()
                env = spawn.call_args.kwargs['env']
                self.assertEqual(env['PIPEWIRE_NODE'], m.NODE)
                self.assertEqual(env['PIPEWIRE_REMOTE'], 'pipewire-0')
                for prop in ['target.object=sp7.front.standard', 'node.dont-fallback=true',
                             'node.dont-move=true', 'node.dont-reconnect=true']:
                    self.assertIn(prop, env['PIPEWIRE_PROPS'])
                self.assertEqual(spawn.call_args.args[0],
                                 ['/usr/bin/python3', '/existing-server'])
                child.stop()

    def test_failed_spawn_cleans_notify_socket(self):
        with tempfile.TemporaryDirectory() as directory:
            child = m.CaptureChild('/nonexistent', runtime_dir=directory)
            with patch.object(m.subprocess, 'Popen', side_effect=OSError('spawn failed')):
                with self.assertRaises(OSError):
                    child.start()
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_unit_lifecycle_and_isolation(self):
        unit = (ROOT / 'systemd/user/sp7-front-rtsp.service').read_text()
        self.assertIn('PartOf=graphical-session.target', unit)
        self.assertIn('WantedBy=graphical-session.target', unit)
        self.assertIn('KillMode=control-group', unit)
        self.assertIn('StartLimitBurst=3', unit)
        self.assertIn('Restart=on-failure', unit)
        self.assertNotIn('WantedBy=default.target', unit)
        self.assertNotIn('Wants=pipewire', unit)
        self.assertNotIn('LD_LIBRARY_PATH', unit)
        self.assertNotIn('ExecStartPre=', unit)


if __name__ == '__main__':
    unittest.main(verbosity=2)
