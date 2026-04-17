from __future__ import annotations

from pathlib import Path

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for paths & files.
    """

    model_config = SettingsConfigDict(
        env_prefix="",  # we provide explicit env names per field below
        extra="ignore",
    )

    project_root: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[1]
    )

    data_dir: Path = Field(default=Path("data"))
    pdfs_dir: Path = Field(default=Path("data") / "sfcrs", env="SFCR_DATA")
    output_dir: Path = Field(default=Path("artifacts"), env="SFCR_OUTPUT")

    @field_validator("project_root", "data_dir", "pdfs_dir", "output_dir", mode="after")
    @classmethod
    def _expanduser(cls, v: Path) -> Path:
        return v.expanduser()

    @field_validator(
        "project_root", "data_dir", "pdfs_dir", "output_dir", mode="before"
    )
    @classmethod
    def _coerce_path(cls, v):
        # Accept strings from env and coerce; allow Path passthrough.
        if v is None:
            return v  # will not occur for non-optional fields unless user passes None explicitly
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            return Path(s).expanduser()
        if isinstance(v, Path):
            return v.expanduser()
        return v

    @model_validator(mode="after")
    def _resolve_project_relative_paths(self) -> Settings:
        self.project_root = self.project_root.resolve()
        self.data_dir = self._resolve_path(self.data_dir)
        self.pdfs_dir = self._resolve_path(self.pdfs_dir)
        self.output_dir = self._resolve_path(self.output_dir)
        return self

    def _resolve_path(self, value: Path) -> Path:
        if value.is_absolute():
            return value.resolve()
        return (self.project_root / value).resolve()

    @computed_field(return_type=Path)
    def output_dir_ingest(self) -> Path:
        return self.output_dir / "ingest"

    @computed_field(return_type=Path)
    def output_dir_extract(self) -> Path:
        return self.output_dir / "extract"

    @computed_field(return_type=Path)
    def output_dir_summaries(self) -> Path:
        return self.output_dir / "summaries"


# Lazy singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
