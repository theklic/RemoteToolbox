"""Guards that keep the docs honest as the code changes.

These tests are the durability mechanism for the project's layered docs: if you
change a config key, a default, or a cross-reference and forget to update the
matching doc, CI fails here instead of the docs silently rotting.

Covered:
- Every config field (and its default) is documented in docs/CONFIGURATION.md.
- Every internal markdown link / #anchor across all docs resolves.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterator, get_args, get_origin

import pydantic
import pytest

from remotetoolbox import config as cfg

ROOT = Path(__file__).resolve().parents[1]


# ─────────────────────────────────────────────────────────────────────────────
# 1. config models  <->  docs/CONFIGURATION.md
# ─────────────────────────────────────────────────────────────────────────────

_UNSET = object()
CONFIG_DOC = (ROOT / "docs" / "CONFIGURATION.md").read_text()
CONFIG_LINES = CONFIG_DOC.splitlines()


def _default_of(field: pydantic.fields.FieldInfo) -> Any:
    if field.is_required():
        return _UNSET
    if field.default_factory is not None:  # type: ignore[truthy-function]
        try:
            return field.default_factory()  # type: ignore[misc]
        except Exception:
            return _UNSET
    return field.default


def _iter_leaf_fields(model: type[pydantic.BaseModel], prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Yield (dotted_path, default) for every leaf config field.

    Nested models recurse; a list-of-model field yields the container path *and*
    its children with a ``[]`` segment (matching how the doc writes them, e.g.
    ``tools.mcp_servers[].name``).
    """
    for fname, field in model.model_fields.items():
        ann = field.annotation
        path = f"{prefix}{fname}"

        if isinstance(ann, type) and issubclass(ann, pydantic.BaseModel):
            yield from _iter_leaf_fields(ann, prefix=path + ".")
            continue

        if get_origin(ann) in (list, set, tuple):
            args = get_args(ann)
            if args and isinstance(args[0], type) and issubclass(args[0], pydantic.BaseModel):
                yield path, _default_of(field)               # the container
                yield from _iter_leaf_fields(args[0], prefix=path + "[].")
                continue

        yield path, _default_of(field)


def _default_tokens(default: Any) -> list[str]:
    """Substrings that must appear in the doc row for this default to be 'shown'."""
    if default is _UNSET or default is None:
        return []
    if isinstance(default, bool):
        return [str(default)]
    if isinstance(default, (int, float)):
        return [str(default)]
    if isinstance(default, str):
        return [default] if default.strip() else []
    if isinstance(default, (list, tuple)):
        return [x for x in default if isinstance(x, str) and x.strip()]
    return []  # dicts etc. — completeness only


_CONFIG_FIELDS = list(_iter_leaf_fields(cfg.Config))


def _doc_rows_for(path: str) -> list[list[str]]:
    """Table rows (as stripped cell lists) whose Key column is exactly `path`.

    Table shape is: | Key | Type | Default | Description |  →  after splitting on
    '|' the key is cell[1] and the default is cell[3].
    """
    rows: list[list[str]] = []
    for ln in CONFIG_LINES:
        if "|" not in ln:
            continue
        cells = [c.strip() for c in ln.split("|")]
        if len(cells) >= 5 and cells[1] == f"`{path}`":
            rows.append(cells)
    return rows


@pytest.mark.parametrize("path,default", _CONFIG_FIELDS, ids=[p for p, _ in _CONFIG_FIELDS])
def test_config_key_is_documented(path: str, default: Any) -> None:
    rows = _doc_rows_for(path)
    assert rows, (
        f"Config key `{path}` exists in config.py but is not documented in "
        f"docs/CONFIGURATION.md. Add a table row for it (keep the docs in sync)."
    )
    default_col = " ".join(cells[3] for cells in rows)  # the Default column only
    for token in _default_tokens(default):
        assert token in default_col, (
            f"Default for `{path}` is {default!r} but the Default column of its "
            f"CONFIGURATION.md row shows {default_col!r}. Update the doc."
        )


def test_config_doc_has_no_obvious_stragglers() -> None:
    """Catch dotted keys documented under a section that no longer exist in the
    models (typo'd or removed keys). Only checks ``a.b``-style backticked keys."""
    # Only consider dotted tokens rooted at a real top-level config section, so
    # filenames like `config.yaml` or `os.environ` aren't mistaken for keys.
    roots = tuple(f"{name}." for name in cfg.Config.model_fields)
    documented = {
        tok
        for tok in re.findall(r"`([a-z_]+(?:\.[a-z_]+|\[\])+)`", CONFIG_DOC)
        if tok.startswith(roots)
    }
    known = {p for p, _ in _CONFIG_FIELDS}
    # Allow documenting parent/section paths (prefixes of a real key).
    unknown = {
        key
        for key in documented
        if key not in known and not any(k.startswith(key + ".") or k.startswith(key + "[]") for k in known)
    }
    assert not unknown, (
        f"docs/CONFIGURATION.md documents config keys that don't exist in "
        f"config.py: {sorted(unknown)}. Remove or fix them."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. internal markdown links / anchors resolve
# ─────────────────────────────────────────────────────────────────────────────

_MD_FILES = sorted(
    p
    for p in ROOT.rglob("*.md")
    # qa/ holds running QA scratch notes — not project docs, so don't link-check them.
    if not any(part in {".venv", ".git", "node_modules", "qa"} for part in p.parts)
)
_LINK_RE = re.compile(r"\[(?:[^\]]+)\]\(([^)]+)\)")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*$")
_ANAME_RE = re.compile(r'<a\s+name="([^"]+)"', re.IGNORECASE)
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def _strip_code(text: str) -> str:
    return _FENCE_RE.sub("", text)


def _slugify(heading: str) -> str:
    """Approximate GitHub's heading-anchor algorithm."""
    h = heading.strip().lower()
    h = re.sub(r"[^\w\s-]", "", h)  # drop punctuation (keeps word chars, space, hyphen)
    h = re.sub(r"\s", "-", h)       # each whitespace -> one hyphen (preserves '--')
    return h


def _anchors_of(path: Path) -> set[str]:
    text = _strip_code(path.read_text())
    anchors: set[str] = set()
    for line in text.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            anchors.add(_slugify(m.group(1)))
    for m in _ANAME_RE.finditer(text):
        anchors.add(m.group(1).lower())
    return anchors


def _collect_links() -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for md in _MD_FILES:
        body = _strip_code(md.read_text())
        for m in _LINK_RE.finditer(body):
            out.append((md, m.group(1).strip()))
    return out


_LINKS = _collect_links()


@pytest.mark.parametrize(
    "src,target",
    _LINKS,
    ids=[f"{src.relative_to(ROOT)}->{target}" for src, target in _LINKS],
)
def test_internal_link_resolves(src: Path, target: str) -> None:
    if target.startswith(("http://", "https://", "mailto:", "tel:")):
        return  # external; not our job to verify

    file_part, _, anchor = target.partition("#")

    if file_part:
        dest = (src.parent / file_part).resolve()
        assert dest.exists(), (
            f"{src.relative_to(ROOT)}: link target {file_part!r} does not exist."
        )
    else:
        dest = src  # pure in-page anchor

    if anchor:
        assert dest.suffix == ".md", (
            f"{src.relative_to(ROOT)}: anchor link into non-markdown file {dest.name}."
        )
        assert anchor.lower() in _anchors_of(dest), (
            f"{src.relative_to(ROOT)}: anchor #{anchor} not found in "
            f"{dest.relative_to(ROOT)} (heading renamed or removed?)."
        )


# ─────────────────────────────────────────────────────────────────────────────
# 3. REFERENCE.md error-table strings still exist in source
# ─────────────────────────────────────────────────────────────────────────────

_REFERENCE_DOC = (ROOT / "docs" / "REFERENCE.md").read_text()
_SRC_PY = "\n".join(p.read_text() for p in (ROOT / "src").rglob("*.py"))
_PLACEHOLDER = re.compile(r"<[^>]+>|…|\{[^}]*\}")

# Messages produced by third-party libs (not our source) — exempt from the check.
_EXEMPT_ERROR_MESSAGES: set[str] = set()


def _norm_msg(s: str) -> str:
    """Normalise away quoting/escaping noise so doc text and source f-strings
    can be compared (drops backslashes, backticks, quotes; collapses whitespace)."""
    for ch in ("\\", "`", "'", '"'):
        s = s.replace(ch, "")
    return re.sub(r"\s+", " ", s).strip()


def _norm_src(s: str) -> str:
    """Like _norm_msg, but first join Python implicit string-concatenation seams
    (``"…a. " f"b…"``) so an error message split across adjacent string literals
    reads as one continuous string."""
    s = re.sub(r"""["']\s*(?:[frbu]{1,2})?["']""", "", s)
    return _norm_msg(s)


def _error_table_messages() -> list[str]:
    section = _REFERENCE_DOC.split("## Error & message reference", 1)[-1]
    messages: list[str] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("| `"):
            continue
        cell = line.split("|")[1].strip()
        m = re.search(r"`(.+)`", cell)  # greedy: first backtick to last
        if m:
            messages.append(m.group(1).replace("\\`", "`"))
    return messages


def _longest_literal(message: str) -> str:
    """The longest placeholder-free, normalised fragment of an error message."""
    parts = [_norm_msg(p) for p in _PLACEHOLDER.split(message)]
    return max(parts, key=len, default="")


_ERROR_ROWS = [(_longest_literal(m), m) for m in _error_table_messages()]
_SRC_NORM = _norm_src(_SRC_PY)


@pytest.mark.parametrize(
    "fragment,message", _ERROR_ROWS, ids=[m[:45] for _f, m in _ERROR_ROWS]
)
def test_reference_error_string_exists_in_source(fragment: str, message: str) -> None:
    if message in _EXEMPT_ERROR_MESSAGES or len(fragment) < 10:
        pytest.skip("no distinctive literal fragment to anchor on")
    assert fragment in _SRC_NORM, (
        f"docs/REFERENCE.md error table lists {message!r} but its literal part "
        f"{fragment!r} no longer appears in src/ — a reworded error string. "
        f"Update the table (or add to _EXEMPT_ERROR_MESSAGES if it's a library string)."
    )


def test_error_table_was_actually_parsed() -> None:
    # Guard against the parser silently matching nothing (then the test above is a no-op).
    assert len(_ERROR_ROWS) >= 10
