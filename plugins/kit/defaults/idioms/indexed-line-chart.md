---
id: indexed-line-chart
name: Indexed line chart
origin: munzner
group: keys
order: 160
kind: idiom
form: encoding
medium: [static, interactive]
shape: 1-key
data:
  keys: [{type: ordinal}]
  values: [{type: quantitative}]
  optional: [{type: categorical, channel: hue}]
tasks: [trend, compare-values]
marks: [{level: 1, mark: line}]
channels:
  encoded:
    - {channel: position-common, carries: key, where: horizontal}
    - {channel: position-common, carries: index, where: vertical}
    - {channel: connection, carries: succession of key levels}
  uniform: [{channel: size, where: line thickness}, {channel: hue, where: single line}]
  varying: []
  inherited: []
scale:
  note: As for a standard line chart, hundreds of levels for both key and value (Layout pp. 22, 27).
see_also:
  - id: line-chart
    when: The absolute values matter, so the original values are plotted.
  - id: slopegraph
    when: Each item has only two time points.
sources: [Layout p. 22, Layout p. 23, Layout p. 26, Layout p. 27]
---

## Helps
Shows change over time on the principle of normalized, not absolute, values (Layout p. 27). Each series is plotted as an index, a value derived from the original and plotted in its place (Layout p. 27). Our reading: series that start at very different levels can then be compared by their change relative to a shared starting point.

## Hides
Our reading: absolute levels disappear, so two series can look the same while one is many times larger than the other. Our reading: the picture depends on the index date, and a different start can change which series looks strongest.

## Arrange
The marks and channels are those of a standard line chart, with the index on the vertical axis in place of the original value (Layout p. 27). The value axis includes zero unless zero is arbitrary or a small change matters (Layout p. 26). In Munzner's example the index date, April 7, 2014, is marked by a vertical line, and the vertical axis runs from 0.2 to 6 times the starting value (Layout p. 27). Our reading: that axis is logarithmic, so doubling and halving cover equal distances; an index is read against its starting value of 1, and a log axis has no zero. Munzner's data line names a quantitative key; any ordered key fits, as for a line chart (Layout pp. 23, 27).
