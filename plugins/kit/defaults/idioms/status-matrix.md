---
id: status-matrix
name: Status matrix
origin: kit
group: keys
order: 130
kind: idiom
form: encoding
medium: [static]
shape: 2-keys
data:
  keys: [{type: categorical}, {type: categorical}]
  values: [{type: categorical}]
  optional: []
tasks: [lookup, trend, clusters-outliers]
marks: [{level: 1, mark: point}]
channels:
  encoded:
    - {channel: position-common, carries: first key, where: vertical (rows)}
    - {channel: position-common, carries: second key, where: horizontal (columns)}
    - {channel: hue, carries: status, where: cell colour}
  uniform: [{channel: size, where: cell size}, {channel: shape}]
  varying: []
  inherited: []
scale:
  note: >-
    Our reading: hundreds of levels for each key, as in a heatmap, but only a few statuses, since each
    needs a hue that can be told apart.
see_also:
  - id: heatmap
    when: The cell value is quantitative or ordered, such as the time since treatment.
  - id: gantt-chart
    when: Each unit has one span, a start and an end, over many periods.
  - id: stacked-bar
    when: The number of units in each status per period matters more than which units they are.
sources: [Layout p. 18, Layout p. 29, Layout p. 30, Layout p. 31, Marks p. 9]
---

## Helps
Our reading: shows the status of every unit in every period at once, such as when each unit is treated, so the timing across units can be seen and any one cell looked up. Munzner's heatmap, which has the same layout, serves to find outliers, and clusters when the rows and columns are well ordered (Layout p. 30). Our reading: with the units sorted by the period in which their status first changes, a staggered rollout shows as a staircase, and a unit that switches back stands out. A categorical status suits hue, an identity channel for categorical attributes (Marks p. 9).

## Hides
Our reading: hue shows no order and only a few levels can be told apart, so an ordered status or one with many levels, such as the time since treatment, belongs in a heatmap. The levels a channel can show must match the levels in the data (Marks p. 9). Munzner contrasts a heatmap ordered by attribute name with one ordered by a derived attribute, a data-driven clustering (Layout p. 31). Our reading: in an arbitrary order, such as by name, the timing pattern can disappear. Our reading: the cells show only the status, so the chart describes the design, such as who is treated when, and nothing of the outcome.

## Arrange
A matrix, Munzner's layout for two keys, with one key along each axis and one cell per pair of key levels; as in a heatmap, the cells are point marks that share borders and do not overlap (Layout pp. 29, 30). Each key needs an ordering, by name or by a value used elsewhere in the encoding (Layout p. 18). A heatmap colours each cell by a quantitative value on an ordered diverging colour map (Layout p. 30). Our reading: the status matrix keeps that layout and puts a categorical status on hue instead, with units usually in the rows and periods in the columns.
