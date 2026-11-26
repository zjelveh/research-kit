"""Near copies among functions (near-copy spec): two functions that are the same once their local names and
typed values are set aside, so that one function with an argument would do for both.

Each function becomes a token sequence: local names (arguments and assigned names) become V, numbers N,
strings S and booleans B; calls, attributes, column names (R `d$x`, Python `d["x"]`), keyword-argument names
and operators are kept, and the function's own name and docstring are dropped. Two sequences are compared with
difflib's ratio.
"""
from __future__ import annotations

import ast
import difflib
import re
from dataclasses import dataclass, field

from code_scan import ENTRY_POINTS, lines_of, parse_python, split_comment

# Measured on two projects' code (spec section 2): 48 of 48 sampled pairs at these levels were copies to merge.
BLOCK = ((0.95, 10), (0.9, 30))          # (similarity, smallest size in tokens) at which the gate blocks
LIST = ((0.8, 30),)                      # and the extra level the map lists for review
# difflib's exact ratio grows faster than linearly with length (about 1 s for a pair of 2,000 tokens), so
# longer functions, about 200 lines, are left out
MAX_TOKENS = 2000
DISTINCT = re.compile(r"\bdistinct:\s*(\S.*)")


@dataclass(eq=False)                      # compared by identity, so it can key a dict
class Body:
    name: str
    file: str
    line: int
    tokens: list[str] = field(repr=False)
    distinct: str = ""                    # the reason after `# distinct:` on the definition line, if any


def at_level(ratio: float, size: int, levels=BLOCK) -> bool:
    return any(ratio >= r and size >= n for r, n in levels)


def listed(ratio: float, size: int) -> bool:
    return at_level(ratio, size, BLOCK) or at_level(ratio, size, LIST)


def comparable(b: Body) -> bool:
    """Compared at all: not a driver's entry point, and not too long to compare."""
    return b.name.rsplit(".", 1)[-1] not in ENTRY_POINTS and len(b.tokens) <= MAX_TOKENS


def _distinct(first_line: str) -> str:
    m = DISTINCT.search(split_comment(first_line)[1])
    return m.group(1).strip() if m else ""


# ---------- Python ----------

class _PyTokens(ast.NodeVisitor):
    def __init__(self, local: set[str]):
        self.local, self.out = local, []

    def generic_visit(self, node):
        if isinstance(node, ast.expr_context):
            return
        if isinstance(node, ast.Name):
            self.out.append("V" if node.id in self.local else node.id)
            return
        if isinstance(node, ast.Constant):
            v = node.value
            self.out.append("B" if isinstance(v, bool) else "N" if isinstance(v, (int, float, complex))
                            else "S" if isinstance(v, (str, bytes)) else repr(v))
            return
        if isinstance(node, ast.JoinedStr):
            self.out.append("S")
            return
        self.out.append(type(node).__name__)
        if isinstance(node, ast.Attribute):
            self.visit(node.value)
            self.out.append("." + node.attr)
            return
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) \
                and isinstance(node.slice.value, str):
            self.visit(node.value)
            self.out.append("$" + node.slice.value)           # a column, as R's d$x
            return
        if isinstance(node, ast.keyword):
            self.out.append((node.arg or "**") + "=")
        super().generic_visit(node)


def _py_locals(fn: ast.AST) -> set[str]:
    names = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.arg):
            names.add(n.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            names.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n is not fn:
            names.add(n.name)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            names.add(n.name)
    return names


def _py_body(rel: str, fn, qual: str, lines: list[str]) -> Body | None:
    body = fn.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    v = _PyTokens(_py_locals(fn))
    try:
        v.visit(fn.args)
        for s in body:
            v.visit(s)
    except RecursionError:                # nested too deeply to walk (hundreds of elif branches): not compared
        return None
    return Body(qual, rel, fn.lineno, v.out, _distinct(lines[fn.lineno - 1] if fn.lineno <= len(lines) else ""))


def python_bodies(rel: str, text: str) -> list[Body]:
    """Top-level functions and the methods of top-level classes."""
    try:
        tree = parse_python(text)
    except RecursionError:
        return []
    if tree is None:
        return []
    lines, out = lines_of(text), []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(_py_body(rel, node, node.name, lines))
        elif isinstance(node, ast.ClassDef):
            out += [_py_body(rel, m, f"{node.name}.{m.name}", lines) for m in node.body
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return [b for b in out if b is not None]


# ---------- R ----------

# Every alternative consumes at least one character and no two can match the same text, so a quote that never
# closes costs one pass to the end of the file, not an exponential search.
R_TOKEN = re.compile(r"""
  (?P<nl>\n) | (?P<ws>[ \t\r\f\v]+) | (?P<comment>\#[^\n]*)
| (?P<raw>[rR](?P<quote>["'])(?P<dashes>-*)(?:\((?:[^)]|\)(?!(?P=dashes)(?P=quote)))*\)
                                            |\[(?:[^\]]|\](?!(?P=dashes)(?P=quote)))*\]
                                            |\{(?:[^}]|\}(?!(?P=dashes)(?P=quote)))*\})(?P=dashes)(?P=quote))
| (?P<str>"(?:[^"\\]|\\[\s\S])*"|'(?:[^'\\]|\\[\s\S])*')
| (?P<name>`[^`]*`)
| (?P<num>0[xX][0-9a-fA-F]+[Li]?|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?[Li]?)
| (?P<id>[A-Za-z.][A-Za-z0-9._]*)
| (?P<op><<-|->>|<-|->|<=|>=|==|!=|&&|\|\||\|>|:::|::|%[^%\n]*%|\\|[-+*/^~!&|<>=?:$@(){}\[\],;])
""", re.X)
R_BOOL = {"TRUE", "FALSE", "T", "F"}
OPEN, CLOSE = "([{", ")]}"
# a line that ends in one of these continues on the next (R's parser does the same)
R_CONTINUES = {"|>", "+", "-", "*", "/", "^", "&", "|", "&&", "||", "<-", "<<-", "->", "->>", "=", "==", "!=", "<",
               ">", "<=", ">=", "~", ",", "!", "$", "@", ":", "::", ":::"}


def _r_tokens(text: str) -> list[tuple[str, str, int]]:
    """(kind, text, line) for each token, comments and spaces left out; kind is nl, str, num, id or op."""
    out, i, line = [], 0, 1
    while i < len(text):
        m = R_TOKEN.match(text, i)
        if m is None:            # a character R wouldn't parse, or a quote that never closes: keep it as an operator
            out.append(("op", text[i], line))
            line += text[i] == "\n"
            i += 1
            continue
        kind = {"raw": "str", "name": "id"}.get(m.lastgroup, m.lastgroup)
        if kind not in ("ws", "comment"):
            out.append((kind, m.group(), line))
        line += m.group().count("\n")
        i = m.end()
    return out


def _close(toks: list, i: int) -> int:
    """The index of the bracket that closes the one at i."""
    depth = 0
    for j in range(i, len(toks)):
        kind, t, _ = toks[j]
        if kind == "op" and t in OPEN:
            depth += 1
        elif kind == "op" and t in CLOSE:
            depth -= 1
            if depth == 0:
                return j
    return len(toks) - 1


def _expression_end(toks: list, b: int) -> int:
    """The last token of the expression that starts at b: its line, and the lines after one that ends in an
    operator or inside brackets; a `;` at the top ends it."""
    depth, j = 0, b
    while j < len(toks):
        kind, t, _ = toks[j]
        if kind == "op" and t in OPEN:
            depth += 1
        elif kind == "op" and t in CLOSE:
            depth -= 1
        elif depth <= 0 and ((kind == "op" and t == ";") or
                             (kind == "nl" and not (j > b and toks[j - 1][0] == "op" and
                                                    (toks[j - 1][1] in R_CONTINUES or
                                                     toks[j - 1][1].startswith("%"))))):
            break
        j += 1
    return j - 1


def _r_locals(formals: list, body: list) -> set[str]:
    names, depth = set(), 0
    for k, (kind, t, _) in enumerate(formals):
        if kind == "op" and t in OPEN:
            depth += 1
        elif kind == "op" and t in CLOSE:
            depth -= 1
        elif kind == "id" and depth == 0 and (k == 0 or formals[k - 1][1] == ","):
            names.add(t.strip("`"))
    stack = []
    for k, (kind, t, _) in enumerate(body):
        if kind == "op" and t in OPEN:
            stack.append(t)
        elif kind == "op" and t in CLOSE:
            stack and stack.pop()
        elif kind == "id" and k + 1 < len(body):
            before, after = body[k - 1][1] if k else "", body[k + 1][1]
            if before in ("$", "@", "::", ":::"):
                continue
            if after in ("<-", "<<-") or (after == "=" and (not stack or stack[-1] == "{")) \
                    or before in ("->", "->>") or (k >= 2 and body[k - 2][1] == "for"):
                names.add(t.strip("`"))
    return names


def _r_sequence(toks: list, local: set[str]) -> list[str]:
    out, stack = [], []
    for k, (kind, t, _) in enumerate(toks):
        if kind == "op" and t in OPEN:
            stack.append(t)
        elif kind == "op" and t in CLOSE:
            stack and stack.pop()
        if kind == "num":
            out.append("N")
        elif kind == "str":
            out.append("S")
        elif kind == "id":
            before = toks[k - 1][1] if k else ""
            after = toks[k + 1][1] if k + 1 < len(toks) else ""
            name = t.strip("`")
            if name in R_BOOL:
                out.append("B")
            elif before in ("$", "@"):
                out.append("$" + name)
            elif after == "=" and stack and stack[-1] in "([":
                out.append(name + "=")              # an argument's name, not a variable
            else:
                out.append("V" if name in local else name)
        else:
            out.append(t)
    return out


def r_bodies(rel: str, text: str) -> list[Body]:
    """Top-level `name <- function(...)` (or `=`, or `\\(...)`) definitions."""
    toks = _r_tokens(text)
    lines, out, depth, i = lines_of(text), [], 0, 0
    while i < len(toks):
        kind, t, line = toks[i]
        if kind == "op" and t in OPEN:
            depth += 1
        elif kind == "op" and t in CLOSE:
            depth = max(0, depth - 1)
        elif depth == 0 and kind == "id" and i + 1 < len(toks) and toks[i + 1][1] in ("<-", "=", "<<-"):
            j = i + 2
            while j < len(toks) and toks[j][0] == "nl":
                j += 1
            if j + 1 < len(toks) and toks[j][1] in ("function", "\\") and toks[j + 1][1] == "(":
                end_formals = _close(toks, j + 1)
                b = end_formals + 1
                while b < len(toks) and toks[b][0] == "nl":
                    b += 1
                end = _close(toks, b) if b < len(toks) and toks[b][1] == "{" else _expression_end(toks, b)
                formals = [x for x in toks[j + 2:end_formals] if x[0] != "nl"]
                body = [x for x in toks[b:end + 1] if x[0] != "nl"]
                local = _r_locals(formals, body)
                out.append(Body(t.strip("`"), rel, line,
                                _r_sequence(formals, local) + ["|"] + _r_sequence(body, local),
                                _distinct(lines[line - 1] if line <= len(lines) else "")))
                i = end + 1
                continue
        i += 1
    return out


def bodies(rel: str, text: str) -> list[Body]:
    return python_bodies(rel, text) if rel.endswith(".py") else r_bodies(rel, text)


# ---------- comparison ----------

def similarity(a: list[str], b: list[str]) -> float:
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def matches(new: Body, others: list[Body], levels=BLOCK) -> list[tuple[float, Body]]:
    """The functions in `others` that `new` is a near copy of at `levels`, closest first."""
    if not comparable(new):
        return []
    lowest = min(r for r, _ in levels)
    sm = difflib.SequenceMatcher(None, autojunk=False)
    sm.set_seq2(new.tokens)
    out = []
    for o in others:
        size = min(len(new.tokens), len(o.tokens))
        if o is new or not comparable(o) or not any(size >= n for _, n in levels):
            continue
        sm.set_seq1(o.tokens)
        # ratio is at most 2 * shorter / (both lengths); the quick bounds come before the exact one
        if sm.real_quick_ratio() < lowest or sm.quick_ratio() < lowest:
            continue
        r = sm.ratio()
        if at_level(r, size, levels):
            out.append((r, o))
    return sorted(out, key=lambda x: (-x[0], x[1].file, x[1].line))


def pairs(funcs: list[Body], levels=BLOCK) -> list[tuple[float, Body, Body]]:
    """Every pair at `levels`, each once. Sizes are compared first: a pair whose lengths differ too much can't
    reach the lowest level."""
    lowest = min(r for r, _ in levels)
    order = sorted((f for f in funcs if comparable(f)), key=lambda f: len(f.tokens))
    out = []
    for i, a in enumerate(order):
        later = []
        for b in order[i + 1:]:
            if 2 * len(a.tokens) / (len(a.tokens) + len(b.tokens)) < lowest:
                break
            later.append(b)
        out += [(r, a, b) for r, b in matches(a, later, levels)]
    return out
