# My RemoteToolbox tools

This is a **starter template for your own, private tools repository** — version
history, changelog, and rollback for the tools you run on RemoteToolbox, kept in
a git repo that is **completely separate** from the RemoteToolbox framework repo.

> Full guide: [RemoteToolbox › docs/MANAGING_TOOLS.md](https://github.com/theklic/RemoteToolbox/blob/main/docs/MANAGING_TOOLS.md)

## Use it

```bash
# 1. Copy this template somewhere outside the toolbox repo
cp -r /path/to/RemoteToolbox/examples/tools-repo ~/rtb-tools
cd ~/rtb-tools

# 2. Make it its own git repo
git init && git add -A && git commit -m "My tools: initial commit"

# 3. Tell RemoteToolbox where they are: in the toolbox's config.yaml
#    tools:
#      paths:
#        - ~/rtb-tools
```

Restart RemoteToolbox and your tools load from here. Now every change to a tool
is tracked, changelogged, and reversible — independent of the framework.

## What's here

```
.
├── .gitignore      # keeps secrets/caches out of your tools repo
├── CHANGELOG.md    # record what you change, so you can roll back with intent
├── README.md       # this file
└── hello/
    └── tool.py     # a starter tool — copy/rename it for your own
```

## Important

- **Secrets do not go here.** Tool API keys/tokens live in the toolbox's `.env`
  and are read via `os.environ`. This repo stays secret-free (and the
  `.gitignore` enforces it), so it's safe to push to a private remote.
- Write tools exactly as in
  [docs/WRITING_TOOLS.md](https://github.com/theklic/RemoteToolbox/blob/main/docs/WRITING_TOOLS.md).
