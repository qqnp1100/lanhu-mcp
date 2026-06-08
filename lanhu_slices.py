#!/usr/bin/env python3
"""
Extract the same slice list rendered by Lanhu's
`.slice-list.scroll_bar_beautify_ff` container from a design json_url.

Usage:
  python extract_lanhu_slices.py "https://.../design.json" --active-file-type PNG
  python extract_lanhu_slices.py design.json --active-file-type SVG
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


VISIBLE_RASTER_TYPES = {"PNG", "JPG", "WEBP"}
VISIBLE_VECTOR_TYPES = {"SVG", "PDF"}


def load_json(source: str, timeout: int, headers: List[str]) -> Any:
    if source.startswith(("http://", "https://")):
        request_headers = {
            "User-Agent": "Mozilla/5.0 LanhuSliceExtractor/1.0",
            "Accept": "application/json,text/plain,*/*",
        }

        token = os.environ.get("LANHU_TOKEN")
        if token:
            encoded = base64.b64encode(f"{token}:".encode("utf-8")).decode("ascii")
            request_headers["Authorization"] = f"Basic {encoded}"

        for header in headers:
            if ":" not in header:
                raise SystemExit(f"Invalid header {header!r}; expected 'Name: value'")
            name, value = header.split(":", 1)
            request_headers[name.strip()] = value.strip()

        req = urllib.request.Request(source, headers=request_headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        text = raw.decode("utf-8-sig")
    else:
        text = Path(source).read_text(encoding="utf-8-sig")

    return json.loads(text)


def first_value(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def nested_get(obj: Dict[str, Any], *path: str) -> Any:
    cur: Any = obj
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def layer_width(layer: Dict[str, Any]) -> Any:
    return first_value(
        layer.get("width"),
        nested_get(layer, "frame", "width"),
        nested_get(layer, "realFrame", "width"),
    )


def layer_height(layer: Dict[str, Any]) -> Any:
    return first_value(
        layer.get("height"),
        nested_get(layer, "frame", "height"),
        nested_get(layer, "realFrame", "height"),
    )


def build_slice_item(
    *,
    index: int,
    name: Any,
    url: Any,
    svg: Any,
    asset: Dict[str, Any],
    layer: Dict[str, Any],
    asset_key: str,
) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "index": index,
        "name": name or "",
        "url": url or "",
        "svg": svg or "",
        asset_key: asset,
        "width": layer_width(layer) or 0,
        "height": layer_height(layer) or 0,
        "web_id": first_value(layer.get("web_id"), layer.get("id"), layer.get("objectID")),
    }

    org_url = asset.get("orgUrl")
    if org_url:
        item["orgUrl"] = org_url

    if asset.get("isNew"):
        if asset.get("svgUrl"):
            item["svgUrl"] = asset.get("svgUrl")
        if asset.get("imageUrl"):
            item["imageUrl"] = asset.get("imageUrl")

    item["isSelected"] = True
    item["isNameEditing"] = False
    item["hasSvg"] = bool(item.get("svg") or item.get("svgUrl"))
    return item


def extract_ps_asset(layer: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
    images = layer.get("images")
    if not layer.get("isAsset") or not isinstance(images, dict):
        return None

    url = images.get("png_xxxhd")
    if not url:
        return None

    # Lanhu frontend ignores placeholder paths whose last two chars are "/0".
    if isinstance(url, str) and url[-2:] == "/0":
        return None

    return build_slice_item(
        index=index,
        name=layer.get("name"),
        url=url,
        svg=images.get("svg"),
        asset=images,
        layer=layer,
        asset_key="images",
    )


def extract_image_asset(layer: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
    image = layer.get("image")
    if not isinstance(image, dict):
        return None

    return build_slice_item(
        index=index,
        name=layer.get("name"),
        url=image.get("bitmap"),
        svg=image.get("svg") or "",
        asset=image,
        layer=layer,
        asset_key="image",
    )


def iter_dicts(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dicts(child)


def iter_layer_tree(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child_key in ("layers", "children"):
            children = value.get(child_key)
            if isinstance(children, list):
                for child in children:
                    yield from iter_layer_tree(child)


def frontend_layer_list(data: Any) -> List[Dict[str, Any]]:
    """Return the layer collection Lanhu uses before building sliceIndex.

    The page does not scan the whole JSON object. For the common Sketch/plugin
    JSON it starts from `info`; for artboard JSON it starts from
    `artboard.layers`.
    """
    if not isinstance(data, dict):
        return [item for item in iter_dicts(data)]

    artboard = data.get("artboard")
    if isinstance(artboard, dict) and isinstance(artboard.get("layers"), list):
        return [
            layer
            for child in artboard["layers"]
            for layer in iter_layer_tree(child)
        ]

    info = data.get("info")
    if isinstance(info, list):
        return [item for item in info if isinstance(item, dict)]

    return [item for item in iter_dicts(data)]


def looks_like_artboard_background(layer: Dict[str, Any], root_ids: Set[Any]) -> bool:
    name = str(layer.get("name") or "").strip().lower()
    if name not in {"背景", "background", "bg"}:
        return False
    return layer.get("parentID") in root_ids or layer.get("parentId") in root_ids


def dedupe_key(item: Dict[str, Any]) -> Tuple[Any, Any, Any]:
    return (item.get("web_id"), item.get("name"), item.get("url") or item.get("imageUrl"))


def extract_slice_index(
    data: Any,
    *,
    include_artboard_background: bool = True,
    dedupe: bool = False,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    seen: Set[Tuple[Any, Any, Any]] = set()
    root_ids: Set[Any] = set()
    if isinstance(data, dict):
        root_ids.update(
            value
            for value in (
                data.get("ArtboardID"),
                nested_get(data, "artboard", "id"),
                nested_get(data, "artboard", "objectID"),
            )
            if value
        )

    for index, layer in enumerate(frontend_layer_list(data)):
        if not include_artboard_background and looks_like_artboard_background(layer, root_ids):
            continue

        item = extract_ps_asset(layer, index) or extract_image_asset(layer, index)
        if not item:
            continue

        key = dedupe_key(item)
        if dedupe:
            if key in seen:
                continue
            seen.add(key)
        items.append(item)

    return items


def normalize_active_file_type(value: str) -> str:
    normalized = value.strip().upper()
    if normalized == "WEBP":
        return "WEBP"
    return normalized


def visible_in_slice_list(item: Dict[str, Any], active_file_type: str) -> bool:
    if active_file_type in VISIBLE_RASTER_TYPES:
        return True
    if active_file_type in VISIBLE_VECTOR_TYPES:
        return bool(item.get("hasSvg"))
    raise SystemExit(
        "--active-file-type must be one of PNG, JPG, WebP, SVG, or PDF"
    )


def slice_list_src(item: Dict[str, Any], enterprise: bool) -> str:
    # Mirrors the frontend preference order used by computed sliceListSrc.
    if enterprise:
        return (
            item.get("format_url")
            or item.get("format_base64")
            or item.get("imageUrl")
            or item.get("url")
            or item.get("orgUrl")
            or item.get("svg")
            or ""
        )
    return (
        item.get("format_url")
        or item.get("imageUrl")
        or item.get("url")
        or item.get("orgUrl")
        or item.get("format_base64")
        or item.get("svg")
        or ""
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Output Lanhu slice-list data from a version json_url."
    )
    parser.add_argument("source", help="Lanhu json_url or local JSON file path")
    parser.add_argument(
        "--active-file-type",
        default="PNG",
        help="Match Lanhu activeFileType filtering: PNG, JPG, WebP, SVG, or PDF",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Output all extracted slices and add _visible_in_slice_list.",
    )
    parser.add_argument(
        "--enterprise",
        action="store_true",
        help="Use enterprise slice thumbnail URL priority.",
    )
    parser.add_argument(
        "--include-artboard-background",
        action="store_true",
        help="Keep root artboard background slices. Lanhu's slice panel usually hides them.",
    )
    parser.add_argument(
        "--header",
        action="append",
        default=[],
        help="Extra HTTP header for json_url requests, for example 'Cookie: ...'.",
    )
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()

    active_file_type = normalize_active_file_type(args.active_file_type)
    data = load_json(args.source, timeout=args.timeout, headers=args.header)
    slice_index = extract_slice_index(
        data,
        include_artboard_background=args.include_artboard_background,
    )

    result: List[Dict[str, Any]] = []
    for item in slice_index:
        visible = visible_in_slice_list(item, active_file_type)
        if not visible and not args.include_hidden:
            continue

        output_item = dict(item)
        output_item["sliceListSrc"] = slice_list_src(output_item, args.enterprise)
        if args.include_hidden:
            output_item["_visible_in_slice_list"] = visible
        result.append(output_item)

    json.dump(
        result,
        sys.stdout,
        ensure_ascii=False,
        separators=(",", ":") if args.compact else None,
        indent=None if args.compact else 2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
