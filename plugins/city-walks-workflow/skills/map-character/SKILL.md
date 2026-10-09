---
name: map-character
description: "Draw a REAL PERSON as a map sprite, alone or driving/riding something (golf cart, tractor, bike), in the map's storybook style and in every facing the sprite needs as it moves. Use when the owner says 'put <name> in the cart', 'add <person> to the map', 'make it face the way it is going', 'they look like a cliche', 'they are in the passenger seat', or sends photos of a person for a sprite. Built from a golf-cart sprite on a sister map project (2026-10-04), which took four rounds; this is the one-round method. Not for buildings or landmarks (landmark-piece) and not for the review gate (piece-review)."
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# map-character

## Goal

One round: a sprite of a specific person that LOOKS LIKE THEM, sits correctly in or on its vehicle, faces where it is going in every facing, and stays inside the vehicle's outline. The owner sees one contact sheet that already passes the checklist below.

## Why this exists

A golf-cart sprite of a real person on a sister map project (2026-10-04) took four rounds and four corrections, each a failure this skill now prevents:

1. A generic cliche person. Cause: the prompt named an age category, and the model drew the category, not the person. The correction: look at the pictures.
2. Passenger seat / facing out of the cart, three times. Causes: a mirrored drawing moves the driver to the other seat; words like "far seat" lose to the reference image's pose; and the model turns faces to the viewer by default.
3. Hands in the lap instead of on the wheel.
4. Head drawn over the canopy roof.
5. Compose-from-words ignored the requested angle: the model copied the ANGLE of the reference cart image in 9 of 12 tries.

## Method

### 1. Describe the person from the photos, never by category (one pass, before any call)

Look at every photo the owner sends and write 5 to 7 concrete traits: build and posture, hair (length, direction, volume, color), glasses (shape, rim), signature expression, how they dress (cut, collar, the color they usually wear; the owner names it if known). BAN category words that summon a stereotype: elderly, grandma, old man, cute, little. Add explicit negatives for the stereotype the category would produce ("not tight curls, not round wire glasses"). Show the owner the trait list only if the photos disagree with each other.

### 2. One approved likeness first, at the simplest pose

Draw the person in ONE facing (front three-quarter, toward the viewer, the facing people are judged on). Three tries in parallel, Gemini `gemini-3-pro-image`, refs = [style anchor or the existing vehicle sprite, every photo]. Pick by likeness. This drawing becomes `<slug>-approved.png` and is a reference in every later call. Do not draw other facings until the likeness is right.

### 3. Every other facing comes from EDITING, never from composing

The model copies the reference image's angle and ignores angle words. So:

- Mirror the approved drawing (`ImageOps.mirror`) to get the opposite horizontal facing, then run a NARROW edit that changes only what mirroring broke (the seat, which hand, lettering). Prompt shape: "Edit IMAGE 1 ... Fix only that ... Change NOTHING else: <list>".
- For the away-from-viewer facing, compose ONCE with the vehicle reference showing the back of the vehicle if one exists; otherwise generate 3 and expect most to come back in the wrong angle; keep only the ones that match, then mirror and edit as above.
- Three tries per edit, in parallel. The sister project kept these as small scripts, one per fix (the seat; the head under the roof); they are not shipped with this plugin.

### 4. Seat geometry, in viewer terms (vehicles)

A US golf cart, car or tractor has its controls on the vehicle's LEFT. The viewer is always below the sprite. So: heading RIGHT shows the vehicle's right flank and the driver is in the FAR seat; heading LEFT shows the left flank and the driver is in the NEAR seat. Say it that way in the prompt, plus: "the other half of the seat is EMPTY", "shoulders, chest and face point the same way the vehicle's front points", "both hands on the wheel directly in front of the driver", "does not turn to the viewer or face out of the side". A mirrored front view for the opposite heading was accepted as long as the driver is behind the wheel and driving; the binding test is behind-the-wheel, hands-on, facing-forward, not left-hand drive in every frame.

### 5. Inside the vehicle's outline

Always include: "the whole head, including the top of the hair, sits clearly below the canopy's lower edge with a gap of air; the canopy edge and posts pass in front of or above the driver". If a keeper still overlaps, run the narrow head edit, not a redraw.

### 6. Checklist on a ZOOMED crop, before the owner sees anything

Crop each candidate to the person + vehicle at 2x and check, writing the verdict per item:

- [ ] Looks like the photos (the traits from step 1), not the category
- [ ] Behind the controls, not beside them
- [ ] Both hands on the wheel/handlebars
- [ ] Facing the direction of travel (not the viewer, not out the side)
- [ ] Head and body inside the vehicle outline (under any roof)
- [ ] Same style, line weight and palette as the map and the other facings
- [ ] Cut-out has no white halo

A contact sheet is NOT the check: a back view's hands-in-lap and a head over the roof were visible only zoomed. Never describe a candidate as "ruled out" in chat unless it is also absent from anything the owner can open; the owner reviews raw files too.

### 7. Wire facings in the app by heading, with hysteresis

Choose the drawing from the heading over a short lookahead: front when moving down the map, back when moving up, `scaleX(-1)` for left. Use enter/exit thresholds (the sister project: up-share > 0.3 to switch to the back view, < 0.1 to switch back) so it never flickers on a level stretch; simulate one lap and report the share per facing and switches per lap.

## Done when

The owner has seen one contact sheet of all facings that passed step 6, said deploy, and the live sprite files compare byte-equal to the local ones on a cache-busted fetch.
