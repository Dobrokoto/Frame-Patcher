---
name: frame-patcher
description: Repair known local defects in PNG, JPEG, or WebP still frames by cropping only the indicated region, editing that crop, and compositing it back through a feathered mask while preserving every source pixel outside the mask. Use when the user already points out a broken hand, face detail, object, sign, shelf section, seam, noise patch, or other specific zone; when they provide enlarged defect crops or a marked image; or when repeated whole-frame image edits would degrade the frame. Do not use for exhaustive unknown-defect discovery; use frame-surgeon for a full audit.
---

# Frame Patcher

**Version:** 1.0

Patch only the known defect. Keep the source immutable and never send the full frame to the image editor.

## Fast workflow

1. Inspect the full image once. Accept defect locations from the user's description, marked frame, or supplied detail crops. Do not perform a semantic census or tile the whole image.
2. If the user supplied a detail crop, locate it in the source:

```bash
python3 <skill-dir>/scripts/patch_tools.py locate SOURCE DETAIL locate.json
```

Use the returned `bbox` only when confidence is at least `0.65`; otherwise ask the user to mark the source.

3. Prepare one patch pack per independent defect:

```bash
python3 <skill-dir>/scripts/patch_tools.py prepare SOURCE PATCH_DIR \
  --bbox x,y,width,height --request "repair description"
```

Use a tight defect bbox. The script adds context, creates native/work crops, hard and feathered masks, a guide, a manifest, and a concise editor prompt. For a long connected object, include enough length to establish direction and continuity. Merge nearby dependent defects into one patch; keep unrelated defects separate.

4. Inspect `guide.png` and `crop-work.png`. The defect mask must remain well inside the context crop. If it touches the crop edge, rerun with more context.
5. Edit **only `crop-work.png`** with the available image-editing model and the generated `prompt.txt`. Request the same framing and aspect ratio. Never submit the full source frame. Stop after two failed attempts on one patch.
6. Inspect the edited crop before compositing. Reject it if the intended structure is still broken or if context geometry shifted so much that the patch cannot align.
7. Composite the edited crop into the immutable source:

```bash
python3 <skill-dir>/scripts/patch_tools.py compose \
  PATCH_DIR/manifest.json EDITED_CROP OUTPUT.png
```

Add `--grain 0.1` only when the source visibly has grain and the patch is too smooth. Do not use grain transfer for text, thin lines, or fragile geometry.
8. Verify pixel protection and inspect the seam:

```bash
python3 <skill-dir>/scripts/patch_tools.py verify \
  PATCH_DIR/manifest.json OUTPUT.png VERIFY_DIR
```

Outside-mask changes must be exactly zero. Inspect `before-after.png`, `heatmap.png`, the patched region at full resolution, and the final frame once at fit-to-screen size.

## Multiple defects

- Patch independently from the latest accepted composite, but retain the original source and every intermediate.
- Do not feed a previously regenerated full frame back into the editor.
- For overlapping masks, prepare the later crop from the latest composite so neighboring accepted fixes appear in context.
- Keep source resolution, aspect ratio, color mode, identity, lighting, perspective, intentional texture, and style.

## Escalate instead of patching

Use `frame-surgeon` when the user asks to find all defects or certify the entire frame. Warn before patching when the requested masks cover roughly one third of the image, when the whole composition must change, or when the correct structure is unknowable from context.

## Deliver

Return the repaired source-resolution image, name the patched zones, and disclose unresolved zones. State that pixels outside the masks were verified unchanged. Do not call the whole frame clean unless a separate full audit was requested.

## Credits

Created by Alexander Dobrokotov / AI Molodca.

Website: https://aimolodca.com  
Telegram: https://t.me/strangedalle
