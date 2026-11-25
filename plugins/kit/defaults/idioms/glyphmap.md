---
id: glyphmap
name: Glyphmap
origin: munzner
group: orientation
order: 290
kind: idiom
form: encoding
medium: [static, interactive]
shape: geographic
data:
  keys: [{type: ordinal}]
  values: [{type: quantitative}]
  optional: [{type: quantitative, channel: luminance}]
  spatial: regions
tasks: [trend, spatial-pattern]
marks: [{level: 1, mark: area}, {level: 2, mark: glyph}]
channels:
  encoded:
    - {channel: position-common, carries: region, where: each glyph at its region's centroid}
    - {channel: position-unaligned, carries: key, where: along each glyph's horizontal or angular axis}
    - {channel: position-unaligned, carries: value, where: along each glyph's vertical or radial axis}
  uniform: [{channel: shape, where: one glyph form for every region}]
  varying: null
  inherited: []
scale: {note: null}
see_also:
  - id: line-chart
    when: There is one series, or a few that can share one set of axes.
  - id: radar-chart
    when: One series' values should read as one closed shape around a circle.
  - id: pie-chart
    when: Each region's glyph shows parts of a whole, as in the map of German states (Spatial p. 17).
  - id: proportional-symbol-map
    when: Each region has a single quantitative value, shown by the size of one symbol (Spatial p. 16).
sources: [Layout p. 45, Layout p. 55, Spatial p. 16, Spatial p. 17]
---

## Helps
Rectilinear glyphs are good for telling linear from nonlinear trends (Layout p. 45). Polar glyphs are good for cyclic patterns, for judging periodicity (Layout p. 45). Our reading: on a map, glyphs let readers compare the shape of each region's series and see where similar shapes cluster.

## Hides
Our reading: glyphs are small, so exact values cannot be read from them. Polar glyphs share the limits of polar axes: angular position is read less precisely than rectilinear position, and radial distance less precisely than aligned rectilinear position (Layout p. 55). Our reading: in the polar form a straight trend becomes a spiral, which is harder to judge than a sloped line. Our reading: on a map, glyphs can overlap one another and the region borders.

## Arrange
Each glyph has its own small axes, rectilinear or polar; Munzner's example draws twelve series both ways, with a white reference line through each rectilinear glyph and a white reference circle through each polar one (Layout p. 45). On a map, the glyphs are a second level of marks over the base map, one per region, typically at the region's centroid and in the same global layout as the map (Spatial p. 16). Munzner's map examples put four bars in each US state, for literacy from 2000 to 2003 coloured by working hours per week, and a pie in each German state for the shares of agricultural, forest and settlement area (Spatial p. 17). In neither map does a value set a glyph's overall size; the marks inside carry the values (Spatial p. 17). Our reading: without a map, glyphs can sit in a grid, sorted by any key.
