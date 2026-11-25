---
id: slopegraph
name: Slopegraph
origin: munzner
group: keys
order: 150
kind: idiom
form: encoding
medium: [static, interactive]
shape: 0-keys
data:
  keys: []
  values: [{type: quantitative}, {type: quantitative}]
  optional: [{type: quantitative, channel: size}, {type: categorical, channel: hue}]
tasks: [trend, compare-values]
marks: [{level: 1, mark: line}]
channels:
  encoded:
    - {channel: position-common, carries: first value, where: left vertical axis}
    - {channel: position-common, carries: second value, where: right vertical axis}
    - {channel: connection, carries: pairing of each item's two values}
    - {channel: tilt, carries: change, where: slope of each line}
    - {channel: size, carries: derived change magnitude, where: line thickness}
    - {channel: hue, carries: change direction}
  uniform: []
  varying: [{channel: length, where: line length}]
  inherited: []
scale: {note: Hundreds of value levels and dozens of items (Layout p. 16).}
see_also:
  - id: scatterplot
    when: How the two values relate across items matters more than each item's change.
  - id: line-chart
    when: Each item has more than two time points.
  - id: indexed-line-chart
    when: Several series are compared by their relative change over many time points.
  - id: parallel-coordinates
    when: Each item has more than two values, since a slopegraph is parallel coordinates with only two axes (Layout p. 52).
sources: [Layout p. 16, Layout p. 49, Layout p. 52]
---

## Helps
Shows changes in rank or value between two values per item, such as a team's wins in two years (Layout p. 16). Each item is one line joining its two values, so the line's orientation shows the change (Layout p. 16). Line thickness can show the size of the change, a derived attribute, and colour its direction (Layout p. 16). Our reading: which items rose, which fell, and which changed most can be seen at a glance from the slopes and colours.

## Hides
Our reading: only two values per item are shown, so anything between the two time points is invisible. Munzner rates the idiom at dozens of items, though it shows hundreds of value levels (Layout p. 16). Our reading: lines cross between the axes, and many crossings make single lines hard to follow; labels at each end crowd together when items have similar values. Each line's length varies with its slope without encoding an attribute, as for a segment in parallel coordinates, of which the slopegraph is the two-axis case (Layout pp. 49, 52).

## Arrange
Each item's two values sit on two parallel vertical axes, joined by a line; lines overlap and share no borders (Layout p. 16). The global layout is not rectilinear: Munzner calls it a special case of parallel coordinates with only two axes (Layout p. 52).
