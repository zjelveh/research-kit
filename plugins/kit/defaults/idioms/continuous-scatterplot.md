---
id: continuous-scatterplot
name: Continuous scatterplot
origin: munzner
group: reduce
order: 300
kind: idiom
form: encoding
medium: [static, interactive]
shape: 2-keys
data:
  keys: [{type: ordinal}, {type: ordinal}]
  values: [{type: quantitative}]
  optional: []
tasks: [relationship, distribution]
marks: [{level: 1, mark: point}]
channels:
  encoded:
    - {channel: position-common, carries: x of the pixel (first key), where: horizontal}
    - {channel: position-common, carries: y of the pixel (second key), where: vertical}
    - {channel: luminance, carries: overplot density, where: ordered luminance in the colour map}
    - {channel: hue, carries: overplot density, where: a sequence of hues in the same colour map}
  uniform: [{channel: size, where: one pixel per cell}]
  varying: []
  inherited: []
scale: {note: No limit on overplotting; millions of items (Reduce p. 16).}
see_also:
  - id: scatterplot
    when: The items are few enough to draw one by one, hundreds rather than millions.
  - id: binned-scatter
    when: The mean of one attribute along the other matters, not the whole density.
  - id: heatmap
    when: The two keys are categorical, not positions derived from two quantitative attributes.
sources: [Reduce p. 5, Reduce p. 16, Marks p. 9]
---

## Helps
Aggregates a scatterplot: the derived table has each pixel's x and y as keys and the density of the items overplotted there as its value (Reduce p. 16). It has no limit on overplotting and scales to millions of items (Reduce p. 16). Our reading: the dense regions show the form of the relationship between the two attributes and where most items lie, which an overplotted scatterplot hides.

## Hides
Our reading: single items are gone, so outliers and small groups in sparse regions fade into the low end of the colour map. Density is read from colour, and luminance ranks well below position among the channels for ordered attributes (Marks p. 9). Aggregation makes it difficult to avoid losing signal (Reduce p. 5).

## Arrange
A dense, space-filling 2D matrix of pixels, each placed by its x and y (Reduce p. 16). The colour map combines a sequence of hues with ordered luminance (Reduce p. 16). Our reading: the axes are those of the scatterplot it aggregates, and each pixel acts as a heatmap cell that shares its borders and overlaps no other. Our reading: a two-dimensional histogram or hexagonal binning is a coarser version, with cells larger than a pixel, and its cell size can change the pattern as a histogram's bin size does.
