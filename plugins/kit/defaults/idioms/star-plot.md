---
id: star-plot
name: Star plot
origin: munzner
group: orientation
order: 390
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
    - {channel: position-unaligned, carries: key, where: angle of each line around the centre}
    - {channel: position-unaligned, carries: value, where: radial position of each line's tip}
    - {channel: length, carries: value, where: radial span from the centre}
  uniform: [{channel: size, where: line thickness}]
  varying: []
  inherited: []
scale: {note: null}
see_also:
  - id: radial-bar-chart
    when: The axes should meet at a central ring instead of a point (Layout p. 36).
  - id: bar-chart
    when: Sizes must be judged accurately, which aligned rectilinear bars allow better than radial lengths (Layout p. 36).
  - id: radar-chart
    when: The key is cyclic and a series' values should read as one closed shape.
sources: [Layout p. 36, Layout p. 55]
---

## Helps
A radial analog of the bar chart: each category gets an angle, and its value is the radial position and length of a line out from a central point (Layout p. 36). Our reading: each value is its own length from the centre, so values are compared one at a time rather than through a filled shape, as in a radar chart.

## Hides
Radial lengths are judged less accurately than aligned rectilinear position, as in a bar chart (Layout p. 36). In a polar layout, angular position is read less precisely than rectilinear position, and radial distance less precisely than aligned rectilinear position (Layout p. 55). Our reading: with no shared baseline or rings, values are hard to read off, and a very short line nearly disappears at the centre.

## Arrange
Polar axes that meet at a central point, one per category (Layout p. 36). The bar chart's horizontal position becomes angular position, and its vertical position and height become radial position and span (Layout p. 36). Munzner's example, from the Vismon paper on fisheries management, sets a star plot of six coloured lines beside a radial bar chart and a rectilinear bar chart (Layout p. 36). Our reading: the lines share no borders and do not overlap except where they meet at the centre.
