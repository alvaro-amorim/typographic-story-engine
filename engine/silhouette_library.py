from __future__ import annotations

import json
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

import fitz  # PyMuPDF
from PIL import Image
from pydantic import BaseModel, Field, field_validator

AssetCategory = Literal["character", "environment", "object"]

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


class SilhouetteCatalog(BaseModel):
    version: str
    assets: list[SilhouetteAsset]

    @field_validator("assets")
    @classmethod
    def unique_ids(cls, value: list[SilhouetteAsset]) -> list[SilhouetteAsset]:
        identifiers = [asset.id for asset in value]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("silhouette asset IDs must be unique")
        return value

    def get(self, asset_id: str) -> SilhouetteAsset:
        for asset in self.assets:
            if asset.id == asset_id:
                return asset
        available = ", ".join(sorted(asset.id for asset in self.assets))
        raise KeyError(f"unknown silhouette asset '{asset_id}'; available: {available}")


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
