import near_copy
from near_copy import at_level, bodies, listed, pairs, similarity


def one(rel, text):
    (b,) = bodies(rel, text)
    return b


def test_local_names_and_values_are_set_aside_in_python():
    a = one("a.py", "def pool(d, k=20):\n    keep = d.groupby('charge').size()\n    return d[d.n > k * 1.5]\n")
    b = one("b.py", "def pool30(x, m=30):\n    n = x.groupby('court').size()\n    return x[x.n > m * 2.5]\n")
    assert a.tokens == b.tokens and similarity(a.tokens, b.tokens) == 1.0


def test_calls_attributes_and_keyword_names_are_kept():
    mean = one("a.py", "def f(df):\n    return df['x'].mean()\n")
    total = one("b.py", "def g(df):\n    return df['x'].sum()\n")
    assert mean.tokens != total.tokens
    kw_a = one("a.py", "def f(d):\n    return d.dropna(how='any')\n")
    kw_b = one("b.py", "def g(d):\n    return d.dropna(subset='any')\n")
    assert kw_a.tokens != kw_b.tokens


def test_the_docstring_and_the_name_are_dropped():
    a = one("a.py", 'def first(x):\n    """Says what it does."""\n    return x + 1\n')
    b = one("b.py", "def second(y):\n    return y + 7\n")
    assert a.tokens == b.tokens


def test_methods_are_named_by_their_class():
    found = bodies("a.py", "class Pool:\n    def load(self):\n        return 1\n\ndef top():\n    return 2\n")
    assert [(b.name, b.line) for b in found] == [("Pool.load", 2), ("top", 5)]


def test_r_functions_with_braces_one_expression_and_lambdas():
    text = ("pool <- function(d, min_cases) {\n  keep <- table(d$charge)\n  d[d$charge %in% names(keep[keep >= min_cases]), ]\n}\n"
            "fmt = function(x, digits = 3) formatC(x, format = 'f', digits = digits)\n"
            "sq <- \\(x) x^2\n"
            "not_a_function <- 3\n")
    found = bodies("a.R", text)
    assert [(b.name, b.line) for b in found] == [("pool", 1), ("fmt", 5), ("sq", 6)]
    fmt = found[1]
    assert "formatC" in fmt.tokens and "format=" in fmt.tokens and "digits=" in fmt.tokens and "V" in fmt.tokens


def test_r_columns_named_arguments_and_booleans():
    a = one("a.R", "f <- function(d) {\n  s <- sum(d$cases, na.rm = TRUE)\n  s / 12\n}\n")
    b = one("b.R", "g <- function(x) {\n  t <- sum(x$cases, na.rm = FALSE)\n  t / 7\n}\n")
    c = one("c.R", "h <- function(x) {\n  t <- sum(x$deaths, na.rm = FALSE)\n  t / 7\n}\n")
    assert a.tokens == b.tokens and "$cases" in a.tokens and "na.rm=" in a.tokens and "B" in a.tokens
    assert a.tokens != c.tokens


def test_r_strings_comments_and_nested_functions():
    text = ('f <- function(x) {\n  # a comment with function( and { in it\n  g <- function(y) y + 1\n'
            '  paste0("}", g(x), r"(a ) " b)")\n}\nh <- function() 2\n')
    assert [b.name for b in bodies("a.R", text)] == ["f", "h"]


def test_distinct_on_the_definition_line():
    assert one("a.py", "def f(x):  # distinct: rounds half away from zero\n    return x\n").distinct
    assert not one("a.py", "def f(x):  # distinct:\n    return x\n").distinct
    assert one("a.R", "f <- function(x) {  # distinct: the legacy panel, kept for one figure\n  x\n}\n").distinct


def test_the_levels():
    assert at_level(0.95, 10) and not at_level(0.94, 29) and at_level(0.9, 30) and not at_level(0.89, 100)
    assert listed(0.8, 30) and not listed(0.8, 29) and listed(0.96, 10)


def test_averages_of_three_and_four_are_alike_but_too_small_to_block():
    a = one("a.py", "def avg3(a, b, c):\n    return (a + b + c) / 3\n")
    b = one("b.py", "def avg4(a, b, c, d):\n    return (a + b + c + d) / 4\n")
    r = similarity(a.tokens, b.tokens)
    assert 0.85 < r < 0.95 and len(a.tokens) < 30
    assert near_copy.matches(b, [a]) == []          # left to the number rule (the typed 3 and 4) and review


def test_pairs_are_found_once_and_matches_are_closest_first():
    base = "def f{n}(d, k):\n    keep = d.groupby('charge').size()\n    d = d[d.charge.isin(keep[keep >= k].index)]\n" \
           "    d['female'] = d.sex == 'F'\n    return d{extra}\n"
    a = one("a.py", base.format(n=1, extra=""))
    b = one("b.py", base.format(n=2, extra=""))
    c = one("c.py", base.format(n=3, extra=".dropna()"))
    found = pairs([a, b, c])
    assert len(found) == 3 and all(x is not y for _, x, y in found)
    hits = near_copy.matches(a, [b, c])
    assert [o.file for _, o in hits] == ["b.py", "c.py"] and hits[0][0] == 1.0


def test_python_that_does_not_parse_has_no_bodies():
    assert bodies("a.py", "def f(:\n") == []


def test_an_unclosed_r_string_costs_one_pass_not_an_exponential_search():
    import time
    tail = "".join(f'lab{i} <- "Don\'t know"\n' for i in range(40))
    text = 'q <- "SELECT * \\\nFROM t"\nf <- function(x) {\n  x + 1\n}\nbad <- "never closed\n' + tail + \
        "g <- function(y) y\n"
    start = time.monotonic()
    found = bodies("a.R", text)
    assert time.monotonic() - start < 1
    assert "f" in [b.name for b in found]                     # the backslash-newline string doesn't derail it


def test_an_r_raw_string_closes_only_on_its_own_bracket():
    text = 'x <- r"(a]" b)"\nf <- function(d) {\n  d\n}\n'
    assert [b.name for b in bodies("a.R", text)] == ["f"]


def test_r_one_expression_bodies_continue_after_an_operator_and_stop_at_a_semicolon():
    found = bodies("a.R", "f <- function(d) d |>\n  filter(x > 1) |>\n  head()\nk <- 3\n"
                          "g <- function(x) x; h <- function(y) y\n")
    assert [b.name for b in found] == ["f", "g", "h"]
    assert "filter" in found[0].tokens and "head" in found[0].tokens and "k" not in found[0].tokens


def test_deeply_nested_python_is_skipped_not_a_crash():
    branches = "".join(f"    elif x == {i}:\n        y = {i}\n" for i in range(1500))
    text = "def deep(x):\n    if x == 0:\n        y = 0\n" + branches + "    return y\n\ndef ok(x):\n    return x\n"
    assert "ok" in [b.name for b in bodies("a.py", text)]


def test_python_columns_are_kept_like_r_columns():
    a = one("a.py", "def f(d):\n    return d['income'].groupby(d['year']).mean()\n")
    b = one("b.py", "def g(d):\n    return d['age'].groupby(d['year']).mean()\n")
    assert "$income" in a.tokens and a.tokens != b.tokens


def test_distinct_is_found_after_a_form_feed():
    assert one("a.py", "x = 1\n\x0c\ndef f(x):  # distinct: the legacy rule\n    return x\n").distinct == "the legacy rule"
    assert one("a.R", "x <- 1\n\x0c\nf <- function(x) {  # distinct: the legacy rule\n  x\n}\n").distinct


def test_entry_points_and_very_long_functions_are_not_compared():
    a = one("a.py", "def main():\n    run(load(param('x')), param('y'), param('z'))\n")
    b = one("b.py", "def main():\n    run(load(param('a')), param('b'), param('c'))\n")
    assert near_copy.matches(a, [b]) == []
    long_body = "".join(f"    x{i} = f(x{i - 1}, {i})\n" for i in range(1, 400))
    c = one("c.py", "def big(x0):\n" + long_body + "    return x0\n")
    d = one("d.py", "def big2(x0):\n" + long_body + "    return x0\n")
    assert len(c.tokens) > near_copy.MAX_TOKENS and near_copy.matches(c, [d]) == []


def test_an_r_raw_string_closes_only_on_its_own_quote():
    text = "x <- r\"(it's)' more)\"\nf <- function(d) {\n  d\n}\n"
    found = bodies("a.R", text)
    assert [b.name for b in found] == ["f"]
