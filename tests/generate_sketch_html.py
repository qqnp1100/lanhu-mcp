"""Generate HTML from a Lanhu Sketch JSON file using project converter logic."""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import lanhu_mcp_server as lanhu  # noqa: E402


DEFAULT_JSON = Path(__file__).with_name(
    "test.json"
)


def _opacity_of(layer: dict) -> float:
    return layer.get("opacity", 100) if layer.get("opacity") is not None else 100


def _first_fill(layer: dict) -> dict:
    for fill in layer.get("fills") or []:
        if fill.get("isEnabled", True) and fill.get("color"):
            return {"color": fill.get("color")}
    return {}


def _image_url(layer: dict) -> str:
    image = layer.get("ddsImage") or layer.get("image") or {}
    return image.get("imageUrl") or image.get("svgUrl") or ""


def _text_info(layer: dict) -> dict:
    font = layer.get("font") or {}
    styles = font.get("styles") or []
    style = styles[0] if styles else {}
    content = font.get("content") or "".join(str(s.get("content", "")) for s in styles) or layer.get("name", "")
    align = font.get("align") or {0: "left", 1: "right", 2: "center"}.get(font.get("textAlignment"), "left")

    return {
        "text": content,
        "color": font.get("color") or style.get("color"),
        "size": font.get("size") or style.get("size") or layer.get("height"),
        "fontPostScriptName": font.get("font") or style.get("font") or font.get("displayName"),
        "fontStyleName": str(style.get("fontWeight") or ""),
        "justification": align,
    }


def _adapt_layer(layer: dict) -> dict:
    frame = layer.get("layerOriginFrame") or layer.get("ddsOriginFrame") or {}
    old_type = layer.get("type") or layer.get("ddsType") or ""
    mapped_type = {
        "text": "textLayer",
        "bitmap": "bitmap",
        "shape": "shape",
        "layer-group": "layerSection",
    }.get(old_type, old_type)

    adapted = {
        "name": layer.get("name", ""),
        "type": mapped_type,
        "left": layer.get("left", frame.get("x", 0)) or 0,
        "top": layer.get("top", frame.get("y", 0)) or 0,
        "width": layer.get("width", frame.get("width", 0)) or 0,
        "height": layer.get("height", frame.get("height", 0)) or 0,
        "visible": layer.get("isVisible", True),
        "blendOptions": {"opacity": {"value": _opacity_of(layer)}},
    }

    if old_type == "text":
        adapted["textInfo"] = _text_info(layer)
    else:
        url = _image_url(layer)
        if url:
            adapted["images"] = {"png_xxxhd": url}
        fill = _first_fill(layer)
        if fill:
            adapted["fill"] = fill

    return adapted


def _design_scale(sketch: dict) -> float:
    device = sketch.get("device", "")
    if "@3x" in device:
        return 3.0
    if "@1x" in device:
        return 1.0
    return 2.0


def _build_board(sketch: dict) -> tuple[dict, int]:
    info = sketch.get("info") or []
    children_by_parent = defaultdict(list)
    for layer in info:
        if layer.get("parentID"):
            children_by_parent[layer["parentID"]].append(layer)

    artboard = next(
        (
            layer
            for layer in info
            if layer.get("ddsType") == "artboard-group" or layer.get("id") == sketch.get("ArtboardID")
        ),
        info[0] if info else {},
    )

    layers = []
    for layer in info:
        old_type = layer.get("type") or layer.get("ddsType") or ""
        if old_type == "artboard-group" or layer.get("isVisible") is False:
            continue
        if old_type == "layer-group" and children_by_parent.get(layer.get("id")):
            continue
        if old_type in {"text", "bitmap", "shape", "layer-group"}:
            layers.append(_adapt_layer(layer))

    # convert_sketch_to_html reverses board.layers internally, so reverse here to
    # preserve the original back-to-front order from the Lanhu info array.
    return {
        "width": artboard.get("width", 375),
        "height": artboard.get("height", 812),
        "layers": list(reversed(layers)),
    }, len(layers)


def generate_html(json_path: Path, output_path: Path | None = None) -> Path:
    sketch = json.loads(json_path.read_text(encoding="utf-8"))
    board, layer_count = _build_board(sketch)
    html, image_mapping, annotations = lanhu.convert_sketch_to_html({"board": board}, _design_scale(sketch), "")

    out = output_path or json_path.with_suffix(".html")
    out.write_text(html, encoding="utf-8")
    print(out)
    print(f"layers={layer_count} images={len(image_mapping)} annotations={len(annotations)} size={out.stat().st_size}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", nargs="?", type=Path, default=DEFAULT_JSON)
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    generate_html(args.json_path, args.output)


if __name__ == "__main__":
    main()
