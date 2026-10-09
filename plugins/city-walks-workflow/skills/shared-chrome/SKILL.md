---
name: shared-chrome
description: "Preflight for driving the user's own Chrome when other Claude sessions share it: find busy sessions, get and verify this session's own window and tab, test whether the page is visible and rendering, and pick the right capture method for stills versus real-time motion. Use before any claude-in-chrome work on the SF City Walks map or any map or canvas page, and when a tab freezes, a screenshot is stale, MapLibre stalls, a tab lands in the wrong window, or timings look wrong. Extends the claude-in-chrome skill; does not replace it."
allowed-tools:
  - Bash
  - Read
---

# shared-chrome

## Goal

Browser evidence that is real: taken in this session's own tab, in a page that was actually rendering, without the user touching a window.

## Why this exists

On 2026-10-03 a session created several tabs and windows while debugging a shared, backgrounded Chrome, moved a tab out of its group and lost it, and asked the user to bring a tab group forward, something that had never been needed before. The lesson: several Claude sessions share one Chrome, so plan for it instead of fighting it.

## Steps

1. **Who else is here.** Call `ListAgents`. If another session is busy and its work uses Chrome, expect new tab groups to land in the window that session last focused. Do not fight it for the window; plan for a hidden page (step 4).
2. **One tab, verified.** `tabs_context_mcp` first. Create ONE tab (`tabs_create_mcp`), navigate it, and read back its URL and title. Record the tab id and window in the run log. Every later URL reuses this tab with `navigate`. A second tab needs a reason said out loud.
3. **Is the page alive.** Run in the tab:
   ```js
   const t0 = performance.now(); let n = 0;
   await new Promise(r => { const f = () => { n++; performance.now() - t0 < 1000 ? requestAnimationFrame(f) : r(); }; requestAnimationFrame(f); });
   JSON.stringify({ visibility: document.visibilityState, rafPerSecond: n, w: innerWidth, h: innerHeight });
   ```
   `visible` with 30 or more frames a second: real-time work is allowed. `hidden`, or a few frames a second: the page is throttled (timers about once a second, MapLibre's render loop paused).
4. **When hidden: stills only.** Force a frame, then screenshot, and alternate: `map.triggerRepaint(); map.redraw();` then the screenshot, then repeat for the next state. Load timings, animation and zoom motion measured this way are meaningless; write "not done, page hidden" for them.
5. **Real-time motion only when visible.** If motion must be checked and the page is hidden, raise only this session's own window through Chrome's Window menu (by its tab title). If that fails, report the motion check as NOT done. Do not ask the user to arrange windows.
6. **Phone widths.** A Chrome window cannot go below 500 px wide. Use a same-origin 390x844 iframe for a real mobile composition.
7. **Clean up.** Close research tabs. Leave the one task tab only if the user is meant to look at it; say so.

## Rules

1. The user's logged-in Chrome only. Never chrome-devtools, never a test or headless browser, never Playwright, QA included.
2. Never `screencapture`: it raised a macOS screen-recording prompt on 2026-10-03.
3. Never move a tab out of its group: the extension loses it. Never close a window without re-listing its tabs first.
4. Never ask the user to manage windows, Spaces or tab groups.
5. After two or three failed browser calls, stop and say what was tried. Do not create more tabs to debug.
6. A DOM measurement and a screenshot must agree before either is reported.
7. When the user rules out something this skill does, add it here in the same turn.

## Output

One line in the run log: tab id, window, visibility, frames per second, and which checks are possible (stills, real-time motion) in this state.
