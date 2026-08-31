# Visual acceptance for uncertain patches

Read this reference only for inferred repairs, reconstructions, paired objects, or long connected surfaces.

## Build the acceptance contract

Describe observable relationships, not merely appearance. Useful invariants include:

- exact object count;
- continuous attachment between parts;
- interaction or contact with a neighboring object;
- preserved silhouette and perspective;
- matching material, lighting, scale, or design family;
- absence of the old defect and forbidden residues.

Mark facts that cannot be known from the source as `uncertain`. A plausible reconstruction is not an exact recovery.

## Select the strategy

- **Occluder crossing several materials:** trace the occluder tightly, provide enough context for every crossed boundary, and inspect each reconstructed boundary separately.
- **Content inside a native frame:** protect the original frame and replace only its interior.
- **Paired objects:** provide the accepted member as a reference and define which properties must match versus differ by perspective.
- **Long continuous surface:** use one connected strip or mask and inspect the entire continuity, not a series of isolated seams.
- **Anatomy or mechanism:** specify object count, attachment, contact, and forbidden intersections.

## Visual gate

Review at three scales:

1. **200%:** seams, halos, double contours, residue, texture breaks, and edge noise.
2. **100%:** topology, anatomy, object relationships, text, perspective, and material continuity.
3. **Fit-to-screen:** whether the patch attracts attention or changes the composition.

Reject the patch if any required invariant fails, even when no pixels changed outside the mask. If two attempts fail for the same reason, pivot the strategy instead of slightly expanding the mask or feather again.

For a reconstruction with several plausible hidden shapes, select the strongest candidate only when all variants preserve the same known evidence. Otherwise disclose the ambiguity or ask the user to choose.
