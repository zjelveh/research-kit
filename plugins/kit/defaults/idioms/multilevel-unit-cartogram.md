---
id: multilevel-unit-cartogram
name: Multilevel unit cartogram
origin: munzner
group: spatial
order: 260
kind: idiom
form: encoding
medium: [static, interactive]
shape: geographic
data:
  keys: [{type: categorical}]
  values: [{type: quantitative}]
  optional: [{type: [categorical, quantitative], channel: colour}]
  spatial: regions
tasks: [compare-values, spatial-pattern]
marks: [{level: 1, mark: point}, {level: 2, mark: area}]
channels:
  encoded:
    - {channel: area, carries: count, where: number of unit squares in a region}
  uniform: [{channel: size, where: unit squares}, {channel: shape, where: unit squares}]
  varying: null
  inherited: [{channel: hue, where: level 2 regions from their unit squares}]
scale: {note: null}
see_also:
  - id: grid-cartogram
    when: Every region should get the same size, with colour carrying the value (Spatial p. 23).
  - id: contiguous-cartogram
    when: Region shapes should stay as close to the original as possible, with area showing the value (Spatial p. 21).
  - id: dot-density-map
    when: Counts should show as same-size dots inside the true region outlines, each dot a fixed number of items (Spatial p. 28).
sources: [Spatial p. 21, Spatial p. 23, Spatial p. 24, Spatial p. 28]
---

## Helps
Builds each region from unit squares, such as one block per electoral vote, so the counts can be counted (Spatial p. 24). Our reading: a region's area is its number of squares, so counts compare as areas, and an exact count is there for a reader who counts.

## Hides
The counts do not pop out perceptually; they can be decoded only with cognitive effort (Spatial p. 24). Our reading: the shapes only resemble the regions, so, as with other non-contiguous cartograms, readers need some familiarity with the original map, and the positions may need explaining. Our reading: counting many squares is slow, and regions with few units are small and hard to label.

## Arrange
Two levels of marks: square point marks for the units at level 1, and the regions they form, poly marks, at level 2; the marks touch at both levels (Spatial p. 24). Munzner's examples assemble the units into state-like shapes, coloured by candidate, and also space those shapes apart, filling the gaps with white squares that can be counted too and show population density, a special case in which the marks still count as touching (Spatial p. 24). Our reading: each state takes its colour from its unit squares, so the level 2 regions inherit colour from level 1, and the blocks keep a quasi-geographic arrangement.
