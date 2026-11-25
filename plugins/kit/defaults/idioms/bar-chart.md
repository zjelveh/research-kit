---
id: bar-chart
name: Bar chart
origin: munzner
group: keys
order: 20
kind: idiom
form: encoding
medium: [static, interactive]
shape: 1-key
data:
  keys: [{type: categorical}]
  values: [{type: quantitative}]
  optional: [{type: categorical, channel: hue}]
tasks: [compare-values, lookup]
marks: [{level: 1, mark: point}]
channels:
  encoded:
    - {channel: position-common, carries: key, where: horizontal at equal intervals}
    - {channel: position-common, carries: value, where: top of each bar}
    - {channel: length, carries: value, where: bar height}
  uniform: [{channel: size, where: bar width}, {channel: hue}, {channel: shape}]
  varying: []
  inherited: []
scale: {note: Dozens to hundreds of key levels and hundreds of value levels (Layout p. 19).}
see_also:
  - id: line-chart
    when: The key is ordered, such as time (Layout p. 23).
  - id: interval-plot
    when: Each value is an estimate with an interval, or the axis need not start at zero.
sources: [Layout p. 18, Layout p. 19, Layout p. 23, Layout p. 25, Layout p. 26, Marks p. 22, Interact p. 49]
---

## Helps
Compares and looks up values across the levels of one categorical key (Layout p. 19). Bars guide readers to judge each mark's height (Marks p. 22). Our reading: sorted by value, the bars also show how the values are distributed.

## Hides
In alphabetical order the bars are easy to look up by name, but trends and the distribution are hard to see; extremes are easy to find in any order, middle ranks are not (Layout p. 18). A value axis that does not include zero misleads (Layout p. 25), unless zero is arbitrary or a small change matters (Layout p. 26). Our reading: a bar's length is its value, so cutting the axis changes the ratios a reader sees between bars. Reading the bars' horizontal positions is possible but difficult (Marks p. 22).

## Arrange
A list of bars along one axis, one per key level at equal intervals; bars share no borders and do not overlap (Layout p. 19). A categorical key needs an ordering: by name, or by a value shown elsewhere in the figure (Layout p. 18). A second categorical key can group bars within each level of the first, which makes comparison easy within a level and hard across levels, or split the chart into small multiples, one per level (Interact p. 49).
