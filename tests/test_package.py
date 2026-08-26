"""The package is importable and declares its version."""


def test_package_exposes_a_version() -> None:
    import edutap.pass_designer

    assert isinstance(edutap.pass_designer.__version__, str)
    assert edutap.pass_designer.__version__
