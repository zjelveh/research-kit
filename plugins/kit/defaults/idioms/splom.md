---
id: splom
name: Scatterplot matrix (SPLOM)
origin: munzner
group: orientation
order: 310
kind: idiom
form: encoding
medium: [static, interactive]
shape: 0-keys
data:
  keys: []
  values: [{type: quantitative}, {type: quantitative}, {type: quantitative, repeats: true}]
  optional: [{type: categorical, channel: position-common}]
tasks: [relationship]
marks: [{level: 1, mark: point}]
channels:
  encoded:
    - {channel: position-common, carries: the attribute of each column, where: horizontal in every cell}
    - {channel: position-common, carries: the attribute of each row, where: vertical in every cell}
  uniform: [{channel: size, where: point size}, {channel: hue}, {channel: shape}]
  varying: []
  inherited: []
scale:
  attributes: {max: 12}
  note: About a dozen attributes, and dozens to hundreds of items (Layout p. 47).
see_also:
  - id: parallel-coordinates
    when: There are more attributes; parallel coordinates handle dozens, with each item as one path (Layout p. 49).
  - id: scatterplot
    when: One pair of attributes matters and should be drawn large.
  - id: heatmap
    when: Correlations among many attributes should show as one coloured cell per pair, as in a correlation matrix.
sources: [Layout p. 47, Layout p. 48, Layout p. 49, Layout p. 50, Layout p. 53]
---

## Helps
Shows correlation for every pair of attributes: a positive correlation is a diagonal from low to high, a negative one a diagonal from high to low, and uncorrelated attributes are spread out (Layout p. 50). All possible pairs of axes are drawn at once (Layout p. 47). Our reading: since every pair is shown, a strong relationship cannot hide in a pair nobody plotted.

## Hides
Each cell shows only two attributes, since rectilinear axes have only vertical and horizontal position to give them (Layout p. 48). Our reading: a relationship among three or more attributes at once does not show in any single cell. The matrix scales to about a dozen attributes (Layout p. 47). Our reading: past that the cells get so small that points overplot before many items fit.

## Arrange
A matrix of scatterplots with rectilinear axes and point marks, one row and one column per attribute (Layout p. 47). Munzner's example plots nine characteristics of abalone, a sea snail, including the categorical sex, and shows only the lower triangle with the attribute names on the diagonal (Layout p. 47). A smaller example shows the full matrix for four attributes (Layout p. 48). Rectilinear axes do not stretch past two: two are best, three are problematic and four or more impossible (Layout p. 53). Our reading: the matrix keeps two axes per cell and adds cells instead, and a full matrix repeats each pair mirrored across the diagonal.
