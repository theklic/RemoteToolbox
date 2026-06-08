# QA logs

Running notes from persona-based QA passes. Each file is written **incrementally
and committed/pushed as findings are made**, so a dropped connection or usage
limit never loses the work in progress.

These are scratch artifacts, not project documentation (they're excluded from the
docs link-check). They can be cleaned up before a final merge.

## Pass 2 (in progress)

- `E-security-review.md` — adversarial security/privacy review (persona: Riley).
- `F-extender.md` — building a new chat adapter + LLM backend (persona: Jordan).

## Pass 1 (summary)

Four personas (beginner, tool author, home-server operator, vibe-coder) — findings
were fixed in commits `4b16e60` (crash-on-LLM-down) and `dc6f881` (bundle:
helper-import, init-tools `main` branch, audit greps, doc accuracy).
