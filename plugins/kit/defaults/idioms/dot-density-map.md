---
id: dot-density-map
name: Dot-density map
origin: munzner
group: spatial
order: 220
kind: idiom
form: encoding
medium: [static, interactive]
shape: geographic
data:
  keys: [{type: categorical}]
  values: [{type: quantitative}]
  optional: [{type: categorical, channel: hue}]
  spatial: regions
tasks: [spatial-pattern, clusters-outliers]
marks: [{level: 1, mark: point}, {level: 1, mark: area}]
channels:
  encoded:
    - {channel: density, carries: value, where: density of dots within each region}
  uniform: [{channel: size, where: dots}, {channel: shape, where: dots}, {channel: tilt, where: dots}, {channel: hue}]
  varying:
    - {channel: position-common, where: random within each region}
  inherited: []
scale: {note: Rendering many dots can be slow (Spatial p. 29).}
see_also:
  - id: one-to-one-dot-map
    when: Each item has its own location to show, one dot per item (Spatial p. 30).
  - id: choropleth-map
    when: The value is a rate or a mean rather than a count of items, so it cannot be split into dots.
  - id: multilevel-unit-cartogram
    when: Counts should be countable units arranged in blocks rather than scattered at random.
sources: [Spatial p. 28, Spatial p. 29, Spatial p. 30]
---

## Helps
Shows a count per region, such as population, by placing dots so that their density within each region shows the value, each dot standing for a constant number of items (Spatial p. 28). It serves to show high-level spatial patterns and clusters; Munzner's example puts one dot per 50,000 people over county outlines (Spatial p. 28). Our reading: dense and sparse areas show at a glance, and each region gets as many dots as its count, whatever its size.

## Hides
Dot positions within a region are random and carry no meaning, and readers who take them as meaningful are misled (Spatial pp. 28, 29). Like a choropleth, it needs normalization: the dots may show where the population is dense rather than the effect of interest (Spatial p. 29). Quantities are hard to read off (Spatial p. 29). On a map that also has symbols, a dot may be read as a symbol for a whole region or as one item (Spatial p. 30).

## Arrange
Dots and region outlines are two mark types at the same level; the dots share size, symbol and orientation, and colour may encode a category or stay uniform (Spatial p. 28). Each dot's position within its region is random, so position varies rather than encodes (Spatial p. 28). Our reading: the count is the number of dots in a region, and density is that count spread over the region's area, which reads as a darker or lighter patch. Our reading: the dots use the base map's layout, share no borders and may overlap where the density is high.
