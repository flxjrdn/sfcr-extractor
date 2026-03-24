from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_test_ollama():
    module_name = "_test_scripts_test_ollama"
    sys.modules.pop(module_name, None)

    spec = importlib.util.spec_from_file_location(
        module_name,
        PROJECT_ROOT / "scripts" / "test_ollama.py",
    )
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _ResponseStub:
    status_code = 200
    text = '{"response": "Paris"}'

    def json(self):
        return {
            "response": "Paris",
            "eval_count": 12,
            "total_duration": 345,
        }


def test_importing_script_does_not_call_ollama(monkeypatch):
    def _unexpected_post(*args, **kwargs):
        raise AssertionError("requests.post must not run during module import")

    monkeypatch.setattr("requests.post", _unexpected_post)

    module = _load_test_ollama()

    assert callable(module.main)
    assert callable(module.request_ollama)


def test_main_calls_ollama_only_when_explicitly_executed(monkeypatch, capsys):
    called = {}

    def _fake_post(url, json, timeout):
        called["url"] = url
        called["json"] = json
        called["timeout"] = timeout
        return _ResponseStub()

    monkeypatch.setattr("requests.post", _fake_post)
    module = _load_test_ollama()

    assert module.main() == 0
    out = capsys.readouterr().out

    assert called == {
        "url": "http://localhost:11434/api/generate",
        "json": {
            "model": "mistral",
            "prompt": module.PROMPT,
            "options": {"temperature": 0.2, "num_predict": 128},
            "stream": False,
        },
        "timeout": 180,
    }
    assert "Ollama responded successfully" in out
