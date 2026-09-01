---
name: frame-patcher
description: Repair, locally replace, integrate, or add a known object in a PNG, JPEG, or WebP still by editing one contextual crop and compositing it through a verified mask while preserving the rest of the source. Use for a user-identified broken or missing object, branded product, hand, face detail, sign, seam, residue, occluder, or additive insert. Do not use for exhaustive defect discovery, broad redesign, or whole-frame restyling.
---

# Frame Patcher

**Version:** 1.4

Repair the requested zone without regenerating the full frame. Pixel protection and visual correctness are separate acceptance gates: passing `verify` never proves that the repaired object looks correct or belongs in the scene.

## Modes and preflight

Choose one edit mode before preparing a patch:

- **Repair:** fix a defect while retaining the visible object.
- **Replace:** regenerate one object or a related object group from a supplied or canonical reference.
- **Integrate:** preserve an already accepted object and correct only its lighting, reflections, contact shadows, material response, grain, or sharpness. This is a fallback after repair or replacement, not a mandatory second pass.
- **Additive:** introduce a new object or related object group that does not yet exist in the source. Generate the clean contextual crop first, then build the composite mask from the actual generated result. Never force a new object into a silhouette invented before generation. Read [references/additive.md](references/additive.md).
- **Redesign:** the composition or a large connected structure must change. Stop using this skill and propose an appropriate broader edit.

Classify uncertainty separately as `repair`, `inferred`, or `reconstruction`. For inferred repair or reconstruction, read [references/visual-acceptance.md](references/visual-acceptance.md).

Before editing, define a short task contract:

- `method`: any workflow explicitly requested by the user;
- `target`: what changes;
- `must_be_true`: 3–7 visible facts required for acceptance;
- `protected`: nearby identity, geometry, text, or objects that must remain;
- `dependencies`: contact surfaces, shadows, reflections, or related objects that must stay coherent;
- `reference_source`: supplied or canonical visual reference when identity, branding, or text matters;
- `uncertain`: hidden structure that cannot be recovered from source pixels.

## Minimal execution policy

- Treat the user's requested method as a hard constraint. If it is impossible, explain why and ask before substituting another technique.
- Default to one inspection, one strategy, one contextual crop, one main generation, one composite, and one verification.
- In additive mode, the prepared region is only a placement guide. `compose` must remain blocked until `postmask` stages a mask made from the actual generation.
- Never make an editor output fit by silently resizing, cropping, stretching, or padding it. Normalize it only through the registration gate below, inspect protected landmarks, and reject coordinate drift before compositing.
- Do not introduce perspective overlays, manual warps, per-object transforms, code prototypes, or other alternate pipelines unless the user requested them or the agreed generative strategy failed for a named reason and the alternative is approved.
- Before any retry, identify the specific failed acceptance fact. Do not rerun merely to seek an unspecified improvement.
- Use an integration pass only when object identity and geometry already pass but the patch still looks pasted on.
- Keep intermediate crops, masks, and manifests temporary. Do not publish or persist them as deliverables.
- Do not narrate every internal operation. User-facing updates should cover meaningful milestones, blockers, or the ready candidate.

## Workflow

1. Inspect the full source once. Accept defect locations from the user's description, marked frame, or supplied detail crop. Do not tile the whole image or claim a full audit.
2. Work only in source-native coordinates. If a bbox came from a scaled preview, convert it and inspect the native overlay before editing.
3. Prepare one patch pack for the requested defect or addition. Group adjacent objects when they form one pile, cluster, continuous surface, or shared lighting/contact problem.
   - Use a tight bbox only for a simple interior repair.
   - For replacement or integration, use one larger contextual crop that contains the complete related group, its support surface, contact zones, neighboring materials, and useful reflection or lighting cues.
   - Keep the edit mask exact. A larger crop does not authorize a larger changed region.
   - For replacement, the mask must cover the complete outgoing object and every residue that must disappear. If transparent packaging, reflections, shadows, or a native frame must change with it, treat those pixels as one related replacement group instead of masking only the visible label or center.
   - Use `--context-bbox` when the useful context is asymmetric or automatic expansion misses the support plane.

```bash
python3 <skill-dir>/scripts/patch_tools.py prepare SOURCE PATCH_DIR \
  --bbox x,y,width,height --mode repair --request "repair description"

python3 <skill-dir>/scripts/patch_tools.py prepare SOURCE PATCH_DIR \
  --mask SOURCE_SIZED_MASK.png --context-bbox x,y,width,height \
  --mode replace --risk reconstruction --request "referenced replacement" \
  --invariant "exact object count and placement" \
  --invariant "reference-matched identity and design"
```

For additive work, use a placement bbox only to choose a large contextual crop. Do not send a pre-generation silhouette as an exact mask:

```bash
python3 <skill-dir>/scripts/patch_tools.py prepare SOURCE PATCH_DIR \
  --bbox x,y,width,height --context-bbox x,y,width,height \
  --mode additive --risk reconstruction \
  --request "add the requested object in the indicated area" \
  --invariant "complete object anatomy or geometry" \
  --invariant "physically correct contact shadow and scene interaction"
```

If the user supplied an unmarked detail crop, locate it first:

```bash
python3 <skill-dir>/scripts/patch_tools.py locate SOURCE DETAIL locate.json
```

Use the returned bbox only at confidence `>= 0.65`; otherwise ask for a mark or identify the native coordinates manually.

4. For a branded product, readable package, logo, or identity-critical object, require a visual reference before generation. Use the user's reference, a canonical asset, or an available relevant brand skill. Do not invent brand design or text from the prompt alone.
5. Inspect `guide.png`, `mask-overlay-native.png`, and `crop-mask-overlay.png`. The context must show enough of the scene to reconstruct perspective, light, contact, and material response. Add context rather than enlarging the edit mask. In additive mode, these overlays indicate placement only.
6. For repair, replace, or integrate, send only `crop-work.png` to the image editor as the base image. When supported, also send `mask-hard-work.png` and the visual references. State that white may change and black must remain unchanged. Include the task contract. Never send the full frame.
7. For additive mode, send the clean `crop-work.png`; use the placement guide only as optional composition guidance. Generate the whole crop with complete new objects, natural occlusion, contact shadows, reflections, and scene-matched softness. Then create a grayscale mask from that actual generated result, retaining only the added objects and physically necessary shadows, reflections, or local interaction. Erase unrelated regenerated background. Stage it before compositing:

```bash
python3 <skill-dir>/scripts/patch_tools.py postmask \
  PATCH_DIR/manifest.json EDITED_CROP POST_GENERATION_MASK.png
```

Inspect `postmask-overlay-edited.png` and `postmask-overlay-source.png`. The mask must follow the real generated silhouettes, not the earlier placement guide. If a reliable post-generation mask cannot be produced, stop rather than reverting to a guessed silhouette.
8. Before replacement or integration compositing, run the registration gate on the editor output:

```bash
python3 <skill-dir>/scripts/patch_tools.py stage \
  PATCH_DIR/manifest.json EDITED_CROP
```

Inspect `registration-checkerboard.png`, `registration-protected-overlay.png`, and `registration-side-by-side.png`. Protected landmarks, framing, scale, translation, and perspective must align. A matching aspect ratio is not evidence of registration. If the editor returned another pixel size, changed the cavity or frame, moved the replacement, or let its footprint extend beyond the authored mask, reject it and regenerate or prepare the complete related replacement group. Never solve geometric drift with a blind resize. After the overlays pass, explicitly stage the reviewed crop:

```bash
python3 <skill-dir>/scripts/patch_tools.py stage \
  PATCH_DIR/manifest.json EDITED_CROP --accept-registration
```

For additive mode, `postmask` remains the staging gate. Inspect the edited crop and its staged mask before compositing. Reject any mode for shifted protected geometry, wrong count or placement, reference drift, remaining outgoing-object fragments, broken text, perspective or topology, missing contact shadows or reflections, material mismatch, halos, double contours, technical bars, clipped generated silhouettes, or retained regenerated background.
9. Composite the registered or post-masked crop into the immutable source. `compose` must reject replacement and integration crops without accepted registration, and must reject arbitrary crop dimensions instead of resizing them silently:

```bash
python3 <skill-dir>/scripts/patch_tools.py compose \
  PATCH_DIR/manifest.json PATCH_DIR/edited-staged.png OUTPUT.png
```

Use `--grain` only when visible source grain makes the patch unnaturally smooth. Avoid it for text, thin lines, and fragile geometry.

10. Run technical verification first:

```bash
python3 <skill-dir>/scripts/patch_tools.py verify \
  PATCH_DIR/manifest.json OUTPUT.png VERIFY_DIR
```

Require `technical_pass: true`, then inspect `qa-contact-sheet.png` and `boundary-overlay.png` at 200%, the repaired object at 100%, and the full frame fit-to-screen. Accept only if every `must_be_true` fact passes, no protected area is damaged, and the patch does not attract attention as a pasted element.

The first verification intentionally returns `visual_acceptance: pending`, `pass: false`, and `delivery_allowed: false`, even when pixel protection passes. After the required visual inspection, record the result explicitly:

```bash
python3 <skill-dir>/scripts/patch_tools.py verify \
  PATCH_DIR/manifest.json OUTPUT.png VERIFY_DIR --visual-acceptance pass
```

Never deliver while `delivery_allowed` is false. A technical pass proves only that pixels outside the soft mask were protected; it does not prove that the replacement is complete, aligned, legible, or visually integrated.

11. If identity and geometry pass but scene integration fails, prepare one `--mode integrate` fallback from the latest accepted composite. Mask only the object surfaces and physically necessary nearby shadow or reflection zones. Preserve count, design, text, geometry, placement, and perspective.
12. Build later patches only from the latest visually accepted composite. Retain the original source and manifests locally until acceptance.

## Strategy and stopping rules

- Default to one generation attempt. Allow a second only after naming the failed acceptance fact and adjusting the relevant crop, mask, reference, or prompt.
- After two failures with the same strategy, stop and request a missing reference, change strategy with the user's approval, disclose unresolved uncertainty, or end the patch.
- Default to adaptive feathering. Use `--edge hard` for silhouettes, glass, text, and mechanical lines; use `--edge soft` for smoke, fur, or genuinely soft transitions. Never use feathering to hide incorrect geometry.
- Perspective warping and deterministic overlays are not default repair methods. Use them only when requested or approved after reference-based generation cannot preserve the required design.
- For an addition, prefer a larger context crop and a post-generation mask over separate guessed masks for each new object. The post mask may include soft contact shadows and reflections, but not unrelated regenerated floor, walls, people, or props.
- Warn before continuing when reconstruction spans unrelated structures or the editable region becomes broad enough to undermine local control.

## Deliver

Return only the source-resolution candidate and briefly report:

- patched zone;
- technical pixel-protection result;
- visual acceptance result;
- any uncertain or unresolved reconstruction.

Do not present intermediate candidates as final deliverables. Do not call the patch successful, clean, or exact when only technical verification passed.

## Credits

Created by Alexander Dobrokotov / AI Molodca.
https://aimolodca.com · https://t.me/strangedalle
