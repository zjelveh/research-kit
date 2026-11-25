---
id: dot-plot
name: Dot plot
origin: kit
group: keys
order: 60
kind: idiom
form: encoding
medium: [static]
shape: 1-key
data:
  keys: [{type: categorical}]
  values: [{type: quantitative}]
  optional: [{type: quantitative, channel: position-common}, {type: categorical, channel: hue}]
tasks: [compare-values, lookup]
marks: [{level: 1, mark: point}]
channels:
  encoded:
    - {channel: position-common, carries: key, where: one axis at equal intervals}
    - {channel: position-common, carries: value, where: the other axis}
  uniform: [{channel: size, where: point size}, {channel: hue}, {channel: shape}]
  varying: []
  inherited: []
scale: {note: null}
see_also:
  - id: bar-chart
    when: The values are amounts with a meaningful zero, and the ratios between them matter.
  - id: interval-plot
    when: Each value is an estimate with an interval.
  - id: slopegraph
    when: Each item has two values, and the change between them in value or rank is the message.
  - id: gantt-chart
    when: The two values of a dumbbell are a start and an end in time.
sources: [Layout p. 18, Layout p. 19, Layout p. 25, Layout p. 26, Marks p. 9, Marks p. 22]
---

## Helps
Our reading: compares values across the levels of one categorical key, as a bar chart does, when zero is not a useful baseline or the values lie close together. Each value is a point placed by position on a common scale, the channel Munzner ranks most effective for ordered values (Marks p. 9). Our reading: a point leaves room for more points in the same row, so two or more values per key level can share it, told apart by hue or shape.

## Hides
Our reading: with no bar from zero, the eye judges where each value lies rather than how large it is, so ratios between values are hard to read, and an axis that starts far from zero can make small differences look large. A categorical key needs an ordering: by name, which is good for lookup but hides trends and the distribution, or by a value used elsewhere in the encoding (Layout p. 18). Our reading: with several points per row, points with equal values hide one another unless their shapes differ or they are offset slightly.

## Arrange
A list along one axis, one key level at equal intervals as in a bar chart, with the value on the other axis (Layout p. 19). Munzner's rule for chart axes is to include zero, except when zero is arbitrary or a small change matters (Layout pp. 25, 26). Munzner groups lollipop charts with bar charts: both guide readers to judge each mark's vertical height (Marks p. 22). Our reading: a dot plot drops the stem and draws no length, so its value axis may start elsewhere; a lollipop chart, whose stem runs from the baseline, should include zero as a bar chart does. Our reading: the dumbbell is a variant with two points per key level joined by a line, for two related values such as before and after; the line shows the gap between them.
