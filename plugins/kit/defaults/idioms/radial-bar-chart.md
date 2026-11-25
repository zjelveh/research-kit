---
id: radial-bar-chart
name: Radial bar chart
origin: munzner
group: orientation
order: 360
kind: idiom
form: encoding
medium: [static, interactive]
shape: 1-key
data:
  keys: [{type: categorical}]
  values: [{type: quantitative}]
  optional: []
tasks: [compare-values]
marks: [{level: 1, mark: point}]
channels:
  encoded:
    - {channel: position-unaligned, carries: key, where: angle of each bar around the centre}
    - {channel: position-unaligned, carries: value, where: radial position of each bar's end}
    - {channel: length, carries: value, where: radial span from the central ring}
  uniform: [{channel: size, where: bar width}]
  varying: []
  inherited: []
scale: {note: null}
see_also:
  - id: star-plot
    when: The axes should meet at a central point instead of a ring (Layout p. 36).
  - id: bar-chart
    when: Sizes must be judged accurately, which aligned rectilinear bars allow better than radial lengths (Layout p. 36).
  - id: coxcomb-chart
    when: Touching wedges at equal angles are wanted, at the cost of area growing faster than length (Layout p. 38).
sources: [Layout p. 36, Layout p. 38, Layout p. 55]
---

## Helps
A radial analog of the bar chart: each category gets an angle around a central ring, and its value is the radial position and length of a bar (Layout p. 36). Each bar keeps a uniform width as it grows, so its area stays linear with its length; Munzner calls bars the safer choice in radial and rectilinear layouts alike (Layout p. 38).

## Hides
Radial lengths are judged less accurately than aligned rectilinear position, as in a bar chart (Layout p. 36). In a polar layout, angular position is read less precisely than rectilinear position, and radial distance less precisely than aligned rectilinear position (Layout p. 55). Our reading: the bars point in different directions, so no two can be compared along a shared baseline.

## Arrange
Polar axes that meet at a central ring, one per category (Layout p. 36). The bar chart's horizontal position becomes angular position, and its vertical position and height become radial position and span (Layout p. 36). In Munzner's example, six coloured bars run outward along light grey tracks (Layout p. 36). Our reading: the bars share no borders and do not overlap.
