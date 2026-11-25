---
id: heatmap
name: Heatmap
origin: munzner
group: keys
order: 110
kind: idiom
form: encoding
medium: [static, interactive]
shape: 2-keys
data:
  keys: [{type: categorical}, {type: categorical}]
  values: [{type: quantitative}]
  optional: []
tasks: [clusters-outliers, relationship]
marks: [{level: 1, mark: point}]
channels:
  encoded:
    - {channel: position-common, carries: first key, where: vertical}
    - {channel: position-common, carries: second key, where: horizontal}
    - {channel: luminance, carries: value, where: ordered diverging colour map}
  uniform: [{channel: size}, {channel: shape, where: symbol}, {channel: tilt, where: orientation}]
  varying: []
  inherited: []
scale:
  items: {max: 1000000}
  value_levels: {max: 10}
  note: Highly asymmetric, with hundreds of key levels and up to a million items, but only about ten levels of the value (Layout p. 30).
see_also:
  - id: scatterplot
    when: The two attributes are quantitative values rather than keys.
  - id: stacked-bar
    when: One key has only a few levels and the totals for the other key matter.
  - id: bar-chart
    when: Exact values matter more than patterns, since bar heights read far more precisely than colour.
  - id: status-matrix
    when: Each cell holds a categorical status, such as treated or not, rather than a quantity.
sources: [Layout p. 30, Layout p. 31]
---

## Helps
Finds outliers, and clusters when the rows and columns are well ordered (Layout p. 30). Rows and columns can be ordered by name or by a derived attribute, a data-driven clustering (Layout p. 31). In Munzner's example of correlations among car variables, the clustered order gathers eight variables into one block and moves the two mileage variables to the end, where they correlate negatively with the rest (Layout p. 31). Our reading: a correlation matrix (Layout p. 31) shows how every pair of attributes relates.

## Hides
Only about ten levels of the value can be told apart, though the keys can have hundreds of levels (Layout p. 30). Our reading: exact values are hard to read from colour, so labels or tooltips are needed when they matter. Our reading: a red-green colour map, as in Munzner's gene example, is hard to read for many colour-blind viewers. Our reading: alphabetical order can hide clusters that a data-driven order shows.

## Arrange
The cells form a matrix, with one key along each axis and one cell per pair of key levels; cells share borders and do not overlap (Layout p. 30). The value is shown by colour on an ordered diverging colour map (Layout p. 30). A reordered correlation matrix is a variant: rows and columns are the same variables, and each cell shows their correlation on a scale from -1 to 1 (Layout p. 31).
