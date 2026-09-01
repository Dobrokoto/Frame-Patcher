# Additive object workflow

Use additive mode when the requested object does not exist in the source. The core distinction is temporal: the composite mask is authored **after** generation, from the actual generated object and its real interaction with the scene.

## Why a pre-generation silhouette is wrong

A guessed mask predicts anatomy, pose, overlap, and shadow before the model has created them. Generated legs, tails, hair, handles, smoke, reflections, or contact shadows then cross the guessed boundary and are clipped. Pixel protection can still pass while the object looks pasted, incomplete, or physically disconnected.

The initial bbox or overlay is therefore only a placement guide. It chooses the crop and communicates approximate composition; it never defines the final silhouette.

## Workflow

1. Choose a context crop large enough to show scale references, support plane, light direction, occlusion order, reflections, and neighboring people or props. Prefer more context over a larger placement box.
2. Prepare with `--mode additive` and a placement bbox. Generate from the clean `crop-work.png`. A placement overlay may be supplied only as guidance and must be described as non-binding.
3. Reject the generated crop unless every new object is complete and already belongs in the scene: correct anatomy or topology, perspective, scale, contact, occlusion, shadow, reflection, softness, grain, and color response.
4. Create a grayscale post-generation mask over the generated crop:
   - white retains the generated result;
   - black restores the immutable source;
   - gray provides intentionally soft transitions.
5. Retain the complete new silhouette plus physically necessary contact shadows, reflections, displaced material, or local interaction. Erase unrelated regenerated people, floor, walls, text, props, and background.
6. Run `postmask` with the same generated crop that the mask was authored against. Inspect both post-mask overlays before composing.
7. Compose and verify. Technical verification must show zero changed pixels outside the staged soft mask. Visual acceptance must still pass at 200%, 100%, and fit-to-screen.

```bash
python3 <skill-dir>/scripts/patch_tools.py prepare SOURCE PATCH_DIR \
  --bbox x,y,width,height --context-bbox x,y,width,height \
  --mode additive --risk reconstruction \
  --request "add one dog and one hamster in the open floor area" \
  --invariant "exactly one complete dog and one complete hamster" \
  --invariant "both animals share the source floor plane and lighting"

# Generate using PATCH_DIR/crop-work.png. Then mask that actual result.
python3 <skill-dir>/scripts/patch_tools.py postmask \
  PATCH_DIR/manifest.json EDITED_CROP POST_GENERATION_MASK.png

python3 <skill-dir>/scripts/patch_tools.py compose \
  PATCH_DIR/manifest.json EDITED_CROP OUTPUT.png

python3 <skill-dir>/scripts/patch_tools.py verify \
  PATCH_DIR/manifest.json OUTPUT.png VERIFY_DIR
```

`postmask` accepts a source-sized mask, a context-native mask, a work-crop mask, or a mask matching the generated crop. A grayscale mask preserves its authored softness by default. The same edited crop used for `postmask` must be used for `compose`; the script rejects a different generation.

## Acceptance facts

- The object count is exact.
- No generated silhouette is clipped by the mask.
- Feet, wheels, supports, or other contact points meet the support plane.
- Necessary shadows and reflections are retained without broad regenerated background.
- Protected people, products, text, architecture, and props return to source pixels outside the post mask.
- At fit-to-screen scale, the addition reads as part of the original capture rather than as an isolated sticker.

Do not use additive mode to repair a visible existing object. Use repair or replace, where a pre-existing target can support an exact pre-generation mask.
