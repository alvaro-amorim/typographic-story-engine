from __future__ import annotations

import json
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

import fitz  # PyMuPDF
from PIL import Image
from pydantic import BaseModel, Field, field_validator, model_validator

AssetCategory = Literal["character", "environment", "object"]
AssetStatus = Literal["primary", "secondary", "candidate"]
PoseSequenceStatus = Literal["planned", "ready", "deprecated"]

_ALLOWED_SVG_TAGS = {
    "svg",
    "g",
    "path",
    "circle",
    "ellipse",
    "rect",
    "polygon",
    "polyline",
    "line",
    "title",
    "desc",
}
_ALLOWED_COLORS = {
    "#000",
    "#000000",
    "black",
    "#fff",
    "#ffffff",
    "white",
    "none",
}


class AssetLicense(BaseModel):
    spdx: str = "CC0-1.0"
    author: str
    source_type: Literal["project-authored", "public-domain", "third-party"]
    source_url: str | None = None
    attribution_required: bool = False


class SilhouetteAsset(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    word: str = Field(min_length=1)
    category: AssetCategory
    subject: str
    pose: str
    view: str
    status: AssetStatus = "candidate"
    roles: list[str] = Field(default_factory=list)
    source_svg: Path
    mask_width: int = Field(default=512, ge=32, le=4096)
    mask_height: int = Field(default=512, ge=32, le=4096)
    anchors: dict[str, tuple[float, float]] = Field(default_factory=dict)
    license: AssetLicense
    tags: list[str] = Field(default_factory=list)

    @field_validator("word")
    @classmethod
    def normalize_word(cls, value: str) -> str:
        normalized = "".join(character for character in value.upper() if not character.isspace())
        if not normalized:
            raise ValueError("word must contain at least one non-whitespace character")
        return normalized

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, value: list[str]) -> list[str]:
        normalized = [role.strip() for role in value]
        if any(not role for role in normalized):
            raise ValueError("asset roles cannot be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("asset roles must be unique")
        return normalized

    @field_validator("anchors")
    @classmethod
    def validate_anchors(
        cls, value: dict[str, tuple[float, float]]
    ) -> dict[str, tuple[float, float]]:
        for name, point in value.items():
            if not name.strip():
                raise ValueError("anchor names cannot be blank")
            if len(point) != 2 or any(coordinate < 0.0 or coordinate > 1.0 for coordinate in point):
                raise ValueError("anchor coordinates must be normalized between zero and one")
        return value


class PoseSequenceSpec(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    subject: str
    from_asset: str
    to_asset: str
    intent: str
    status: PoseSequenceStatus = "planned"


class SilhouetteCatalog(BaseModel):
    version: str
    defaults: dict[str, str] = Field(default_factory=dict)
    pose_sequences: list[PoseSequenceSpec] = Field(default_factory=list)
    assets: list[SilhouetteAsset]

    @field_validator("assets")
    @classmethod
    def unique_ids(cls, value: list[SilhouetteAsset]) -> list[SilhouetteAsset]:
        identifiers = [asset.id for asset in value]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("silhouette asset IDs must be unique")
        return value

    @model_validator(mode="after")
    def validate_catalog_references(self) -> "SilhouetteCatalog":
        assets_by_id = {asset.id: asset for asset in self.assets}

        for role, asset_id in self.defaults.items():
            if not role.strip():
                raise ValueError("default asset role cannot be blank")
            if asset_id not in assets_by_id:
                raise ValueError(
                    f"default asset role '{role}' references unknown asset '{asset_id}'"
                )

        sequence_ids = [sequence.id for sequence in self.pose_sequences]
        if len(sequence_ids) != len(set(sequence_ids)):
            raise ValueError("pose sequence IDs must be unique")

        for sequence in self.pose_sequences:
            if sequence.from_asset == sequence.to_asset:
                raise ValueError("pose sequence must use two different assets")
            try:
                source = assets_by_id[sequence.from_asset]
                destination = assets_by_id[sequence.to_asset]
            except KeyError as error:
                raise ValueError(
                    f"pose sequence '{sequence.id}' references unknown asset '{error.args[0]}'"
                ) from error
            if source.subject != sequence.subject or destination.subject != sequence.subject:
                raise ValueError(
                    f"pose sequence '{sequence.id}' assets must belong to subject '{sequence.subject}'"
                )

        return self

    def get(self, asset_id: str) -> SilhouetteAsset:
        for asset in self.assets:
            if asset.id == asset_id:
                return asset
        available = ", ".join(sorted(asset.id for asset in self.assets))
        raise KeyError(f"unknown silhouette asset '{asset_id}'; available: {available}")

    def get_default(self, role: str) -> SilhouetteAsset:
        try:
            asset_id = self.defaults[role]
        except KeyError as error:
            available = ", ".join(sorted(self.defaults))
            raise KeyError(f"unknown default role '{role}'; available: {available}") from error
        return self.get(asset_id)

    def get_pose_sequence(self, sequence_id: str) -> PoseSequenceSpec:
        for sequence in self.pose_sequences:
            if sequence.id == sequence_id:
                return sequence
        available = ", ".join(sorted(sequence.id for sequence in self.pose_sequences))
        raise KeyError(f"unknown pose sequence '{sequence_id}'; available: {available}")


def load_silhouette_catalog(path: str | Path) -> SilhouetteCatalog:
    catalog_path = Path(path)
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog = SilhouetteCatalog.model_validate(payload)
    base = catalog_path.resolve().parent
    resolved = [
        asset.model_copy(update={"source_svg": (base / asset.source_svg).resolve()})
        for asset in catalog.assets
    ]
    return catalog.model_copy(update={"assets": resolved})


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def validate_silhouette_svg(path: str | Path) -> dict[str, object]:
    svg_path = Path(path)
    if not svg_path.is_file():
        raise ValueError(f"silhouette SVG was not found: {svg_path}")

    root = ElementTree.fromstring(svg_path.read_text(encoding="utf-8"))
    if _local_name(root.tag) != "svg":
        raise ValueError("silhouette source must have an <svg> root")
    if "viewBox" not in root.attrib:
        raise ValueError("silhouette SVG must define a viewBox")

    visible_elements = 0
    for element in root.iter():
        name = _local_name(element.tag)
        if name not in _ALLOWED_SVG_TAGS:
            raise ValueError(f"unsupported SVG element in silhouette source: <{name}>")
        if name not in {"svg", "g", "title", "desc"}:
            visible_elements += 1

        for attribute, raw_value in element.attrib.items():
            attr_name = _local_name(attribute)
            value = raw_value.strip().lower()
            if attr_name in {"href", "src"}:
                raise ValueError("silhouette SVG cannot reference external resources")
            if attr_name in {"filter", "mask", "clip-path"} or "url(" in value:
                raise ValueError("silhouette SVG cannot use filters, masks or external paint servers")
            if attr_name in {"fill", "stroke"} and value not in _ALLOWED_COLORS:
                raise ValueError(
                    f"silhouette SVG colors must be pure black, white or none; found {raw_value}"
                )
            if attr_name == "style" and any(
                forbidden in value for forbidden in ("url(", "filter:", "mask:", "clip-path:")
            ):
                raise ValueError("silhouette SVG style contains a forbidden feature")

    if visible_elements == 0:
        raise ValueError("silhouette SVG does not contain visible geometry")

    return {
        "path": str(svg_path.resolve()),
        "visible_elements": visible_elements,
        "is_valid": True,
    }


def rasterize_silhouette(
    asset: SilhouetteAsset,
    output_path: str | Path,
) -> Path:
    validate_silhouette_svg(asset.source_svg)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    document = fitz.open(stream=asset.source_svg.read_bytes(), filetype="svg")
    try:
        page = document.load_page(0)
        rect = page.rect
        matrix = fitz.Matrix(
            asset.mask_width / rect.width,
            asset.mask_height / rect.height,
        )
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        pixmap.save(str(destination))
    finally:
        document.close()

    with Image.open(destination) as raw:
        grayscale = raw.convert("L").resize(
            (asset.mask_width, asset.mask_height),
            Image.Resampling.LANCZOS,
        )
        binary = grayscale.point(lambda pixel: 0 if pixel < 128 else 255, mode="1")
        binary.convert("L").save(destination)

    validate_binary_mask(destination, asset.mask_width, asset.mask_height)
    return destination


def validate_binary_mask(path: str | Path, width: int, height: int) -> dict[str, object]:
    mask_path = Path(path)
    with Image.open(mask_path) as image:
        grayscale = image.convert("L")
        if grayscale.size != (width, height):
            raise ValueError(
                f"mask dimensions must be {width}x{height}; found {grayscale.width}x{grayscale.height}"
            )
        values = set(grayscale.getdata())

    if not values.issubset({0, 255}):
        raise ValueError("mask must contain only pure black and pure white pixels")
    if 0 not in values:
        raise ValueError("mask must contain a black silhouette")
    if 255 not in values:
        raise ValueError("mask must contain a white background")

    return {
        "path": str(mask_path.resolve()),
        "width": width,
        "height": height,
        "colors": sorted(values),
        "is_valid": True,
    }


def build_catalog_masks(
    catalog: SilhouetteCatalog,
    output_root: str | Path,
    *,
    asset_ids: list[str] | None = None,
) -> dict[str, Path]:
    root = Path(output_root).resolve()
    requested = set(asset_ids or [asset.id for asset in catalog.assets])
    unknown = requested - {asset.id for asset in catalog.assets}
    if unknown:
        raise KeyError("unknown silhouette assets: " + ", ".join(sorted(unknown)))

    built: dict[str, Path] = {}
    for asset in catalog.assets:
        if asset.id not in requested:
            continue
        destination = root / asset.category / asset.subject / asset.id / "mask.png"
        built[asset.id] = rasterize_silhouette(asset, destination)
    return built
