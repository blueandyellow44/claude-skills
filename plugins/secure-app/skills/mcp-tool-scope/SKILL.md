---
name: mcp-tool-scope
description: "Check authorization inside an MCP server's tools, the layer route checks cannot see once /mcp sits behind OAuth (OWASP MCP07, MCP10, MCP06): every SQL read or write a non-owner tool can reach carries a predicate on the signed-in identity, follow-up lookups included; reads filter at the finest grain the app knows (channel visibility, not only server membership); no tool takes the caller's identity as an argument; tools the model can call do not change stored state; sync, delete and admin tools check an owner; OAuth client registration has a redirect-host allowlist; tool descriptions, parameter descriptions and server instructions carry no hidden directions (OWASP MCP03). Use when the user says 'MCP app security', 'can one user read another user's data through a tool', 'IDOR in my MCP server', 'is my connector scoped', before an MCP app goes to a reviewer, or when secure-launch reports mcp.*. Do NOT use it for the OAuth flow itself (launch-security-audit) or for prompt injection through tool results (secure-ai ai-attack-surface)."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
  - Grep
---

# mcp-tool-scope

Built 2026-11-01. A run of the whole suite on an MCP app passed every route check, because the app has one HTTP route and it is behind OAuth. All of its real authorization lived in about ten tools that take server, channel and message ids and answer from SQL, and the suite never looked there. This skill reads that layer.

## Trigger

The repo registers MCP tools (registerTool, server.tool, a FastMCP @tool), or secure-launch reports mcp.*.

## Inputs

- Repo path.

## Prerequisites

- secure-core.

## Procedure

Built further 2026-11-01 from a security review of a real MCP app, which found seven issues after this check had passed it: four were in reach of a static read and are checked now (follow-up lookups, scope grain, model-visible writes, open registration); browser-bound OAuth state, retention of deleted data and outage fallbacks are runtime behavior and need the app's own tests.

1. `python3 <base>/../../scripts/check_mcp.py REPO`.
2. `mcp.tool-scope` FAIL high: open each file:line. The statement is keyed on an id the caller passed and has no identity predicate, so any signed-in caller reads or changes another person's rows by passing their id. Add the identity to the WHERE (bound from the verified token), or a membership subquery.
3. `mcp.tool-scope` FAIL low: the statement is scoped, but a nested lookup inside it is not (for example the timestamp of a message used to page before it). It leaks the looked-up value for an id the caller cannot see, not the rows. Add the same predicate inside the subquery.
4. `mcp.identity-from-args` FAIL: drop the identity argument and read the caller from the token props inside the handler.
5. `mcp.privileged-tools` FAIL: add the owner or role check before the work starts.
5a. `mcp.scope-grain` FAIL (medium): the read is scoped, but more coarsely than its rows (per-channel rows filtered by server membership). Add the finer predicate.
5b. `mcp.model-writes` FAIL: medium when an argument the model chooses drives the write (dismiss_message_id), low when the write is a side effect of calling the tool (a "seen" marker). Move the write into its own tool with `_meta: { ui: { visibility: ['app'] } }` and call it from the card.
5c0. `mcp.tool-descriptions` FAIL (high): a description the model reads carries an instruction tag, concealment from the user, an order to read secrets or send data to a URL, or a rule for another tool. Rewrite it to say what the tool does and nothing else. Built after Cisco's key-free mcp-scanner caught 1 of 3 planted poisonings and flagged a real app's "every synced server" as exfiltration (trial 2026-11-01).
5c. `mcp.oauth-registration` FAIL (medium): dynamic registration or client-ID metadata documents accept any host. Refuse /register unless every redirect_uri is on an allowed host, and refuse client-id URLs outside the same list, before the OAuth library sees the request.
6. Then prove the predicates with mutation-proven-tests: remove the identity predicate from the main read, and a test that calls the tool as a second user must go red.

## Outputs

Three checks for the ledger, each with file:line evidence.

## Failure handling

- The check follows functions a tool calls, two hops, across served files; a deeper chain or SQL built from fragments in another module can be missed. Read the query layer by hand and say so.
- An id taken from a scoped lookup earlier in the same function counts as safe; one passed between functions does not, and reads as a false alarm. Accept it with its evidence through secure-gate, or restructure.
- An MCP import with no recognized tool registration is UNKNOWN: list the tools by hand.

## Verification

`bash <base>/../../tests/run_tests.sh`

Known-bad: a tool read keyed only on the caller's note id (FAIL high), a tool taking user_id as an argument, a sync tool with no owner check, a scoped read with an unscoped nested lookup (FAIL low), SQL passed through the app's own helper, and a FastMCP tool keyed only on the caller's id all FAIL. Phase 11 (bench/cases/secure_app_mcp.py, run as unit tests too): a follow-up lookup joining past the filter, the same in a function with brace-typed parameters, per-channel notes scoped by membership, an id lookup behind a registerAppTool tool, a model-visible dismiss argument, open registration, and an upstream redirect mistaken for an allowlist all FAIL; their fixed shapes and a one-line clock helper beside a log writer PASS. Description poisoning (bench/cases/secure_app_mcp_descriptions.py, also unit tests): an <IMPORTANT> tag reading ~/.ssh, history sent to a URL, a BCC rule for another tool, an HTML comment, a zero-width escape, a .describe() parameter, server.tool's description argument, server instructions and a FastMCP docstring all FAIL; a real app's routing text, a data label, a source URL with an API-key note, and a plain send_email description PASS. Known-good: an owner-scoped read beside an owner-gated sync, a visible() helper interpolated into the SQL, neighbors read by a channel id taken from a scoped lookup, and a membership subquery held in a const all PASS; a repo with no MCP server is mcp.none PASS; an MCP import with no recognizable tool is UNKNOWN.

## Rules

1. A PASS means each statement carries the predicate, not that the predicate is right; say so in the report.
2. When the owner rules that this skill should not do something, add that rule here in the same turn.
