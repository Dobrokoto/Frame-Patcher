---
name: frame-patcher
description: Repair a known local defect in a PNG, JPEG, or WebP still by editing a contextual crop and compositing it through an exact mask while preserving the rest of the source. Use for a user-identified broken object, hand, face detail, sign, seam, residue, or occluder. Do not use for exhaustive defect discovery, broad redesign, or whole-frame restyling.
---

# Frame Patcher

**Version:** 1.1

Repair the requested zone without regenerating the full frame. Pixel protection and visual correctness are separate acceptance gates: passing `verify` never proves that the repaired object looks correct.

## Preflight

Classify the edit before preparing a patch:

- **Repair:** the correct structure is visible or continues clearly from nearby pixels.
- **Inferred repair:** structure can be inferred from symmetry, a reference, or an unambiguous relationship.
- **Reconstruction:** the request removes an occluder or invents fully hidden anatomy, clothing, text, or object geometry. Record the uncertain regions and do not imply exact recovery.
- **Redesign:** the composition or a large connected structure must change. Stop using this skill and propose an appropriate broader edit.

For inferred repair or reconstruction, read [references/visual-acceptance.md](references/visual-acceptance.md).

Before editing, define a short task contract:

- `target`: what changes;
- `must_be_true`: 3–7 visible facts required for acceptance;
- `protected`: nearby identity, geometry, text, or objects that must remain;
- `dependencies`: objects whose relationship must stay coherent;
- `uncertain`: hidden structure that cannot be recovered from source pixels.

## Workflow

1. Inspect the full source once. Accept defect locations from the user's description, marked frame, or supplied detail crop. Do not tile the whole image or claim a full audit.
2. Work only in source-native coordinates. If a bbox came from a scaled preview, convert it and inspect the native overlay before editing.
3. Prepare one patch pack per independent defect. Use a tight bbox only for simple interior regions. Use an exact source-sized mask or polygon whenever the edit touches a silhouette, frame, text, anatomy, thin object, or several materials.

```bash
python3 <skill-dir>/scripts/patch_tools.py prepare SOURCE PATCH_DIR \
  --bbox x,y,width,height --request "repair description"

python3 <skill-dir>/scripts/patch_tools.py prepare SOURCE PATCH_DIR \
  --mask SOURCE_SIZED_MASK.png --request "repair description" \
  --risk reconstruction --invariant "natural continuous silhouette"
```

If the user supplied an unmarked detail crop, locate it first:

```bash
python3 <skill-dir>/scripts/patch_tools.py locate SOURCE DETAIL locate.json
```

Use the returned bbox only at confidence `>= 0.65`; otherwise ask for a mark or identify the native coordinates manually.

4. Inspect `guide.png`, `mask-overlay-native.png`, and `crop-mask-overlay.png`. The edit mask must remain inside the context crop. Add context rather than enlarging the edit mask.
5. Send **only** `crop-work.png` to the image editor. When multiple image references are supported, also send `mask-hard-work.png` and state: white may change, black must remain unchanged. Include the task contract in the prompt. Never send the full frame.
6. Inspect every edited crop before compositing. Reject it for shifted protected geometry, remaining defect fragments, new objects or anatomy, broken topology, text corruption, halos, double contours, technical bars, or incorrect aspect ratio.
7. Composite into the immutable source:

```bash
python3 <skill-dir>/scripts/patch_tools.py compose \
  PATCH_DIR/manifest.json EDITED_CROP OUTPUT.png
```

Use `--grain` only when visible source grain makes the patch unnaturally smooth. Avoid it for text, thin lines, and fragile geometry.

8. Run verification:

```bash
python3 <skill-dir>/scripts/patch_tools.py verify \
  PATCH_DIR/manifest.json OUTPUT.png VERIFY_DIR
```

Require `technical_pass: true`, then inspect `qa-contact-sheet.png` and `boundary-overlay.png` at 200%, the repaired object at 100%, and the full frame fit-to-screen. Accept only if every `must_be_true` item passes and no protected area is damaged.
9. Build later patches only from the latest visually accepted composite. Retain the original source and intermediate manifests.

## Strategy and stopping rules

- Separate independent defects. Group adjacent defects when they are topologically dependent, paired, or part of one continuous surface.
- Default to adaptive feathering. Use `--edge hard` for silhouettes, glass, text, and mechanical lines; use `--edge soft` for smoke, fur, or genuinely soft transitions. Never use feathering to hide incorrect geometry.
- Allow at most two generation attempts and two composite adjustments with the same strategy. After that, change strategy, request a reference, disclose the unresolved uncertainty, or stop.
- Warn before continuing when reconstruction spans several unrelated structures or the editable region becomes broad enough to undermine local control.

## Deliver

Return the source-resolution image and report:

- patched zones;
- technical pixel-protection result;
- visual acceptance result;
- any uncertain or unresolved reconstruction.

Do not call the patch successful, clean, or exact when only technical verification passed.

## Credits

Created by Alexander Dobrokotov / AI Molodca.
https://aimolodca.com · https://t.me/strangedalle
