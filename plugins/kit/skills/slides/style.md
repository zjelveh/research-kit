# Slide style guide

Applies to every slide in `slides/<talk>/talk.tex`.

1. A figure's own title and axis labels name what is plotted, not the finding. Fix figure titles in the plotting script, as in the paper.
2. No hand-typed numbers or tables. Numbers are macros from the paper's `numbers.tex`, tables are generated files input with `\input{\papertables/<file>}`, and figures come from the paper's `figures/` folder by file name (`\includegraphics{<file>}`); items the manuscript keeps elsewhere are reached by a relative path, never copied. The slides numbers check (`lint_numbers.py --gate slides`) enforces the bare-number part.
3. At most about 6 bullets per slide. More than that is two slides.

## House conventions

The house conventions are a separate file, so each user can set their own; the slides skill says how to find the one in effect.
