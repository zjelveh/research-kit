---
id: dense-software-overview
name: Dense software overview
origin: munzner
group: density
order: 400
kind: idiom
form: encoding
medium: [static, interactive]
shape: 1-key
data:
  keys: [{type: ordinal}]
  values: [{type: quantitative}, {type: quantitative}, {type: quantitative}]
  optional: []
tasks: [clusters-outliers]
marks: [{level: 1, mark: point}]
channels:
  encoded:
    - {channel: luminance, carries: test results, where: a red-to-green ramp}
    - {channel: position-common, carries: line order in the program, where: vertical within a column}
    - {channel: position-common, carries: first and last character positions, where: horizontal ends of each line}
    - {channel: length, carries: extent of each line, where: line width}
  uniform: [{channel: size, where: line height of one pixel}]
  varying: null
  inherited: []
scale:
  note: 10,000 lines of code or more (Layout p. 57).
see_also:
  - id: heatmap
    when: There are two keys in a matrix, one cell per pair; at one pixel per cell a heatmap is dense too.
  - id: bar-chart
    when: Each line's length is a value to compare from a shared baseline.
sources: [Layout p. 57]
---

## Helps
Shows test results for every line of a large program at once: each line of code is one mark, coloured by its test results, and the layout fits 10,000 lines or more (Layout p. 57). Munzner's example is the Tarantula tool, built to help locate faults in code from test information (Layout p. 57). Our reading: runs of lines with the same result stand out against the rest.

## Hides
Line widths are not aligned: each line starts at its own first character, so its width is its extent, not its last character position (Layout p. 57). Each line is one pixel high by design (Layout p. 57). Our reading: the code itself therefore cannot be read in the overview. Our reading: wrapping into columns splits the program, so lines on either side of a column break end up far apart on screen.

## Arrange
Within each column, lines run down in program order, each placed horizontally from its first to its last character (Layout p. 57). A second, global pass wraps the long vertical list into columns, like scanlines, to fit it into a square (Layout p. 57). Lines share borders along the vertical and do not overlap, and the layout is dense (Layout p. 57).
