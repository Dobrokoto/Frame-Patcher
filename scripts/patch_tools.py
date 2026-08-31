#!/usr/bin/env python3
"""Deterministic local crop, mask, composite, locate, and verification tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


RESAMPLE = Image.Resampling.LANCZOS


def fail(message: str) -> None:
    raise SystemExit(message)


def save_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_bbox(value: str) -> tuple[int, int, int, int]:
    try:
        parts = [int(round(float(item.strip()))) for item in value.split(",")]
    except ValueError as exc:
        fail(f"Invalid bbox: {value} ({exc})")
    if len(parts) != 4 or parts[2] <= 0 or parts[3] <= 0:
        fail("bbox must be x,y,width,height with positive width and height")
    return tuple(parts)  # type: ignore[return-value]


def clamp_bbox(bbox: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x, y, w, h = bbox
    x0 = max(0, min(width - 1, x))
    y0 = max(0, min(height - 1, y))
    x1 = max(x0 + 1, min(width, x + w))
    y1 = max(y0 + 1, min(height, y + h))
    return x0, y0, x1 - x0, y1 - y0


def expand_bbox(
    bbox: tuple[int, int, int, int], width: int, height: int, factor: float, min_padding: int
) -> tuple[int, int, int, int]:
    x, y, w, h = bbox
    target_w = max(w + 2 * min_padding, int(round(w * factor)))
    target_h = max(h + 2 * min_padding, int(round(h * factor)))
    target_w = min(width, target_w)
    target_h = min(height, target_h)
    cx, cy = x + w / 2, y + h / 2
    x0 = int(round(cx - target_w / 2))
    y0 = int(round(cy - target_h / 2))
    x0 = max(0, min(width - target_w, x0))
    y0 = max(0, min(height - target_h, y0))
    return x0, y0, target_w, target_h


def require_rgb(image: Image.Image, label: str) -> None:
    if image.mode not in {"RGB", "RGBA"}:
        fail(f"{label} must be 8-bit RGB or RGBA; found mode {image.mode}")


def make_default_mask(
    size: tuple[int, int], local_bbox: tuple[int, int, int, int], shape: str
) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    x, y, w, h = local_bbox
    box = (x, y, x + w - 1, y + h - 1)
    if shape == "ellipse":
        draw.ellipse(box, fill=255)
    else:
        radius = max(2, min(w, h) // 6)
        draw.rounded_rectangle(box, radius=radius, fill=255)
    return mask


def make_polygon_mask(path: Path, size: tuple[int, int]) -> Image.Image:
    data = json.loads(path.read_text(encoding="utf-8"))
    points = data.get("points") if isinstance(data, dict) else data
    if not isinstance(points, list) or len(points) < 3:
        fail("Polygon JSON must contain at least three source-native [x, y] points")
    parsed: list[tuple[int, int]] = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            fail("Each polygon point must be [x, y]")
        try:
            x, y = int(round(float(point[0]))), int(round(float(point[1])))
        except (TypeError, ValueError) as exc:
            fail(f"Invalid polygon point {point}: {exc}")
        if not (0 <= x < size[0] and 0 <= y < size[1]):
            fail(f"Polygon point {(x, y)} is outside source size {size}")
        parsed.append((x, y))
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon(parsed, fill=255)
    return mask


def choose_feather(
    explicit: float | None, edge: str, target_bbox: tuple[int, int, int, int]
) -> tuple[float, list[str]]:
    short_side = max(1, min(target_bbox[2], target_bbox[3]))
    if explicit is None:
        if edge == "hard":
            feather = 1.0
        elif edge == "soft":
            feather = float(min(8, max(2, round(short_side * 0.03))))
        else:
            feather = float(min(3, max(1, round(short_side * 0.02))))
    else:
        feather = max(0.0, float(explicit))
    warnings: list[str] = []
    if feather > short_side * 0.05:
        warnings.append(
            f"Feather {feather:g}px exceeds 5% of target short side ({short_side}px); inspect for halos"
        )
    return feather, warnings


def mask_overlay(image: Image.Image, mask: Image.Image, color: tuple[int, int, int], alpha: int) -> Image.Image:
    base = image.convert("RGBA")
    tint = Image.new("RGBA", image.size, (*color, 0))
    tint.putalpha(mask.point(lambda p: alpha if p >= 128 else 0))
    return Image.alpha_composite(base, tint)


def fit_image(image: Image.Image, size: tuple[int, int], force: bool = False) -> Image.Image:
    target_ratio = size[0] / size[1]
    source_ratio = image.width / image.height
    ratio_error = abs(source_ratio / target_ratio - 1.0)
    if ratio_error > 0.05 and not force:
        fail(
            f"Edited crop aspect ratio differs by {ratio_error:.1%}; reject it or rerun compose with --force-resize"
        )
    return image.resize(size, RESAMPLE)


def command_prepare(args: argparse.Namespace) -> None:
    source_path = Path(args.source).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not source_path.is_file():
        fail(f"Source not found: {source_path}")
    output_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(source_path) as opened:
        source = opened.copy()
    require_rgb(source, "Source")
    width, height = source.size

    source_copy = output_dir / f"source-original{source_path.suffix.lower()}"
    shutil.copy2(source_path, source_copy)

    full_mask: Image.Image | None = None
    mask_source = "bbox"
    if args.mask:
        with Image.open(args.mask) as opened:
            full_mask = opened.convert("L")
        if full_mask.size != source.size:
            fail("Source-sized mask dimensions do not match the source")
        binary = full_mask.point(lambda p: 255 if p >= 128 else 0)
        mask_box = binary.getbbox()
        if not mask_box:
            fail("Mask contains no selected pixels")
        target_bbox = (mask_box[0], mask_box[1], mask_box[2] - mask_box[0], mask_box[3] - mask_box[1])
        full_mask = binary
        mask_source = "source-sized-mask"
    elif args.polygon:
        full_mask = make_polygon_mask(Path(args.polygon).resolve(), source.size)
        mask_box = full_mask.getbbox()
        if not mask_box:
            fail("Polygon contains no selected pixels")
        target_bbox = (mask_box[0], mask_box[1], mask_box[2] - mask_box[0], mask_box[3] - mask_box[1])
        mask_source = "source-native-polygon"
    elif args.bbox:
        target_bbox = parse_bbox(args.bbox)
    else:
        fail("prepare requires --bbox, --mask, or --polygon")

    target_bbox = clamp_bbox(target_bbox, width, height)
    context_bbox = expand_bbox(target_bbox, width, height, args.context, args.min_padding)
    cx, cy, cw, ch = context_bbox
    tx, ty, tw, th = target_bbox
    local_bbox = (tx - cx, ty - cy, tw, th)

    crop_native = source.crop((cx, cy, cx + cw, cy + ch))
    if full_mask is None:
        hard_native = make_default_mask((cw, ch), local_bbox, args.shape)
    else:
        hard_native = full_mask.crop((cx, cy, cx + cw, cy + ch)).point(lambda p: 255 if p >= 128 else 0)
    feather, warnings = choose_feather(args.feather, args.edge, target_bbox)
    soft_native = hard_native.filter(ImageFilter.GaussianBlur(radius=feather)) if feather else hard_native.copy()

    scale = min(4.0, max(0.25, args.work_size / max(cw, ch)))
    work_size = (max(1, int(round(cw * scale))), max(1, int(round(ch * scale))))
    crop_work = crop_native.resize(work_size, RESAMPLE)
    hard_work = hard_native.resize(work_size, Image.Resampling.NEAREST)
    soft_work = soft_native.resize(work_size, RESAMPLE)

    crop_native_path = output_dir / "crop-native.png"
    crop_work_path = output_dir / "crop-work.png"
    hard_native_path = output_dir / "mask-hard-native.png"
    soft_native_path = output_dir / "mask-soft-native.png"
    hard_work_path = output_dir / "mask-hard-work.png"
    soft_work_path = output_dir / "mask-soft-work.png"
    crop_native.save(crop_native_path)
    crop_work.save(crop_work_path)
    hard_native.save(hard_native_path)
    soft_native.save(soft_native_path)
    hard_work.save(hard_work_path)
    soft_work.save(soft_work_path)

    full_hard = Image.new("L", source.size, 0)
    full_hard.paste(hard_native, (cx, cy))
    mask_overlay(source, full_hard, (255, 30, 30), 92).save(output_dir / "mask-overlay-native.png")
    mask_overlay(crop_work, hard_work, (255, 30, 30), 92).save(output_dir / "crop-mask-overlay.png")

    guide = source.convert("RGBA")
    overlay = Image.new("RGBA", source.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((cx, cy, cx + cw - 1, cy + ch - 1), outline=(255, 210, 0, 255), width=max(2, width // 500))
    draw.rectangle((tx, ty, tx + tw - 1, ty + th - 1), fill=(255, 40, 40, 60), outline=(255, 40, 40, 255), width=max(2, width // 400))
    guide = Image.alpha_composite(guide, overlay)
    guide.save(output_dir / "guide.png")

    request = (args.request or "repair the indicated defect").strip()
    invariants = [item.strip() for item in (args.invariant or []) if item.strip()]
    protected = [item.strip() for item in (args.protected or []) if item.strip()]
    uncertain = [item.strip() for item in (args.uncertain or []) if item.strip()]
    if args.risk == "reconstruction" and mask_source == "bbox":
        warnings.append(
            "Reconstruction uses a generated bbox mask; prefer --mask or --polygon for silhouettes and multi-material edges"
        )
    if args.risk == "reconstruction" and not uncertain:
        warnings.append("Reconstruction has no declared uncertain region; do not imply exact recovery")
    contract_lines = []
    if invariants:
        contract_lines.append("Must be true: " + "; ".join(invariants) + ".")
    if protected:
        contract_lines.append("Protect: " + "; ".join(protected) + ".")
    if uncertain:
        contract_lines.append("Uncertain hidden structure: " + "; ".join(uncertain) + ".")
    prompt = (
        "Use case: precise-object-edit\n"
        "Inputs: first image is a context crop; second image, when provided, is the exact edit mask "
        "where white may change and black must remain unchanged.\n"
        f"Primary request: {request}.\n"
        f"Risk class: {args.risk}.\n"
        + ("\n".join(contract_lines) + "\n" if contract_lines else "")
        + "Change only the indicated central defect. Preserve crop framing, camera, identity, geometry, "
        "lighting, color, perspective, texture and all surrounding context. Return the same composition "
        "and aspect ratio. Do not beautify, reframe, add objects, or modify unrelated pixels."
    )
    (output_dir / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")

    manifest = {
        "schema_version": 2,
        "source": str(source_copy),
        "source_sha256": sha256(source_copy),
        "source_size": [width, height],
        "source_mode": source.mode,
        "coordinate_space": "source_native",
        "mask_source": mask_source,
        "target_bbox": list(target_bbox),
        "context_bbox": list(context_bbox),
        "local_bbox": list(local_bbox),
        "work_size": list(work_size),
        "work_scale": scale,
        "feather": feather,
        "edge": args.edge,
        "risk": args.risk,
        "request": request,
        "invariants": invariants,
        "protected": protected,
        "uncertain": uncertain,
        "warnings": warnings,
        "paths": {
            "crop_native": str(crop_native_path),
            "crop_work": str(crop_work_path),
            "mask_hard_native": str(hard_native_path),
            "mask_soft_native": str(soft_native_path),
            "mask_hard_work": str(hard_work_path),
            "mask_soft_work": str(soft_work_path),
            "guide": str(output_dir / "guide.png"),
            "mask_overlay_native": str(output_dir / "mask-overlay-native.png"),
            "crop_mask_overlay": str(output_dir / "crop-mask-overlay.png"),
            "prompt": str(output_dir / "prompt.txt"),
        },
    }
    save_json(output_dir / "manifest.json", manifest)
    print(
        json.dumps(
            {
                "target_bbox": target_bbox,
                "context_bbox": context_bbox,
                "work_size": work_size,
                "coordinate_space": "source_native",
                "risk": args.risk,
                "feather": feather,
                "warnings": warnings,
            },
            indent=2,
        )
    )


def ring_from_mask(mask: Image.Image, radius: int = 12) -> np.ndarray:
    size = max(3, radius * 2 + 1)
    if size % 2 == 0:
        size += 1
    size = min(size, 51)
    dilated = mask.filter(ImageFilter.MaxFilter(size=size))
    hard = np.asarray(mask, dtype=np.uint8) >= 128
    return (np.asarray(dilated, dtype=np.uint8) > 0) & (~hard)


def color_match_patch(patch: np.ndarray, original: np.ndarray, ring: np.ndarray, strength: float) -> np.ndarray:
    if strength <= 0 or ring.sum() < 32:
        return patch
    result = patch.astype(np.float32).copy()
    channels = min(3, result.shape[2])
    for channel in range(channels):
        src_values = original[..., channel][ring].astype(np.float32)
        edit_values = result[..., channel][ring]
        src_mean, src_std = float(src_values.mean()), float(src_values.std())
        edit_mean, edit_std = float(edit_values.mean()), float(edit_values.std())
        if edit_std < 1.0:
            continue
        matched = (result[..., channel] - edit_mean) * (src_std / edit_std) + src_mean
        result[..., channel] = result[..., channel] * (1.0 - strength) + matched * strength
    return np.clip(result, 0, 255)


def command_compose(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest).resolve()
    manifest = read_json(manifest_path)
    source_path = Path(manifest["source"])
    if sha256(source_path) != manifest["source_sha256"]:
        fail("Immutable source copy hash changed")
    with Image.open(source_path) as opened:
        source = opened.copy()
    require_rgb(source, "Source")
    with Image.open(args.edited_crop) as opened:
        edited = opened.convert(source.mode)
    cx, cy, cw, ch = [int(v) for v in manifest["context_bbox"]]
    edited_native = fit_image(edited, (cw, ch), force=args.force_resize)
    edited_native.save(manifest_path.parent / "edited-native.png")
    original_crop = source.crop((cx, cy, cx + cw, cy + ch))
    hard_mask = Image.open(manifest["paths"]["mask_hard_native"]).convert("L")
    soft_mask = Image.open(manifest["paths"]["mask_soft_native"]).convert("L")

    original_array = np.asarray(original_crop, dtype=np.uint8)
    patch_array = np.asarray(edited_native, dtype=np.uint8)
    ring = ring_from_mask(hard_mask)
    patch_float = color_match_patch(patch_array, original_array, ring, float(args.color_match))

    grain = max(0.0, min(1.0, float(args.grain)))
    if grain > 0:
        blurred = np.asarray(original_crop.filter(ImageFilter.GaussianBlur(radius=1.0)), dtype=np.float32)
        residual = original_array.astype(np.float32) - blurred
        channels = min(3, patch_float.shape[2])
        patch_float[..., :channels] += residual[..., :channels] * grain
        patch_float = np.clip(patch_float, 0, 255)

    alpha = np.asarray(soft_mask, dtype=np.float32) / 255.0
    if patch_float.ndim == 3:
        alpha = alpha[..., None]
    final_crop = original_array.copy()
    active = np.asarray(soft_mask, dtype=np.uint8) > 0
    blended = np.rint(original_array.astype(np.float32) * (1.0 - alpha) + patch_float * alpha).astype(np.uint8)
    final_crop[active] = blended[active]

    output_array = np.asarray(source, dtype=np.uint8).copy()
    output_array[cy : cy + ch, cx : cx + cw] = final_crop
    output = Image.fromarray(output_array, mode=source.mode)
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.save(output_path)

    review = Image.new(source.mode, (cw * 2, ch))
    review.paste(original_crop, (0, 0))
    review.paste(Image.fromarray(final_crop, mode=source.mode), (cw, 0))
    review.save(manifest_path.parent / "before-after.png")
    print(json.dumps({"output": str(output_path), "source_size": source.size, "context_bbox": [cx, cy, cw, ch]}, indent=2))


def command_verify(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest).resolve()
    manifest = read_json(manifest_path)
    source = Image.open(manifest["source"]).copy()
    output = Image.open(args.output).convert(source.mode)
    if output.size != source.size:
        fail(f"Output size {output.size} differs from source {source.size}")
    source_array = np.asarray(source, dtype=np.int16)
    output_array = np.asarray(output, dtype=np.int16)
    diff = np.abs(output_array - source_array)
    pixel_diff = diff.max(axis=2) if diff.ndim == 3 else diff

    cx, cy, cw, ch = [int(v) for v in manifest["context_bbox"]]
    hard_image = Image.open(manifest["paths"]["mask_hard_native"]).convert("L")
    soft_image = Image.open(manifest["paths"]["mask_soft_native"]).convert("L")
    hard = np.asarray(hard_image, dtype=np.uint8)
    soft = np.asarray(soft_image, dtype=np.uint8)
    full_hard = np.zeros((source.height, source.width), dtype=np.uint8)
    full_soft = np.zeros((source.height, source.width), dtype=np.uint8)
    full_hard[cy : cy + ch, cx : cx + cw] = hard
    full_soft[cy : cy + ch, cx : cx + cw] = soft
    outside_hard = full_hard == 0
    outside_soft = full_soft == 0
    feather_ring = (full_soft > 0) & (full_hard < 128)
    inside_hard = full_hard >= 128
    changed_outside_soft = int(np.count_nonzero(pixel_diff[outside_soft]))
    changed_outside_hard = int(np.count_nonzero(pixel_diff[outside_hard]))
    changed_feather_ring = int(np.count_nonzero(pixel_diff[feather_ring]))
    changed_inside_hard = int(np.count_nonzero(pixel_diff[inside_hard]))
    max_outside_soft = int(pixel_diff[outside_soft].max()) if outside_soft.any() else 0

    verify_dir = Path(args.verify_dir).resolve()
    verify_dir.mkdir(parents=True, exist_ok=True)
    heat = np.clip(pixel_diff.astype(np.float32) * 6.0, 0, 255).astype(np.uint8)
    heat_image = Image.fromarray(heat, mode="L")
    heat_image.save(verify_dir / "heatmap.png")

    source_crop = source.crop((cx, cy, cx + cw, cy + ch)).convert("RGB")
    output_crop = output.crop((cx, cy, cx + cw, cy + ch)).convert("RGB")
    boundary_outer = hard_image.filter(ImageFilter.MaxFilter(size=5))
    boundary_inner = hard_image.filter(ImageFilter.MinFilter(size=5))
    boundary_array = np.asarray(boundary_outer, dtype=np.int16) - np.asarray(boundary_inner, dtype=np.int16)
    boundary_mask = Image.fromarray(np.where(boundary_array > 0, 255, 0).astype(np.uint8), mode="L")
    mask_overlay(output_crop, boundary_mask, (255, 0, 255), 210).save(verify_dir / "boundary-overlay.png")

    panel_scale = min(1.0, 768.0 / max(cw, ch))
    panel_size = (max(1, int(round(cw * panel_scale))), max(1, int(round(ch * panel_scale))))
    label_height = 28

    def labeled_panel(image: Image.Image, label: str) -> Image.Image:
        panel = Image.new("RGB", (panel_size[0], panel_size[1] + label_height), (24, 24, 24))
        panel.paste(image.convert("RGB").resize(panel_size, RESAMPLE), (0, label_height))
        ImageDraw.Draw(panel).text((8, 7), label, fill=(245, 245, 245))
        return panel

    heat_crop = heat_image.crop((cx, cy, cx + cw, cy + ch))
    zero = Image.new("L", heat_crop.size, 0)
    heat_rgb = Image.merge("RGB", (heat_crop, zero, zero))
    exact_mask_panel = mask_overlay(output_crop, hard_image, (255, 30, 30), 110)
    panels = [
        labeled_panel(source_crop, "SOURCE"),
        labeled_panel(output_crop, "OUTPUT"),
        labeled_panel(heat_rgb, "PIXEL DIFF"),
        labeled_panel(exact_mask_panel, "HARD MASK"),
    ]
    contact = Image.new("RGB", (panels[0].width * 2, panels[0].height * 2), (18, 18, 18))
    contact.paste(panels[0], (0, 0))
    contact.paste(panels[1], (panels[0].width, 0))
    contact.paste(panels[2], (0, panels[0].height))
    contact.paste(panels[3], (panels[0].width, panels[0].height))
    contact.save(verify_dir / "qa-contact-sheet.png")

    visual_review = {
        "status": "pending",
        "required_scales": ["200% boundary", "100% object", "fit-to-screen full frame"],
        "must_be_true": manifest.get("invariants", []),
        "protected": manifest.get("protected", []),
        "uncertain": manifest.get("uncertain", []),
        "reject_if": [
            "old defect remains",
            "protected geometry shifted",
            "new object or anatomy error",
            "broken topology, text, perspective, or material",
            "halo, seam, or double contour",
        ],
    }
    save_json(verify_dir / "visual-review.json", visual_review)

    technical_pass = changed_outside_soft == 0
    result = {
        "pass": technical_pass,
        "technical_pass": technical_pass,
        "visual_acceptance": "pending",
        "changed_pixels_outside_soft_mask": changed_outside_soft,
        "max_channel_difference_outside_soft_mask": max_outside_soft,
        "changed_pixels_outside_hard_mask": changed_outside_hard,
        "changed_pixels_in_feather_ring": changed_feather_ring,
        "changed_pixels_inside_hard_mask": changed_inside_hard,
        "source_size": list(source.size),
    }
    save_json(verify_dir / "verification.json", result)
    print(json.dumps(result, indent=2))
    if changed_outside_soft:
        raise SystemExit(2)


def gradient(image: Image.Image) -> np.ndarray:
    gray = np.asarray(image.convert("L"), dtype=np.float32) / 255.0
    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)
    gx[:, 1:-1] = gray[:, 2:] - gray[:, :-2]
    gy[1:-1, :] = gray[2:, :] - gray[:-2, :]
    magnitude = np.sqrt(gx * gx + gy * gy)
    std = float(magnitude.std())
    return (magnitude - magnitude.mean()) / max(std, 1e-6)


def ncc_best(source: np.ndarray, template: np.ndarray) -> tuple[float, int, int]:
    try:
        from scipy.signal import fftconvolve
    except ImportError:
        fail("The locate command requires scipy; use a marked source image or provide --bbox instead")
    th, tw = template.shape
    sh, sw = source.shape
    if th > sh or tw > sw or min(th, tw) < 8:
        return -1.0, 0, 0
    template_zero = template - template.mean()
    template_energy = float(np.sum(template_zero * template_zero))
    if template_energy < 1e-8:
        return -1.0, 0, 0
    reversed_template = template_zero[::-1, ::-1]
    numerator = fftconvolve(source, reversed_template, mode="valid")
    kernel = np.ones((th, tw), dtype=np.float32)
    sums = fftconvolve(source, kernel, mode="valid")
    sums_sq = fftconvolve(source * source, kernel, mode="valid")
    count = float(th * tw)
    variance = np.maximum(sums_sq - (sums * sums) / count, 1e-8)
    scores = numerator / np.sqrt(variance * template_energy)
    index = int(np.nanargmax(scores))
    y, x = np.unravel_index(index, scores.shape)
    return float(scores[y, x]), int(x), int(y)


def command_locate(args: argparse.Namespace) -> None:
    source_image = Image.open(args.source).convert("RGB")
    detail_image = Image.open(args.detail).convert("RGB")
    source_grad = gradient(source_image)
    base_scales = [float(item) for item in args.scales.split(",") if item.strip()]

    def search(scales: list[float], best: tuple[float, int, int, int, int, float] | None = None):
        current = best
        for scale in scales:
            width = max(8, int(round(detail_image.width * scale)))
            height = max(8, int(round(detail_image.height * scale)))
            if width > source_image.width or height > source_image.height:
                continue
            candidate = detail_image.resize((width, height), RESAMPLE)
            score, x, y = ncc_best(source_grad, gradient(candidate))
            record = (score, x, y, width, height, scale)
            if current is None or score > current[0]:
                current = record
        return current

    best = search(base_scales)
    if best is None:
        fail("No viable scale fits inside the source")
    refine = sorted({best[5] * factor for factor in (0.82, 0.88, 0.94, 0.97, 1.03, 1.06, 1.12, 1.18)})
    best = search(refine, best)
    score, x, y, width, height, scale = best
    result = {"bbox": [x, y, width, height], "confidence": round(score, 4), "matched_scale": round(scale, 4)}
    save_json(Path(args.output_json).resolve(), result)
    print(json.dumps(result, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local image patch preparation and pixel-safe compositing")
    commands = parser.add_subparsers(dest="command", required=True)

    locate = commands.add_parser("locate", help="Locate an enlarged or resized detail crop in a source image")
    locate.add_argument("source")
    locate.add_argument("detail")
    locate.add_argument("output_json")
    locate.add_argument("--scales", default="0.2,0.25,0.333,0.4,0.5,0.667,0.75,1.0,1.25,1.5,2.0")
    locate.set_defaults(func=command_locate)

    prepare = commands.add_parser("prepare", help="Create a contextual crop and local masks")
    prepare.add_argument("source")
    prepare.add_argument("output_dir")
    region = prepare.add_mutually_exclusive_group(required=True)
    region.add_argument("--bbox", help="x,y,width,height in source-native pixels")
    region.add_argument("--mask", help="Source-sized grayscale mask")
    region.add_argument("--polygon", help="JSON file with source-native polygon points")
    prepare.add_argument("--request", default="repair the indicated defect")
    prepare.add_argument("--context", type=float, default=2.5)
    prepare.add_argument("--min-padding", type=int, default=48)
    prepare.add_argument("--work-size", type=int, default=1024)
    prepare.add_argument("--feather", type=float, default=None, help="Explicit feather radius; default is adaptive")
    prepare.add_argument("--edge", choices=["auto", "hard", "soft"], default="auto")
    prepare.add_argument("--shape", choices=["rect", "ellipse"], default="rect")
    prepare.add_argument(
        "--risk", choices=["repair", "inferred", "reconstruction"], default="repair"
    )
    prepare.add_argument("--invariant", action="append", help="Visible fact required for acceptance")
    prepare.add_argument("--protected", action="append", help="Nearby structure that must remain unchanged")
    prepare.add_argument("--uncertain", action="append", help="Hidden structure not recoverable from source pixels")
    prepare.set_defaults(func=command_prepare)

    compose = commands.add_parser("compose", help="Composite one edited crop through the local mask")
    compose.add_argument("manifest")
    compose.add_argument("edited_crop")
    compose.add_argument("output")
    compose.add_argument("--color-match", type=float, default=0.85)
    compose.add_argument("--grain", type=float, default=0.0)
    compose.add_argument("--force-resize", action="store_true")
    compose.set_defaults(func=command_compose)

    verify = commands.add_parser("verify", help="Verify no pixels changed outside the feathered mask")
    verify.add_argument("manifest")
    verify.add_argument("output")
    verify.add_argument("verify_dir")
    verify.set_defaults(func=command_verify)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
