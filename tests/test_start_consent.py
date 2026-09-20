"""First-run downloads must require an affirmative answer, even for --update."""
import hashlib
import os
import sys

import pytest
import start


@pytest.fixture
def launcher(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(start, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['start.py', '--no-browser'])
    (tmp_path / 'requirements.txt').write_text('yt-dlp\nyt-dlp-ejs\n')
    calls = []

    def create(location, with_pip):
        calls.append('venv')
        binary = location / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        binary.parent.mkdir(parents=True)
        binary.touch()

    monkeypatch.setattr(start.venv, 'create', create)
    monkeypatch.setattr(start.subprocess, 'call', lambda cmd, **kw: calls.append(cmd) or 0)
    monkeypatch.setattr(start.shutil, 'which', lambda name: name)
    return tmp_path, calls


@pytest.mark.parametrize('answer', ['', 'n', 'no', 'yes'])
def test_decline_has_no_environment_install_or_server_side_effects(launcher, monkeypatch, answer):
    root, calls = launcher
    monkeypatch.setattr('builtins.input', lambda prompt: answer)
    with pytest.raises(SystemExit, match='declined'):
        start.main()
    assert calls == []
    assert not (root / '.venv').exists()


@pytest.mark.parametrize('error', [EOFError, KeyboardInterrupt])
def test_no_interactive_answer_fails_closed(launcher, monkeypatch, error):
    root, calls = launcher

    def no_answer(prompt):
        raise error

    monkeypatch.setattr('builtins.input', no_answer)
    with pytest.raises(SystemExit, match='declined'):
        start.main()
    assert calls == []
    assert not (root / '.venv').exists()


def test_approved_install_then_start(launcher, monkeypatch):
    root, calls = launcher
    monkeypatch.setattr('builtins.input', lambda prompt: 'Y')
    assert start.main() == 0
    assert calls[0] == 'venv'
    assert calls[1][1:5] == ['-m', 'pip', 'install', '--upgrade']
    assert calls[2][1:4] == ['-m', 'uvicorn', 'app.main:app']
    assert (root / '.venv/.clipnest-requirements').is_file()


def test_ready_environment_starts_without_install_or_prompt(launcher, monkeypatch):
    root, calls = launcher
    binary = root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    binary.parent.mkdir(parents=True)
    binary.touch()
    marker = root / '.venv/.clipnest-requirements'
    marker.write_text(hashlib.sha256((root / 'requirements.txt').read_bytes()).hexdigest())
    monkeypatch.setattr('builtins.input', lambda prompt: pytest.fail('No installation to approve'))
    assert start.main() == 0
    assert len(calls) == 1 and calls[0][1:3] == ['-m', 'uvicorn']

    monkeypatch.setattr(sys, 'argv', ['start.py', '--no-browser', '--update'])
    monkeypatch.setattr('builtins.input', lambda prompt: '')
    calls.clear()
    with pytest.raises(SystemExit, match='declined'):
        start.main()
    assert calls == []
