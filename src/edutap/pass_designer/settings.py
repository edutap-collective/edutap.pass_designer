"""Configuration. Everything through pydantic-settings, no stray getenv."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The example catalogue lives at the repository root, not inside the
# installed package (`data/` is not part of the wheel — see
# `pyproject.toml`'s `[tool.hatch.build.targets.wheel]`). A plain relative
# default of `Path("data/catalogue.example.json")` would therefore only
# resolve when the process's working directory happens to be the repository
# root — true for `uv run uvicorn` invoked from there, false for `pytest` run
# from anywhere else, and false for a CI step that `cd`s first.
#
# An editable/source checkout (any local dev or test run) always has this
# file at `<repo root>/src/edutap/pass_designer/settings.py`, so the
# repository root can be found from `__file__` itself, independent of the
# working directory. A container built from the wheel does not have this
# layout at all — there `_REPO_ROOT_CATALOGUE` does not exist, and the
# fallback below is never actually used because `compose.yml` sets
# `PASS_DESIGNER_CATALOGUE_PATH` explicitly.
_REPO_ROOT_CATALOGUE = (
    Path(__file__).resolve().parents[3] / "data" / "catalogue.example.json"
)
_DEFAULT_CATALOGUE_PATH = (
    _REPO_ROOT_CATALOGUE
    if _REPO_ROOT_CATALOGUE.exists()
    else Path("data/catalogue.example.json")
)


class Settings(BaseSettings):
    """Runtime configuration for the designer."""

    model_config = SettingsConfigDict(env_prefix="PASS_DESIGNER_")

    catalogue_path: Path = _DEFAULT_CATALOGUE_PATH
    root_path: str = ""
    """Path prefix when served behind Traefik, e.g. `/portale/pass-designer`."""


def get_settings() -> Settings:
    """Return the settings, read from the environment."""
    return Settings()
