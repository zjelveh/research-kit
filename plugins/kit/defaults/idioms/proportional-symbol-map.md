---
id: proportional-symbol-map
name: Proportional symbol map
origin: munzner
group: spatial
order: 200
kind: idiom
form: encoding
medium: [static, interactive]
shape: geographic
data:
  keys: [{type: categorical}]
  values: [{type: quantitative}]
  optional: [{type: [categorical, quantitative], channel: colour}]
  spatial: regions
tasks: [spatial-pattern, compare-values]
marks: [{level: 1, mark: area}, {level: 2, mark: point}, {level: 2, mark: glyph}]
channels:
  encoded:
    - {channel: position-common, carries: geographic location, where: base map on both axes}
    - {channel: size, carries: value, where: symbol span}
  uniform: [{channel: shape, where: symbol}, {channel: hue}]
  varying: []
  inherited: []
scale: {note: null}
see_also:
  - id: choropleth-map
    when: Regions are roughly equal in size, the best case for colour by region (Spatial p. 14).
  - id: necklace-map
    when: Symbols overlap too much and can be placed outside their regions instead (Spatial p. 18).
  - id: glyphmap
    when: Each region needs a small chart rather than one value (Spatial p. 17).
  - id: one-to-one-dot-map
    when: Items have their own locations, and each mark should be one item rather than a whole region (Spatial p. 30).
  - id: dorling-cartogram
    when: Circles sized by the value should touch without overlapping, at the cost of exact positions.
sources: [Spatial p. 14, Spatial p. 16, Spatial p. 17, Spatial p. 18, Spatial p. 19, Spatial p. 30]
---

## Helps
Shows one value per region by the size of a symbol, such as a circle for each state's population, and is often a good alternative to a choropleth (Spatial p. 16). It is fairly intuitive to read, and since the symbol's size follows the value, it eases the choropleth's problem that a region's salience follows its size (Spatial p. 19). Our reading: a large value stands out even when its region is small, and symbol sizes can be compared across the whole map.

## Hides
Symbols can overlap one another and hide the region boundaries beneath them (Spatial p. 19). On a map that also has dots, a point mark is ambiguous: it could be a symbol for a whole region, a dot for one item or a dot for many items (Spatial p. 30). Our reading: areas are compared less precisely than lengths, so close values are hard to rank, and a size legend helps. Our reading: each symbol sits at its region's centre, so it shows nothing about where in the region the items are.

## Arrange
Two levels of marks: the base map's regions at level 1, and one symbol per region at level 2, a point mark or a glyph (Spatial p. 16). The symbols share the base map's layout, usually rectilinear, each typically at its region's centroid, with a polar local layout whose span shows the value (Spatial p. 16). The symbol is usually the same for every region; colour may encode another attribute or stay uniform, and orientation may encode one only when the symbol is asymmetric (Spatial p. 16). Our reading: each symbol is placed where its region lies on the base map, and symbols share no borders.
