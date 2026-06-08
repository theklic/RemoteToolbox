# Managing your tools (version history, changelog, rollback)

Your tools are **yours** — they're gitignored out of the RemoteToolbox repo on
purpose. But "not in the toolbox's git" doesn't mean "not in *any* git." The
recommended setup is to keep your tools in **their own git repository**, so you
get full version history, a changelog, branches for risky changes, and one-command
rollback when you break something — all completely separate from the framework.

```
   RemoteToolbox repo  ──────►  framework + docs        (you pull updates)
   your tools repo     ──────►  hello/, weather/, …     (you own the history)
                                CHANGELOG.md
```

The two repos live independent lives: you can update the framework without
touching your tools, and rewrite your tools' history without affecting the
framework.

---

## Two layouts (pick one)

### A) A separate tools repo — recommended

Keep your tools in their own directory anywhere on disk, as its own repo, and
point the toolbox at it.

```bash
# Bootstrap from the template (copies a .gitignore + CHANGELOG + a starter tool)
cp -r RemoteToolbox/examples/tools-repo ~/rtb-tools
cd ~/rtb-tools
git init && git add -A && git commit -m "My tools: initial commit"
```

Then tell the toolbox where they are, in `config.yaml`:

```yaml
tools:
  paths:
    - ~/rtb-tools        # ~ is expanded; any absolute/relative path works
```

Restart RemoteToolbox. Done. Your tools and their history are fully separate from
the framework. You can even point multiple toolbox installs at the same repo.

> `tools.paths` accepts **multiple** directories, so you can mix a personal repo,
> a shared/team repo, and the default `./tools` if you like.

### B) A repo nested inside `tools/` — zero config

If you'd rather not touch config, just make the default `tools/` folder its own
repo:

```bash
cd RemoteToolbox/tools
git init && git add -A && git commit -m "My tools: initial commit"
```

This works because the toolbox repo **ignores** everything in `tools/`, so your
nested `.git` and tool files are invisible to it (the loader also skips `.git/`).

**Caveat:** `tools/` also contains two files the *toolbox* owns
(`README.md`, `.gitkeep`). They'll show up in your nested repo — just commit them
or add them to your tools repo's `.gitignore`. Layout (A) avoids this overlap,
which is why it's recommended.

---

## Keep a changelog

A changelog is what turns "git history" into "I know exactly what to roll back."
The template ships a [`CHANGELOG.md`](../examples/tools-repo/CHANGELOG.md) you can
keep updating. Minimum viable habit:

- One entry per meaningful change, newest on top: what tool, what changed, why.
- Commit the changelog **with** the code change it describes.
- Tag known-good states so you can jump back instantly:

  ```bash
  git add -A && git commit -m "weather: add wind speed"
  git tag good-2026-06-08          # a snapshot you trust
  ```

If you let an AI assistant add tools, ask it to add a changelog entry too — see
[CLAUDE.md](../CLAUDE.md).

---

## Everyday workflow

```bash
# Try a risky change on a branch so main stays runnable
git switch -c experiment-new-scraper
# ...edit tools, restart RemoteToolbox, test in the console adapter...
git add -A && git commit -m "scraper: try new parser"

# Happy? merge it back
git switch main && git merge experiment-new-scraper

# Not happy? throw it away
git switch main && git branch -D experiment-new-scraper
```

Remember: **tools load at startup**, so restart RemoteToolbox after any change
(`python -m remotetoolbox`, or restart the service — see
[DEPLOYMENT.md](DEPLOYMENT.md#6-run-it-as-a-service-systemd)).

---

## Rolling back when you break something

You changed a tool, restarted, and now it errors or behaves wrong. Options, from
gentlest to bluntest:

**Undo the last change but keep a record of the undo:**

```bash
git revert HEAD          # makes a new commit that reverses the last one
```

**Jump back to a known-good tag, then move forward again:**

```bash
git stash                # park any uncommitted edits
git checkout good-2026-06-08    # inspect/run this known-good snapshot
# happy here? make it the new tip:
git switch -c recovery && git switch main && git reset --hard good-2026-06-08
```

**Restore just one broken tool file from a past commit** (leave everything else):

```bash
git log --oneline -- weather/tool.py     # find a good commit
git checkout <commit> -- weather/tool.py # restore only that file
git commit -m "weather: roll back to working version"
```

After any rollback, **restart RemoteToolbox** so it reloads the tools.

> The changelog tells you *which* tag/commit is the safe one — that's why it's
> worth keeping.

---

## Back up to a private remote

Local history protects you from your own edits; a remote protects you from a dead
disk or a re-cloned container.

```bash
# Create a PRIVATE repo on GitHub/GitLab first, then:
git remote add origin git@github.com:you/rtb-tools.git
git push -u origin main
```

Make it **private** — even though secrets shouldn't be in here, your tools reveal
what your home setup can do. (The template `.gitignore` keeps `.env` and
credentials out regardless.)

---

## Secrets stay out of your tools repo

Tool credentials (API keys, tokens) live in the **toolbox's `.env`** and are read
at runtime via `os.environ` — never written into tool files. So your tools repo
contains only code + changelog and is safe to version and push. See
[WRITING_TOOLS.md › Secrets](WRITING_TOOLS.md#secrets--credentials) and
[SECURITY.md](SECURITY.md).

---

## Tracking which framework version your tools target (optional)

If you upgrade RemoteToolbox and a tool stops working, it helps to know which
framework version your tools were written against. A lightweight habit: note the
RemoteToolbox version (`python -c "import remotetoolbox; print(remotetoolbox.__version__)"`)
in your `CHANGELOG.md` when you do a framework upgrade, so you can correlate.

---

## TL;DR

- Your tools belong in **their own git repo**, separate from the toolbox.
- Bootstrap from [`examples/tools-repo`](../examples/tools-repo/) and point
  `tools.paths` at it.
- Keep a `CHANGELOG.md`; tag known-good states.
- Break something? `git revert`, restore a file, or reset to a tag — then restart.
- Push to a **private** remote for backup. Secrets stay in the toolbox `.env`.
