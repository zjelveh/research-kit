---
id: gantt-chart
name: Gantt chart
origin: munzner
group: keys
order: 330
kind: idiom
form: encoding
medium: [static, interactive]
shape: 1-key
data:
  keys: [{type: categorical}]
  values: [{type: quantitative}, {type: quantitative}]
  optional: []
tasks: [relationship]
marks: [{level: 1, mark: point}]
channels:
  encoded:
    - {channel: position-common, carries: start time, where: horizontal; left end of each bar}
    - {channel: position-common, carries: end time, where: horizontal; right end of each bar}
    - {channel: length, carries: duration, where: bar width}
    - {channel: position-common, carries: key, where: vertical in alphanumeric order}
  uniform: [{channel: size, where: bar thickness}]
  varying: null
  inherited: []
scale:
  note: Dozens of key levels for the bars and hundreds of value levels for the times and durations (Layout p. 28).
see_also:
  - id: bar-chart
    when: Each item has one value rather than a start and an end, and aligned bars compare more precisely.
  - id: line-chart
    when: The question is how a quantity changes over time, not when items start and end.
sources: [Layout p. 28]
---

## Helps
Brings out temporal overlaps between items, and dependencies between their starts and ends (Layout p. 28). Our reading: that is, which items run at the same time, and which start when another ends. Each bar's width encodes its duration, end minus start, redundantly with the two times (Layout p. 28).

## Hides
Our reading: the bars do not start from a shared baseline, so durations are harder to compare than bar heights in a bar chart. Our reading: dependencies are only implied by position unless links between bars are drawn. Munzner rates the idiom at dozens of bars (Layout p. 28).

## Arrange
Time runs along the horizontal axis, and items are listed vertically, in alphanumeric order by name (Layout p. 28). Each item is one bar from its start time to its end time; bars share no borders and do not overlap (Layout p. 28).
