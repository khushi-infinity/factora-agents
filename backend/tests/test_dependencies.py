"""Toolchain smoke test: every declared dependency must import on this interpreter."""

from __future__ import annotations

import importlib

import pytest

EXPECTED_IMPORTS = (
    "fastapi",
    "uvicorn",
    "pydantic",
    "pydantic_settings",
    "neatlogs",
    "pytest",
    "httpx",
)


@pytest.mark.parametrize("module_name", EXPECTED_IMPORTS)
def test_declared_dependency_imports(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None
