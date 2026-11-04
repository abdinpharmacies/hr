# Abdin eCommerce Editor — interaction and motion rules

These instructions apply to every file in `ab_ecommerce_editor`. Follow the repository's parent instructions as well.

## Visual reference

The current `ab_ecommerce_editor` workspace is the reference for all future UI work. Preserve its blue/violet palette, white surfaces, rounded panels, typography, spacing, restrained shadows, and Arabic RTL support. Use `ui-ux-pro-max` for UI work. Keep all changes scoped to this module.

## Motion is part of the feature

- Every navigation, panel change, selection, reorder, insertion, removal, and interactive state change must have intentional transition feedback consistent with this workspace.
- Preserve staged entrances and short exits when navigating between the library, document editor, and reusable-template editor.
- Allow blocks to be dragged directly in the preview and from the layer list. Show the drop position before release and retain up/down buttons for keyboard and touch users.
- Animate reordering as a coordinated hop: one block lifts toward its new position while the displaced block moves in the opposite direction; both settle smoothly. Apply the same movement to drag/drop, move buttons, undo, and redo.
- Animate the existing keyed block elements between their old and new positions. Do not remount the entire preview just to replay an entrance animation; preserve focus and scroll position.
- Use the existing spring-like easing. Keep interaction feedback around 150–240 ms, rearrangement around 420–520 ms, and staged entrances around 480–650 ms. Prefer transform and opacity animations.
- Motion must explain an action. Avoid decorative infinite loops, flashing, and animations that delay editing or saving. Loading indicators may loop.
- Handle interrupted navigation, cancelled drags, rapid repeated movement, failed requests, and component destruction without stuck states or stale updates. Cancel owned animations during cleanup.
- Respect `prefers-reduced-motion` in both CSS and JavaScript. Reduced motion must preserve every operation while skipping travel, scale, and hop effects.

## Verification and continuity

- Verify preview dragging in both directions, layer synchronization, undo/redo, saved order, locked review states, RTL, mobile alternatives, and reduced motion when changing movement behavior.
- Keep English source strings and both Arabic catalogs synchronized; retain accessible names, visible focus, and controls usable without dragging.
- Update `changelog.d/current.md` with the actual changes. Put test evidence and outstanding limitations in `outputs/ab_ecommerce_editor_validation` outside the runtime addon.
- Preserve draft/published separation, publishing permissions, company isolation, and the versioned JSON contract. Visual work must not alter commerce data or bypass publication controls.
