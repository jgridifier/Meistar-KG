from backend.pipeline.java_env import _homebrew_java_homes, ensure_java_available, java_version


def test_ensure_java_available() -> None:
    ensure_java_available()
    version = java_version()
    assert "version" in version.lower()


def test_homebrew_java_paths_are_well_formed() -> None:
    for home in _homebrew_java_homes():
        assert (home / "bin" / "java").exists()