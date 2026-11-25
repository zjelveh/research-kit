---
id: one-to-one-dot-map
name: One-to-one dot map
origin: munzner
group: spatial
order: 210
kind: idiom
form: encoding
medium: [static, interactive]
shape: geographic
data:
  keys: []
  values: []
  optional: [{type: categorical, channel: hue}]
  spatial: points
tasks: [spatial-pattern, distribution, clusters-outliers]
marks: [{level: 1, mark: point}, {level: 1, mark: area}]
channels:
  encoded:
    - {channel: position-common, carries: item location, where: both map axes}
  uniform: [{channel: size, where: dots}, {channel: shape, where: dots}, {channel: hue}]
  varying: []
  inherited: []
scale: {note: Rendering many dots can be slow (Spatial p. 29).}
see_also:
  - id: dot-density-map
    when: Each dot should stand for many items, placed at random within its region (Spatial p. 30).
  - id: choropleth-map
    when: The data come aggregated by region, as they often do (Spatial p. 15).
  - id: proportional-symbol-map
    when: One mark per region should show an aggregate, rather than one mark per item (Spatial p. 30).
  - id: scatterplot
    when: The two positions are attributes other than longitude and latitude, with no base map.
sources: [Spatial p. 15, Spatial p. 27, Spatial p. 29, Spatial p. 30]
---

## Helps
Places one dot at each item's actual location, using position, to show detailed spatial distributions and patterns, clusters and outliers (Spatial p. 27). It is straightforward to understand, and it avoids the choropleth's problems with regions of unequal size (Spatial p. 29). Our reading: each dot is an actual item, so gaps and clusters on the map are features of the data.

## Hides
Like a choropleth, it needs normalization: the dots may show where the population is dense rather than the effect of interest (Spatial p. 29). On a map that also has symbols, a point mark is ambiguous: it could be a symbol for a whole region, a dot for one item or a dot for many items placed at random (Spatial p. 30). Our reading: where items are dense, dots cover one another, so counts in crowded areas are hard to judge.

## Arrange
Dots and region outlines are two mark types at the same level; the dots share one size and symbol, and colour may encode a category or stay uniform (Spatial p. 27). Munzner's example colours dots by the nearest of seven burger chains (Spatial p. 27). Our reading: in that example the dots sit on a regular grid, so each reads as a sample point coloured by its nearest chain rather than as one restaurant. Our reading: the dots use the base map's layout, usually rectilinear, share no borders and overlap where items are close. Munzner also lists dot density map as another name for it (Spatial p. 27).
