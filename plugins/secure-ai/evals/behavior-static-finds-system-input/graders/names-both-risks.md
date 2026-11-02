---
type: 'llm'
---

PASS if the answer says caller input (body.company) is placed in the system prompt AND flags that the reply is returned as text/html (or says plainly it could not judge the HTML risk), each with a file reference.
FAIL if it calls the route safe, or claims a probe or live test was run.
