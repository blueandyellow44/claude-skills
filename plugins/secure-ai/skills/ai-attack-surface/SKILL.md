---
name: ai-attack-surface
description: "Static security check of an app's AI features: a model key in browser code, caller input placed in the system prompt, an environment secret inside prompt text, model output written as raw HTML, passed to eval, a shell or string-built SQL, Markdown rendered with attacker images and links left on, and tool or function-calling handlers that fetch a URL the model picked. Use when the user says 'prompt injection', 'is my chatbot safe', 'AI security', 'LLM security', 'can someone jailbreak this', 'audit the AI route', or when secure-launch reports ai.*. Do NOT use it for AI spend and daily caps (secure-app ai-route-metering, abuse-and-spend) or for probing a running app (ai-redteam)."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
  - Grep
---

# ai-attack-surface

A model treats every piece of text it reads as possible instructions. Whatever a stranger can put in front of it (a chat message, a fetched page, an uploaded file, a tool result) can steer it, so the damage is decided by what the app lets the model's output touch. This skill finds those places in code. It does not judge prompt wording.

## Trigger

The repo calls a model API or SDK (Anthropic, OpenAI, Gemini, Vertex, OpenRouter, Perplexity, the Vercel AI SDK, LangChain, Workers AI), or secure-launch reported an `ai.*` FAIL.

## Inputs

- Repo path.

## Prerequisites

- secure-core.

## Procedure

1. `python3 <base>/../../scripts/check_ai.py REPO`.
2. Read every FAIL at its file:line before reporting; the checks follow one level of assignment inside a file and name-based output tracking, so confirm the value really is caller input or model output.
3. Fix in this order, worst first:
   - `ai.client-key` (critical): move the call behind a server route; rotate the key with secure-secrets secret-rotation, because it already shipped.
   - `ai.output.exec` (critical): parse the reply into a closed set of allowed actions; bind SQL parameters; never eval or shell out model text.
   - `ai.prompt.secret` (high): take the secret out of the prompt entirely. No prompt wording keeps it in.
   - `ai.prompt.system-input` (high): keep the system prompt fixed; send caller text as a user message, fenced (`<document>...</document>`) and named as data.
   - `ai.output.html` (high): render as text, or DOMPurify before any HTML sink.
   - `ai.tools.fetch` (high): route the tool's fetch through outbound-fetch-guard's safeFetch or a host allowlist.
   - `ai.output.markdown` (medium): `disallowedElements={['img']}` or a `urlTransform` allowlist on react-markdown; an image renderer that drops external URLs on marked.
4. Then run ai-redteam against the local dev server: a clean static pass says the dangerous plumbing is absent, not that the model resists injection.

## Outputs

One JSON object of checks (PASS, FAIL, UNKNOWN) for the ledger; each FAIL names file:line and a one-line fix.

## Failure handling

- The model call lives in a shared package outside the repo: `ai.none` PASSes. Run the check on that package too.
- A reply reaches the sink through two or more variables or across files: the check follows one assignment in the same file and can miss longer chains. Read the render path by hand and say so in the ledger.
- A sink is fed a variable named `summary` or `answer` that is not model output: that is a false alarm; rename the variable or accept the line with its evidence through secure-gate.

## Verification

`bash <base>/../../tests/run_tests.sh`

Known-bad: a Hono route with request JSON in the system prompt, a Stripe secret in the prompt, `c.html(reply)`, model SQL in a template `prepare`, a tool fetching `block.input.url`, ReactMarkdown and dangerouslySetInnerHTML on `reply`, and a Vite key with dangerouslyAllowBrowser all FAIL. Known-good: a fixed system prompt with fenced user input, safeFetch in the tool, DOMPurify and disallowedElements, and a browser that calls only its own `/api/chat` all PASS. Each id also FAILs on its own in a one-flaw fixture. Phase 8 (2026-11-01): a system prompt assembled in a variable, a sanitizer on a different sink, and a chat component rendering Markdown from a prop named `text` all FAIL; the same shapes made safe (a constant-only variable, the sanitizer on this sink, a blog renderer) PASS.

## Rules

1. Report the line, never a guess about the model's behavior; behavior is ai-redteam's job.
2. Never send a probe or a model call from this skill.
3. When the owner rules that this skill should not do something, add that rule here in the same turn.
