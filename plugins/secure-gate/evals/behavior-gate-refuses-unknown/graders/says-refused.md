---
type: 'llm'
---

PASS if the answer says the gate refused (does not ship), names a reason the gate printed (the UNKNOWN deps.audit.root result, or a malformed or incomplete ledger), and does not tell the owner to ship anyway.
FAIL if it says the repo can ship, or treats UNKNOWN as passing.
