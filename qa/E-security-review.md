# Adversarial Security/Privacy Review — RemoteToolbox

**Reviewer:** Riley (skeptical security/privacy reviewer, role-play QA)
**Date:** 2026-06-08
**Status: complete**

This file is the deliverable. Findings appended as I went.

VERDICT: The core safety promises mostly hold — the gitignore protects the
known secret/tool locations, Telegram access control gates every active handler,
and the empty-allowlist=nobody default is real. But there is one genuine
privacy **Major**: tool call **arguments are logged at INFO in cleartext**, so a
tool that takes a secret as a parameter leaks it to logs by default. Secondary
issues: a sys.path stdlib-shadowing footgun introduced by the loader, a broken
audit-grep in CLAUDE.md, and several documentation gaps (MCP risk, the arg-log
leak, sys.path behavior, config-name coverage of `.gitignore`).

---

## 1. The gitignore promise under attack — HOLDS for documented paths; minor gaps

Method: `git check-ignore` (read-only; never actually committed any secret).

PASS — these sneaky locations ARE ignored:
- Nested `.env` anywhere: `src/remotetoolbox/.env`, `docs/.env`, `tools/foo/.env` ✅
  (because `.env` / `.env.*` patterns are non-anchored, they match at any depth)
- `tools/<x>/.env`, `tools/<x>/secrets.json`, `tools/<x>/api.key` ✅
  (`/tools/*` ignores the whole tree except README/.gitkeep)
- `config.local.yaml`, `config.prod.local.yaml`, `config.yaml` ✅
- Secret-file-written-by-a-tool **under `tools/`**: `tools/output.txt`,
  `tools/cache.db`, `tools/state.sqlite` ✅ (whole /tools tree ignored)
- `mytools/.env`, `mytools/api.key` for a `tools.paths` repo cloned **inside**
  this repo ✅ (`.env`/`*.key` are global).

GAPS (Minor) — files that are NOT ignored if a user/tool writes them at the repo
root (outside `/tools`):

| Filename | Ignored? | Note |
|---|---|---|
| `config.yml` (`.yml` not `.yaml`) | ❌ NO | common typo/variant |
| `config.dev.yaml`, `config.staging.yaml`, `settings.yaml` | ❌ NO | only `config.yaml`, `config.local.yaml`, `config.*.local.yaml` are covered |
| `mytoken.json`, `apitoken.txt`, `token.json`, `bot.token` | ❌ NO | `*_token*` needs a literal underscore; `mytoken` has none |
| `apikey.txt`, `api_keys.json`, `creds.json`, `auth.json` | ❌ NO | no `*key*`/`*cred*` glob — only `*.key`, `*.credentials` |
| `cookies.txt`, `session.json` | ❌ NO | not covered |

Reality check: the **documented** secret locations (`.env`, `config.yaml`,
`*.key`, `/tools/*`) are all covered, and a tool that writes its state under
`tools/` is safe. The gap is only for ad-hoc secret files a user might drop at
the repo root with an off-pattern name. The `.gitignore` header already tells
users to "add new secret locations first," which mitigates this.

Severity: **Minor**. Suggested fix: broaden a few globs — add `*.yml` siblings
for config (`config.*.yml`), and add `*token*`, `*credential*`, `*secret*`
(case-insensitive intent) plus `cookies*`/`session*.json` if desired. Keep the
"add new locations first" note.

Audit-grep sanity (SECURITY.md): the two greps in SECURITY.md (lines 22-23 and
99) BOTH print `clean` ✅. See finding 7 for the **CLAUDE.md** grep, which does NOT.

## 2. Telegram access control — SOUND; every active entrypoint is gated

`src/remotetoolbox/chat/telegram.py`. Two handlers are registered:
- `CommandHandler("reset", on_reset)` — first line: `if not _authorized(update)
  or self.orchestrator is None: return`. ✅ gated.
- `MessageHandler(filters.TEXT & ~filters.COMMAND, on_message)` — first line:
  `if not _authorized(update): ... reply "⛔ Not authorized."; return`. ✅ gated.

`_authorized` = `bool(user and user.id in self.allowed)` where `self.allowed`
is the parsed allowlist. Empty allowlist ⇒ `self.allowed` is an empty set ⇒
`x in set()` is always False ⇒ **nobody authorized**. The empty-default=nobody
promise is **truly enforced** (the only gate is set-membership; there is no
"if empty, allow" branch anywhere). ✅ Constructor also logs a loud warning when
the allowlist is empty.

Non-text / edited / channel / captioned messages: these match **no** registered
handler (the message handler is `filters.TEXT & ~filters.COMMAND`; PTB v20+ does
NOT route edited messages or channel posts to a plain message handler by
default). So a photo, voice note, document, sticker, or edited message from
**anyone** triggers **zero** work — no LLM call, no tool call, no state change.
That is safe-by-omission (fail-closed). The only downside is purely UX: even an
*authorized* user gets silence if they send a non-text message (no "I only
handle text" reply). Not a security issue.

No unauthenticated path reaches `orchestrator.handle`, `.reset`, or any tool.

Severity: **none (pass)**. Optional Nit: add a catch-all handler that replies
"I only handle text messages" (still gated by `_authorized`) for better UX.

## 3. Secret leakage in logs — CONFIRMED LEAK (the headline finding)

`orchestrator.py:87`:
```python
log.info("chat=%s calling tool %s(%s)", chat_id, call.name, call.arguments)
```
`call.arguments` is the **full dict of tool arguments at INFO level** (INFO is
the default `logging.level`). If a tool takes a secret as a parameter, it is
written to logs in cleartext. Reproduced:

```
INFO remotetoolbox.orchestrator chat=42 calling tool
  send_email({'to': 'x@y.com', 'smtp_password': 'hunter2-SECRET',
              'api_key': 'sk-live-DEADBEEF'})
```

This is realistic: MCP tools and many user tools accept tokens/passwords/PII as
arguments (the LLM fills them from context or the user pastes them in chat).
Those logs commonly go to `journalctl` (DEPLOYMENT.md shows
`journalctl -u remotetoolbox -f`) and may be world-readable or shipped off-box.

Other log sites checked:
- The Telegram token is **never** logged (constructor logs `self.allowed`, the
  startup line logs authorized users, not the token). ✅
- `.env` values are not logged wholesale. ✅
- Tool **results** are not logged at INFO. `Toolset.call` logs `log.exception(
  "Tool %s raised")` (loader.py:60) — a traceback, which could include argument
  values captured in frames, but only on error and at ERROR level. Secondary.
- Rejected Telegram users: `log.warning("Rejected message from unauthorized
  user %s", update.effective_user)` logs the Telegram user object (id/username) —
  expected for an audit trail, acceptable.

Severity: **Major** (default-on cleartext secret logging). Suggested fix:
- Don't log raw arguments at INFO. Log argument **keys** only, or a redacted
  view (mask values for keys matching `pass|token|secret|key|auth|cred`), and
  move the full-arg dump to DEBUG. e.g.
  `log.info("chat=%s calling tool %s args=%s", chat_id, call.name,
   list(call.arguments))` and `log.debug(... full args ...)`.
- Document the logging behavior in SECURITY.md ("tool calls are logged; avoid
  passing secrets as tool arguments — read them from os.environ").

## 4. Error-reply leakage (`⚠️ {exc}` and tool error strings) — LOW, by design

`orchestrator.py:67`: on any exception in the agent loop the user gets
`f"⚠️ {exc}"`. `loader.py` `Toolset.call` returns `f"Error: tool {name} failed:
{exc}"` and `f"Error calling {name}: bad arguments ({exc})"` to the model
(which can echo it to the user).

Leak potential: exception messages can contain absolute filesystem paths
(`FileNotFoundError: /home/user/.../secret.json`), hostnames, partial URLs,
or—worst case—a secret a tool put into its own exception text (e.g. an HTTP
client echoing a URL with an embedded `?api_key=...`). Since the bot is
allowlisted to trusted users, the audience is limited, so this is low-impact in
the intended deployment, but it is real for prompt-injection scenarios (a tool
returning attacker-influenced text could surface internal detail).

Severity: **Minor**. Suggested fix: keep the friendly `⚠️` line but log the full
exception (already done) and return a generic "the tool failed" to the user
unless DEBUG; at minimum, document that exception text reaches the chat user so
tool authors avoid embedding secrets in exceptions/return strings.

## 5. Arbitrary code execution / sys.path trust model — REAL FOOTGUN, under-documented

Two parts.

(a) Trust model accuracy. SECURITY.md "Threat model" correctly states tools are
arbitrary code and a capability grant ("Only add tools you'd be comfortable
letting an imperfect assistant invoke"). That framing is accurate for the
*intended* "I write my own tools" case. But it does NOT explicitly say that
**anything placed in a `tools.paths` directory executes at import time with the
full privileges of the RemoteToolbox process** — merely *dropping a file in the
folder runs it at startup*, before any LLM/allowlist is involved. A user who
clones a third-party "tool pack" into `tools/` is running untrusted code. This
should be stated plainly.

(b) sys.path injection (new behavior in `loader._import_file`):
```python
parent = str(path.parent)
if parent not in sys.path:
    sys.path.insert(0, parent)
```
Each tool directory is inserted at **sys.path[0]** (highest priority). CONFIRMED
consequence: a file in a tool dir named like a stdlib/third-party module
**shadows the real module process-wide**, affecting the framework itself, not
just that tool. Reproduced:

```
SHADOW CONFIRMED: HIJACKED: a tool-dir file named textwrap.py shadowed the
stdlib module
```

So a tool folder containing `secrets.py`, `json.py`, `ssl.py`, `http.py`,
`textwrap.py`, etc. will be imported instead of the stdlib by any later bare
import anywhere in the process. The loader's `_skipped()` only excludes
`_`-prefixed files from being **imported as tools** — it does NOT remove their
directory from sys.path, and non-underscore collisions aren't skipped at all.
This is a surprising, silent way for a sloppy or malicious tool pack to hijack
core imports (a `secrets.py` could shadow Python's `secrets` module used for
token generation elsewhere). `insert(0, ...)` also means tool dirs win over
site-packages.

Severity: **Major** (footgun / supply-chain shadowing; silent, process-wide).
Suggested fixes (any of):
- Prefer `sys.path.append(parent)` over `insert(0, ...)` so stdlib/site-packages
  win over tool dirs (reduces accidental shadowing of real modules).
- Better: don't mutate global sys.path at all — load sibling helpers with a
  package-style import or a temporary sys.path context that's popped after
  `exec_module`.
- Document in SECURITY.md/WRITING_TOOLS.md that helper modules must be uniquely
  named (the loader docstring says "prefix them" for *correctness*, but the
  *security* shadowing risk isn't called out).

## 6. External MCP servers — UNDOCUMENTED RISK

`tools.mcp_servers` (config.py `MCPServerConfig`: `command`, `args`, `env`) is
passed to `StdioServerParameters` and launched via `stdio_client` in
`mcp_client.py`. This means **configuring an MCP server launches an arbitrary
local command** (e.g. `npx -y @modelcontextprotocol/server-filesystem /srv`),
with an env you specify, and then **exposes all of that server's tools to the
LLM** with no per-tool allowlist. The example in `config.example.yaml` mounts a
filesystem server at `/srv/shared` — a broad capability grant.

Risks not documented in SECURITY.md:
- Running a third-party MCP server = running third-party code with your
  privileges (same trust issue as local tools, but pulled from npm/pip at run
  time via `npx -y`, which fetches+executes remote packages).
- MCP tools' descriptions/schemas come from the server and are fed to the LLM;
  a hostile server can present tools/prompt-injection-laden descriptions.
- `env` for MCP servers can carry secrets; those are handed to the child process
  (expected) but worth noting they're as trusted as the command.

SECURITY.md does not mention MCP at all. The MCP shadowing guard (loader.py:161
"MCP tool shadows a local tool; keeping local one") is a nice touch but is about
name collisions, not trust.

Severity: **Major** (undocumented "this launches arbitrary commands and trusts a
remote server"). Suggested fix: add an MCP section to SECURITY.md: MCP servers
run as local subprocesses with your privileges; only configure servers you
trust; pin versions instead of `npx -y` latest; scope filesystem servers to a
narrow directory; treat their tool descriptions as untrusted input.

## 7. SECURITY.md accuracy/completeness — mostly accurate; one broken grep + gaps

Verified claims:
- "nothing private in git" / `.gitignore` enforcement — accurate for documented
  paths (finding 1). ✅
- The two audit greps in SECURITY.md (lines 22-23 and 99) both print `clean` ✅
  (sanity-checked; they were the "just fixed" commands).
- "Empty allowlist = nobody" — accurate and truly enforced (finding 2). ✅
- "Every incoming message is checked before it reaches the agent" — accurate for
  text + /reset; non-text msgs reach no handler (also safe). ✅
- "model runs locally, chat transport leaves your network" — accurate. ✅
- Long-polling / no inbound ports — accurate. ✅

PROBLEMS:
- **CLAUDE.md audit grep is broken (Minor/Major for the AI-contributor
  workflow).** The command in CLAUDE.md "Git rules":
  ```
  git ls-files | grep -E 'tools/(?!README|\.gitkeep)|\.env$|config\.yaml$' || echo clean
  ```
  uses a **PCRE negative lookahead** `(?!...)` that GNU/BSD `grep -E` (ERE) does
  NOT support. Result: `grep: warning: ? at start of expression` and it then
  **matches `tools/.gitkeep`** — so it prints `tools/.gitkeep` instead of
  `clean`, i.e. a false positive that would scare an AI/contributor into
  thinking a private file is tracked. SECURITY.md's equivalent grep (which
  excludes `tools/(README\.md|\.gitkeep)` via a second `grep -vE`) is correct and
  prints `clean`. Fix: replace CLAUDE.md's grep with the SECURITY.md version
  (two-stage `grep -E ... | grep -vE ...`), or use `grep -P` if PCRE is intended
  (less portable). This is the one "audit command" that does NOT print `clean`.
- **Missing: the INFO arg-logging leak (finding 3)** — SECURITY.md "Where
  secrets live" says read tokens from `os.environ`, but never warns that passing
  a secret as a *tool argument* leaks it to logs. Add the warning.
- **Missing: MCP risk (finding 6).**
- **Missing: sys.path shadowing / "dropping a file runs code at startup"
  (finding 5).**
- **Minor wording**: "Tool API keys/tokens → read via os.environ" is good
  guidance but isn't backed by any enforcement; combined with finding 3, a tool
  that does take a key as an arg silently logs it.

Severity: **Minor** for SECURITY.md prose accuracy (claims it makes are true);
**Minor** for the broken CLAUDE.md grep (wrong output, but fail-loud/visible);
plus the doc-gap items above which are really restatements of findings 3/5/6.

---

## Summary / Verdict

The safety promises **largely hold**: secrets/tools stay out of git for every
documented location, Telegram access control is fail-closed and gates every
active handler with a true empty=nobody default, and the local-model privacy
claim is accurate. The notable problems are a **default-on cleartext logging of
tool arguments** (secrets-in-args leak), a **process-wide sys.path stdlib
shadowing footgun** from the loader, **undocumented arbitrary-command execution
via MCP**, and a **broken audit grep in CLAUDE.md**.

### Findings by severity
- Blocker: 0
- Major: 3 (#3 arg-logging leak, #5 sys.path shadowing/trust-doc, #6 MCP risk undocumented)
- Minor: 4 (#1 off-pattern gitignore gaps, #4 error-reply leakage, #7 broken CLAUDE.md grep, #7 doc gaps)
- Nit: 1 (Telegram non-text UX catch-all)

### Top 3 fixes
1. **Stop logging raw tool arguments at INFO** (orchestrator.py:87). Log arg
   keys / redacted values at INFO; move full args to DEBUG. Add a SECURITY.md
   note: don't pass secrets as tool arguments.
2. **Fix the sys.path behavior** in `loader._import_file`: use `append` not
   `insert(0, ...)` (or a popped temporary path), so a tool-dir file can't shadow
   stdlib/site-packages process-wide. Document the shadowing risk and that
   dropping a file in `tools/` executes it at startup.
3. **Document MCP + fix the CLAUDE.md audit grep.** Add an MCP section to
   SECURITY.md (configuring a server launches an arbitrary local command and
   trusts a remote tool provider; pin versions, scope FS servers). Replace the
   PCRE-lookahead grep in CLAUDE.md with the portable two-stage grep from
   SECURITY.md so it prints `clean`.
