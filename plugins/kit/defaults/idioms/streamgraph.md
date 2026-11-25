---
id: streamgraph
name: Streamgraph
origin: munzner
group: keys
order: 340
kind: idiom
form: encoding
medium: [static, interactive]
shape: 2-keys
data:
  keys: [{type: ordinal}, {type: categorical}]
  values: [{type: quantitative}]
  optional: []
tasks: [trend]
marks: [{level: 1, mark: area}, {level: 2, mark: area}]
channels:
  encoded:
    - {channel: position-common, carries: time key, where: horizontal}
    - {channel: length, carries: value, where: layer height at each time}
    - {channel: hue, carries: layer key}
  uniform: []
  varying: [{channel: position-common, where: vertical position of each layer}]
  inherited: [{channel: shape, where: whole shape at level 2}, {channel: hue, where: whole shape at level 2}]
scale:
  note: Dozens to hundreds of levels for the layer key, far more than the 10 to 12 of a stacked bar chart; most layers do not extend across the whole chart (Layout p. 21).
see_also:
  - id: stacked-bar
    when: The stacked key has at most 10 to 12 levels and values at single points of the key matter (Layout p. 20).
  - id: line-chart
    when: Each series must be read on its own against a shared axis.
sources: [Layout p. 20, Layout p. 21]
---

## Helps
Shows how each layer continues across time; Munzner calls it a generalized stacked graph (Layout p. 21). It takes dozens to hundreds of layers, far more than a stacked bar chart (Layout p. 21). Our reading: the outline of the whole shape shows the total over time, such as how much people go to the movies overall, not only how each movie does.

## Hides
It is not for looking up a value at a single point in time (Layout p. 21). Very few layers can carry readable labels: the big ones are labelled in the static view and the rest only on hover (Layout p. 21). Our reading: no layer rests on a flat baseline, so even the bottom layer cannot be read against an axis, and layer heights are hard to compare across layers.

## Arrange
Layers run along a horizontal time axis and stack vertically, in an order that puts the layers with large counts at the top and bottom (Layout p. 21). An algorithm derives each layer's shape so that its height at each time encodes its count (Layout p. 21). The layers touch, with shared borders and no overlaps, and together make one whole shape at the second level (Layout p. 21). Our reading: the stack sits on a computed, curving baseline, not on a flat zero line.
