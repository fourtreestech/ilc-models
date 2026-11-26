"""Tests for the package's public interface"""

import importlib

import pytest

import ilc_models

SUBMODULES = ("event", "league", "lineup", "match", "player", "table", "user")


@pytest.mark.parametrize("name", ilc_models.__all__)
def test_public_name_is_exported(name):
    assert hasattr(ilc_models, name)


@pytest.mark.parametrize("name", ilc_models.__all__)
def test_public_name_is_the_submodule_object(name):
    exported = getattr(ilc_models, name)
    sources = [
        getattr(mod, name)
        for mod in (importlib.import_module(f"ilc_models.{s}") for s in SUBMODULES)
        if hasattr(mod, name)
    ]
    assert sources
    assert all(source is exported for source in sources)


def test_all_public_submodule_names_are_exported():
    for s in SUBMODULES:
        mod = importlib.import_module(f"ilc_models.{s}")
        for name, obj in vars(mod).items():
            if name.startswith("_") or getattr(obj, "__module__", None) != mod.__name__:
                continue
            assert name in ilc_models.__all__, f"{s}.{name} not in __all__"
