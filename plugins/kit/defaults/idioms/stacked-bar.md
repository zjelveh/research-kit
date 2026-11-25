---
id: stacked-bar
name: Stacked bar chart
origin: munzner
group: keys
order: 100
kind: idiom
form: encoding
medium: [static, interactive]
shape: 2-keys
data:
  keys: [{type: categorical}, {type: categorical}]
  values: [{type: quantitative}]
  optional: []
tasks: [part-to-whole, compare-values]
marks: [{level: 1, mark: point}, {level: 2, mark: glyph}]
channels:
  encoded:
    - {channel: position-common, carries: main key, where: horizontal at equal intervals}
    - {channel: length, carries: value, where: segment height}
    - {channel: hue, carries: second key}
    - {channel: position-common, carries: value of the lowest segment, where: vertical}
  uniform: [{channel: size, where: segment width}, {channel: position-common, where: horizontal position within a bar}]
  varying: [{channel: position-common, where: vertical position of every segment above the lowest}]
  inherited: [{channel: hue, where: whole bar at level 2}]
scale:
  second_key_levels: {max: 12}
  note: Asymmetric, with 10 to 12 levels for the stacked key and dozens to hundreds for the main key (Layout p. 20).
see_also:
  - id: streamgraph
    when: The stacked key has dozens to hundreds of levels across time (Layout p. 21).
  - id: bar-chart
    when: There is no second key, or only the totals matter.
  - id: heatmap
    when: Both keys have many levels and patterns across all pairs matter more than exact values.
  - id: normalized-stacked-bar
    when: Only the shares matter, so each bar is stretched to full height and relative sizes show proportions (Layout p. 44).
sources: [Layout p. 20, Layout p. 21, Layout p. 44, Marks p. 23, Marks p. 24]
---

## Helps
Shows the part-to-whole relationship between each bar and its segments (Layout p. 20). It adds one more key to the bar chart: each value is indexed by a pair of key levels, such as a species and a condition (Layout p. 20). Each whole bar is a glyph that reads like a bar in a normal bar chart (Layout p. 20). Our reading: the totals therefore compare across bars, and the bottom segments, which share the baseline, compare as easily as plain bars.

## Hides
Only the lowest segment's vertical position encodes its value; for every segment above it, vertical position varies without encoding data (Layout p. 20). Our reading: comparing one level of the second key across bars is therefore hard for any segment above the bottom. The segments touch, so one cannot move, grow or change shape on its own without affecting the others (Marks pp. 23, 24).

## Arrange
Bars form a list along one axis, one per level of the main key as in a normal bar chart, and segments stack by the second key within each bar (Layout p. 20). Segments share borders along the vertical only and do not overlap (Layout p. 20). Munzner orders the upper segments alphabetically by the second key's level names (Layout p. 20). Our reading: the example figure on that page stacks its segments in another order, so the order is a choice; the level that most needs comparing belongs on the baseline.
