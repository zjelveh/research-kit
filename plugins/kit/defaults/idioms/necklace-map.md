---
id: necklace-map
name: Necklace map
origin: munzner
group: spatial
order: 270
kind: idiom
form: encoding
medium: [static, interactive]
shape: geographic
data:
  keys: [{type: categorical}]
  values: [{type: quantitative}]
  optional: []
  spatial: regions
tasks: [compare-values]
marks: [{level: 1, mark: area}, {level: 2, mark: point}]
channels:
  encoded:
    - {channel: position-common, carries: geographic location, where: base map on both axes}
    - {channel: size, carries: value, where: symbol span}
    - {channel: hue, carries: region, where: symbol fill matching its region}
  uniform: [{channel: shape, where: circle symbols}]
  varying: [{channel: position-common, where: position along the necklace}]
  inherited: null
scale: {note: null}
see_also:
  - id: proportional-symbol-map
    when: Symbols can sit on their regions, accepting the overlap a necklace avoids (Spatial p. 18).
  - id: dorling-cartogram
    when: Circles sized by the value should keep rough geographic positions instead of sitting on a curve.
sources: [Spatial p. 18, Spatial 2025 p. 32, Spatial 2025 p. 33, Spatial 2025 p. 34]
---

## Helps
A variant of the symbol map that places the symbols by algorithm outside the regions rather than inside them (Spatial p. 18). It addresses the clutter problem, and it can be hierarchical (Spatial 2025 p. 32). In Munzner's figure, circles that overlap heavily on a plain symbol map sit apart on a ring around the map (Spatial p. 18). Our reading: symbols in a row along the necklace are easy to compare by size, and none of them hides a small region.

## Hides
Each symbol is less clearly tied to its region than on a plain symbol map (Spatial 2025 p. 32). Our reading: readers must match each symbol to its region by label or colour, which is harder for regions far from the necklace. Our reading: neighbours on the necklace need not be neighbours on the map, so spatial patterns are harder to see.

## Arrange
The design maps two-dimensional data onto a one-dimensional domain (Spatial 2025 p. 32). In Munzner's figure the necklace is a circle around a map of Europe, and the circles on it, each labelled with a country code and filled with its country's colour, touch or are spaced apart but do not overlap (Spatial p. 18). The algorithm computes feasible intervals, then optimizes symbol sizes and placements, trading off each symbol's position relative to its region, large symbols, disjoint symbols and a suitable order along the curve (Spatial 2025 p. 33). Our reading: the algorithm sets each symbol's place on the necklace, so position along it varies rather than encodes, by the logic Munzner applies to the Dorling cartogram. Extensions use several necklaces, nested or disjoint, or add flows between regions (Spatial 2025 p. 34).
