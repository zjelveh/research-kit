---
id: parallel-coordinates
name: Parallel coordinates
origin: munzner
group: orientation
order: 320
kind: idiom
form: encoding
medium: [static, interactive]
shape: 0-keys
data:
  keys: []
  values: [{type: quantitative}, {type: quantitative}, {type: quantitative, repeats: true}]
  optional: [{type: categorical, channel: hue}]
tasks: [relationship]
marks: [{level: 1, mark: line}]
channels:
  encoded:
    - {channel: position-common, carries: each attribute's value, where: vertical position on that attribute's axis}
    - {channel: connection, carries: one item across all its attributes, where: path meeting each axis at the value}
  uniform: [{channel: size, where: line thickness}]
  varying: [{channel: length, where: each segment's length by its slope}]
  inherited: []
scale: {note: Dozens of attributes and hundreds of items (Layout p. 49).}
see_also:
  - id: splom
    when: There are fewer attributes and each item can be a point in every pair's scatterplot (Layout p. 49).
  - id: slopegraph
    when: There are only two attributes; a slopegraph is the two-axis case (Layout p. 52).
  - id: radar-chart
    when: The axes are levels of one cyclic key and belong around a circle.
sources: [Layout p. 48, Layout p. 49, Layout p. 50, Layout p. 51, Layout p. 52, Layout p. 54]
---

## Helps
Shows correlation between neighbouring axes: a positive correlation as parallel segments, a negative one as segments that all cross halfway between the axes, and no correlation as scattered crossings (Layout p. 50). Lining up the axes in parallel shows many attributes at once, where orthogonal axes show only two (Layout pp. 48, 49). Our reading: each item can be followed across all the attributes as one line, so items with similar profiles form bundles of similar lines.

## Hides
Patterns are visible only between neighbouring pairs of axes (Layout p. 51). So the order of the axes matters: reorderable axes allow interactive exploration but leave the search to people, and the algorithms proposed so far do not fully solve it (Layout p. 51). Parallel axes cost unfamiliarity and training time (Layout p. 54). Our reading: each axis usually has its own scale, so heights cannot be compared from one axis to the next, and many crossing lines are hard to follow one at a time.

## Arrange
One axis per attribute, lined up in parallel, with each value at a vertical position on its axis (Layout p. 49). Each item is a single jagged path, piecewise linear between axes, where a scatterplot matrix would draw it as a point in every cell; the segments vary in length with their slope (Layout p. 49). In Munzner's small example, colour picks out two of the five items, matching their rows in the table (Layout p. 49). In the Wegman figure Munzner uses for correlation, the axes run horizontally, one above another (Layout p. 50). Our reading: the lines share no borders and overlap.
