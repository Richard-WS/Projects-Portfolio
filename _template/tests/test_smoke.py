"""Smoke test: the package imports and reports a version."""


def test_package_imports():
    import example

    assert example.__version__ == "0.1.0"
