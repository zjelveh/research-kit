---
id: scatterplot
name: Scatterplot
origin: munzner
group: keys
order: 40
kind: idiom
form: encoding
medium: [static, interactive]
shape: 0-keys
data:
  keys: []
  values: [{type: quantitative}, {type: quantitative}]
  optional: [{type: quantitative, channel: size}, {type: categorical, channel: hue}, {type: categorical, channel: shape}]
tasks: [relationship, distribution, clusters-outliers]
marks: [{level: 1, mark: point}]
channels:
  encoded:
    - {channel: position-common, carries: first value, where: horizontal}
    - {channel: position-common, carries: second value, where: vertical}
  uniform: [{channel: size}, {channel: hue}, {channel: shape, where: symbol}, {channel: tilt, where: orientation}]
  varying: []
  inherited: []
scale: {note: Hundreds of items (Layout p. 11).}
see_also:
  - id: slopegraph
    when: Each item's change from one value to the other matters more than how the two relate across items.
  - id: line-chart
    when: One of the two attributes is an ordered key, such as time, and the points are read in sequence.
  - id: heatmap
    when: Correlations among many attributes are shown at once, one cell per pair, as in a correlation matrix.
  - id: splom
    when: There are more than two attributes, since position shows only two (Layout p. 48).
  - id: continuous-scatterplot
    when: Millions of items overplot, and their density is what matters (Reduce p. 16).
  - id: binned-scatter
    when: The mean of one value along the other matters more than the single items.
sources: [Layout p. 9, Layout p. 10, Layout p. 11, Layout p. 12, Layout p. 14, Layout p. 15, Layout p. 48, Marks p. 22, Reduce p. 16]
---

## Helps
Finds trends, outliers, the distribution, correlation and clusters in two quantitative values (Layout p. 11). Correlation shows as the shape of the point cloud: a rising line at perfect positive correlation, a shapeless cloud at none, and a falling line at perfect negative correlation (Layout p. 14). It also shows clusters, and whether they match classes shown by colour (Layout p. 15). Horizontal and vertical positions are equally easy to decode (Marks p. 22).

## Hides
Our reading: with many items, opaque points overplot, so dense regions hide how many points sit there. Munzner rates the idiom at hundreds of items (Layout p. 11). Our reading: a single item is hard to find unless it is labelled, because no key places it. Horizontal and vertical position show only two attributes, one on each axis (Layout p. 48).

## Arrange
Both axes express values and neither holds a key, so each item is placed by its two values alone (Layout p. 9). Points share no borders and may overlap (Layout p. 10). Point marks leave room for more channels: size for a third attribute, usually with the radius set to the square root of the value so that area grows linearly with it, and colour and symbol for others (Layout p. 12). Our reading: QQ and calibration plots are scatterplots read against a diagonal reference line, where sample quantiles would equal theoretical ones, or observed rates would equal predicted ones. Our reading: a funnel plot puts each study's estimate against its standard error, with a reference line at the pooled estimate and lines on either side for the spread expected from chance alone.
