---
id: ballotmap
name: BallotMap
origin: munzner
group: spatial
order: 280
kind: design-choice
form: encoding
medium: [static, interactive]
shape: geographic
data:
  keys: [{type: categorical}, {type: categorical}, {type: ordinal}]
  values: [{type: quantitative}]
  optional: []
  spatial: regions
tasks: [spatial-pattern, compare-values]
marks: [{level: 1, mark: point}, {level: 2, mark: glyph}]
channels:
  encoded:
    - {channel: hue, carries: party}
    - {channel: saturation, carries: elected or not, where: each ward rectangle}
    - {channel: length, carries: number elected, where: saturated part of each row}
    - {channel: position-common, carries: ballot position within party, where: rows top to bottom in each party band}
  uniform: [{channel: size, where: ward rectangle}, {channel: size, where: borough square}]
  varying: null
  inherited: []
scale: {note: null}
see_also:
  - id: choropleth-map
    when: One value per region is enough, and regions are similar enough in size to avoid a choropleth's size issues (Spatial 2025 p. 43).
  - id: grid-cartogram
    when: One colour per region in an equal-cell quasi-geographic grid is enough.
  - id: glyphmap
    when: Small charts should sit at true map positions, or in a plain grid.
sources: [Spatial 2025 p. 41, Spatial 2025 p. 42, Spatial 2025 p. 43, Spatial 2025 p. 44]
---

## Helps
Shows, for every borough in a quasi-geographic grid, how many candidates at each ballot position within each party were elected (Spatial 2025 p. 42). Munzner's case study, from the BallotMaps paper by Wood, Badawood, Dykes and Slingsby, asks whether the effect of ballot position on who is elected varies across London's 32 boroughs (Spatial 2025 p. 42). Were there no bias from name order, the bars would all match in length; instead their lengths follow a clear pattern, and candidates placed first within their party win more often than those placed second or third (Spatial 2025 p. 42). Munzner presents its quasi-geographic positioning as the best of both worlds: a choropleth has size issues, and a table loses geographic position (Spatial 2025 p. 43). Our reading: every borough gets the same space, so small inner boroughs are as readable as large outer ones.

## Hides
Our reading: grid positions are only roughly geographic, so readers need the real map to find a borough. Our reading: the bars are small, so exact values are hard to read, and 32 squares of nine bars each take time to scan.

## Arrange
The 32 boroughs sit in a grid of four rows of eight squares, placed quasi-geographically, and Munzner shows an outline map of the boroughs beside it (Spatial 2025 p. 43). Within each borough square, each small rectangle is a ward, coloured by party and saturated when the candidate was elected, with candidates ordered top to bottom by their ballot position within their party, a derived attribute (Spatial 2025 pp. 41, 42). Our reading: like a grid cartogram it gives each region an equal cell, and like a glyphmap each cell holds small charts, here nine bars in three party bands. Spatially ordered treemaps are another way to give regions quasi-geographic positions (Spatial 2025 p. 44).
