from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from engine.scene_models import SceneTransform

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
AssetFacing = Literal["left", "right", "neutral"]


def normalize_story_text(value: str) -> str:
    """Normalize free text for deterministic alias and intent matching."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.findall(r"[a-z0-9]+", without_marks))


class AssetSpec(BaseModel):
    """Reusable semantic glyph asset with a default scene placement."""

    id: str = Field(min_length=1)
    word: str = Field(min_length=1)
    glyphs_path: Path
    aliases: list[str] = Field(default_factory=list)
    tags: set[str] = Field(default_factory=set)
    z_index: int = 0
    transform: SceneTransform = Field(default_factory=SceneTransform)
    visible: bool = True
    always_include: bool = False
    facing: AssetFacing = "neutral"

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("asset id cannot be blank")
        if any(character.isspace() for character in normalized):
            raise ValueError("asset id cannot contain whitespace")
        return normalized

    @field_validator("word")
    @classmethod
    def normalize_word(cls, value: str) -> str:
        normalized = "".join(character for character in value.upper() if character.isalpha())
        if not normalized:
            raise ValueError("asset word must contain at least one alphabetic character")
        return normalized

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            alias = normalize_story_text(value)
            if alias and alias not in normalized:
                normalized.append(alias)
        return normalized

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: set[str]) -> set[str]:
        return {
            normalize_story_text(value).replace(" ", "_")
            for value in values
            if normalize_story_text(value)
        }

    @model_validator(mode="after")
    def ensure_word_alias(self) -> "AssetSpec":
        word_alias = normalize_story_text(self.word)
        if word_alias not in self.aliases:
            self.aliases.insert(0, word_alias)
        return self

    def matches(self, normalized_story: str) -> bool:
        padded = f" {normalized_story} "
        return any(f" {alias} " in padded for alias in self.aliases)


class AssetRegistry(BaseModel):
    """Local catalog used by deterministic and future LLM story planners."""

    id: str = Field(default="default", min_length=1)
    width: int = Field(default=1280, gt=0)
    height: int = Field(default=720, gt=0)
    background: str = "transparent"
    assets: list[AssetSpec] = Field(min_length=1)

    @field_validator("background")
    @classmethod
    def validate_background(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized == "transparent":
            return normalized
        if not _HEX_COLOR.fullmatch(value):
            raise ValueError(
                "background must be 'transparent' or a six-digit hexadecimal color"
            )
        return value.upper()

    @model_validator(mode="after")
    def validate_unique_asset_ids(self) -> "AssetRegistry":
        identifiers = [asset.id for asset in self.assets]
        duplicates = sorted(
            identifier
            for identifier in set(identifiers)
            if identifiers.count(identifier) > 1
        )
        if duplicates:
            raise ValueError("asset IDs must be unique: " + ", ".join(duplicates))
        return self

    def by_id(self) -> dict[str, AssetSpec]:
        return {asset.id: asset for asset in self.assets}


def load_asset_registry(path: str | Path) -> AssetRegistry:
    registry_path = Path(path)
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid asset registry JSON: {error}") from error
    return AssetRegistry.model_validate(payload)


def resolve_registry_paths(
    registry: AssetRegistry,
    registry_path: str | Path,
) -> AssetRegistry:
    base_directory = Path(registry_path).resolve().parent
    assets = []
    for asset in registry.assets:
        glyphs_path = asset.glyphs_path
        if not glyphs_path.is_absolute():
            glyphs_path = (base_directory / glyphs_path).resolve()
        assets.append(asset.model_copy(update={"glyphs_path": glyphs_path}))
    return registry.model_copy(update={"assets": assets})
