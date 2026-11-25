---
id: binned-scatter
name: Binned scatterplot
origin: kit
group: reduce
order: 80
kind: idiom
form: encoding
medium: [static]
shape: 1-key
data:
  keys: [{type: ordinal}]
  values: [{type: quantitative}]
  optional: [{type: categorical, channel: hue}]
tasks: [relationship]
marks: [{level: 1, mark: point}]
channels:
  encoded:
    - {channel: position-common, carries: bin of x (key), where: horizontal at the bin's mean of x}
    - {channel: position-common, carries: mean of y in the bin, where: vertical}
  uniform: [{channel: size, where: point size}, {channel: hue}, {channel: shape}]
  varying: []
  inherited: []
scale: {note: null}
see_also:
  - id: scatterplot
    when: The items are few enough to draw one by one, or single items matter.
  - id: continuous-scatterplot
    when: The whole joint density of the two attributes matters, not only the mean of one along the other.
  - id: histogram
    when: The distribution of one attribute matters, as counts per bin.
sources: [Layout p. 10, Layout p. 11, Marks p. 9, Reduce p. 5, Reduce p. 9, Reduce p. 10]
---

## Helps
Our reading: shows how the mean of one quantitative attribute changes along another, when there are too many items for a scatterplot to show it. Munzner rates a scatterplot at hundreds of items (Layout p. 11). Combining the items in each bin into one derived point informs about the whole set (Reduce pp. 5, 9). Each bin's mean is a point placed by position on a common scale, the channel Munzner ranks most effective for ordered values (Marks p. 9).

## Hides
Our reading: each point is a mean, so the spread of y within each bin is hidden, and a binned scatterplot can show a tight relationship where the items scatter widely. Aggregation makes it difficult to avoid losing signal (Reduce p. 5). In a histogram the bin size is crucial (Reduce p. 10). Our reading: a binned scatterplot's bins matter in the same way. Our reading: when both attributes are first adjusted for covariates, the points are adjusted means rather than raw ones, and the caption must say so.

## Arrange
The axes are a scatterplot's: horizontal and vertical position for two quantitative attributes (Layout p. 10). Our reading: there is one point per bin of x, at the bin's mean of x and the mean of y within it; the bins either hold equal numbers of items, as quantiles of x, or have equal widths. Our reading: a fit line, estimated on the items rather than the bins, may be drawn over the points, and several groups can share the axes, told apart by hue. Our reading: the regression-discontinuity plot is a variant: bins and fit lines stop at a cutoff on x and start again past it, and a vertical reference line marks the cutoff, so the jump there shows.
