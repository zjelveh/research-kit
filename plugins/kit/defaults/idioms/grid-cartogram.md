---
id: grid-cartogram
name: Grid cartogram
origin: munzner
group: spatial
order: 250
kind: idiom
form: encoding
medium: [static, interactive]
shape: geographic
data:
  keys: [{type: categorical}]
  values: [{type: quantitative}]
  optional: []
  spatial: regions
tasks: [spatial-pattern]
marks: [{level: 1, mark: point}]
channels:
  encoded:
    - {channel: luminance, carries: value, where: tile fill as in a choropleth}
  uniform: [{channel: size, where: tile}, {channel: shape, where: one tile shape for all}, {channel: tilt, where: tile orientation}]
  varying:
    - channel: position-common
      where: aligned to the grid, then kept close to relative order and true location
  inherited: []
scale: {note: null}
see_also:
  - id: choropleth-map
    when: Region shapes and true areas matter, with colour encoding the value just as here (Spatial p. 23).
  - id: dorling-cartogram
    when: Each region should be sized by the value, as a circle (Spatial p. 22).
  - id: multilevel-unit-cartogram
    when: A region's size should carry a count that readers can count off in unit squares (Spatial p. 24).
  - id: heatmap
    when: Coloured cells are placed by two keys rather than by geography.
sources: [Spatial p. 22, Spatial p. 23, Spatial p. 24, Spatial p. 26]
---

## Helps
Gives every region a tile of the same size and shape in a grid that keeps roughly the map's arrangement, and shows the value by colour, as a choropleth does (Spatial p. 23). Its regular tiles are easier to read than warped regions, its equal areas soften the size problems of other cartograms, and its uniform shapes suit layering other encodings on top (Spatial p. 26). Our reading: equal tiles also remove the choropleth's problem that large regions look more important than small ones.

## Hides
When the original regions differ greatly in size, forcing them into equal tiles distorts the map substantially (Spatial p. 26). Readers still need some familiarity with the original map, and the quasi-geographic positions may need explaining (Spatial p. 26). Our reading: every region gets the same weight, so a tiny region and a huge one look equally important, and the value comes from colour alone.

## Arrange
Each region becomes a point mark, a circle, square or hexagon, of uniform size, shape and orientation; the tiles are arranged in a grid and touch without overlapping (Spatial p. 23). Tiles must align with the grid, and the algorithm then tries to keep the regions' relative order and each tile close to its true location, so order and position vary without encoding anything (Spatial p. 23). Munzner's examples show US states as circles, squares and hexagons, and London boroughs as squares; other names include grid map, mosaic cartogram, tile grid map and tile map (Spatial p. 23). Our reading: several of the examples leave small gaps between tiles, which still fill the cells of one grid.
