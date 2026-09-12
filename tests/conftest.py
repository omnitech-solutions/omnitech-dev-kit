"""Isolate $KIT_HOME for every test.

The machine layer is real state in the developer's home directory. A test suite that writes there
would both pollute it and read another session's spend, so every test gets its own.
"""
import os, tempfile
import pytest


@pytest.fixture(autouse=True)
def isolated_kit_home(monkeypatch):
    d = tempfile.mkdtemp(prefix="kit-home-")
    monkeypatch.setenv("KIT_HOME", d)
    monkeypatch.setenv("KIT_CONFIG_HOME", d)
    yield d
