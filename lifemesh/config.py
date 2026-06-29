from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ENV_HOME = "LIFEMESH_HOME"
ENV_OBSIDIAN_VAULT = "LIFEMESH_OBSIDIAN_VAULT"
ENV_LMSTUDIO_BASE_URL = "LIFEMESH_LMSTUDIO_BASE_URL"
ENV_EMBEDDING_MODEL = "LIFEMESH_EMBEDDING_MODEL"
ENV_VLM_MODEL = "LIFEMESH_VLM_MODEL"
ENV_SQLITE_VEC_EXTENSION = "LIFEMESH_SQLITE_VEC_EXTENSION"


@dataclass(frozen=True)
class LifemeshConfig:
    home: Path
    obsidian_vault: Path | None
    lmstudio_base_url: str | None
    embedding_model: str | None
    vlm_model: str | None
    sqlite_vec_extension: Path | None

    @property
    def db_path(self) -> Path:
        return self.home / "lifemesh.db"

    @property
    def raw_asset_dir(self) -> Path:
        return self.home / "raw-assets" / "manual-input"


def load_config(
    *,
    home: str | None = None,
    obsidian_vault: str | None = None,
    lmstudio_base_url: str | None = None,
    embedding_model: str | None = None,
    vlm_model: str | None = None,
    sqlite_vec_extension: str | None = None,
) -> LifemeshConfig:
    resolved_home = Path(
        _first_nonempty(home, os.environ.get(ENV_HOME), "~/.lifemesh") or "~/.lifemesh"
    ).expanduser()
    file_config = _read_config_file(resolved_home / "config.json")

    return LifemeshConfig(
        home=resolved_home,
        obsidian_vault=_optional_path(
            _first_nonempty(obsidian_vault, os.environ.get(ENV_OBSIDIAN_VAULT), file_config.get("obsidian_vault"))
        ),
        lmstudio_base_url=_first_nonempty(
            lmstudio_base_url,
            os.environ.get(ENV_LMSTUDIO_BASE_URL),
            file_config.get("lmstudio_base_url"),
        ),
        embedding_model=_first_nonempty(
            embedding_model,
            os.environ.get(ENV_EMBEDDING_MODEL),
            file_config.get("embedding_model"),
        ),
        vlm_model=_first_nonempty(
            vlm_model,
            os.environ.get(ENV_VLM_MODEL),
            file_config.get("vlm_model"),
        ),
        sqlite_vec_extension=_optional_path(
            _first_nonempty(
                sqlite_vec_extension,
                os.environ.get(ENV_SQLITE_VEC_EXTENSION),
                file_config.get("sqlite_vec_extension"),
            )
        ),
    )


def _read_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"LifeMesh config must be a JSON object: {path}")
    return data


def _first_nonempty(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _optional_path(value: str | None) -> Path | None:
    if value is None:
        return None
    return Path(value).expanduser()
