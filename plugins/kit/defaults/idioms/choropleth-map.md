---
id: choropleth-map
name: Choropleth map
origin: munzner
group: spatial
order: 190
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
marks: [{level: 1, mark: area}]
channels:
  encoded:
    - {channel: position-common, carries: geographic location, where: both map axes}
    - {channel: luminance, carries: value, where: region fill in a sequential colour map}
    - {channel: shape, carries: geographic boundary, where: region outline}
    - {channel: area, carries: geographic area, where: region}
  uniform: []
  varying: []
  inherited: []
scale: {note: null}
see_also:
  - id: proportional-symbol-map
    when: Regions differ in size, and a symbol sized by the value eases the gap between region size and salience (Spatial p. 19).
  - id: one-to-one-dot-map
    when: Items have their own locations, and dots avoid the problem of unequal region sizes (Spatial p. 29).
  - id: grid-cartogram
    when: Every region should get the same size, with colour still carrying the value (Spatial p. 23).
  - id: heatmap
    when: Coloured cells are placed by two keys rather than by geography.
sources: [Spatial p. 8, Spatial p. 9, Spatial p. 13, Spatial p. 14, Spatial p. 15, Spatial p. 19, Spatial p. 23, Spatial p. 29]
---

## Helps
Shows how one value varies across space when the central task is to understand spatial relationships (Spatial p. 9). It is easy to read, needs no learning since the form is well established, and suits data that were collected and aggregated by region in the first place (Spatial p. 15). Our reading: neighbouring regions with similar colours read as one area, so regional clusters and gradients stand out.

## Hides
A map of raw values mostly shows where people live, so values should be normalized, such as unemployed people per 100 citizens, and failing to normalize is a common error (Spatial p. 13). How much a region's colour stands out depends on the region's size, not its value, so large regions look more important than small ones, and the choice of palette changes the result a great deal (Spatial p. 15). Position, the most effective channel, is spent on geographic location, which is reasonable only when the spatial pattern is the central task (Spatial p. 15). Our reading: colour shows the value only roughly, so regions can be ranked only coarsely, and exact values need a legend or labels.

## Arrange
Each region is a key in the table, used to look up its value (Spatial p. 8). Each region is drawn with its given geometry: the polygons touch without overlapping, their shapes show the boundaries and their areas the geographic areas, in a rectilinear layout for most latitude and longitude projections (Spatial p. 9). Colour shows the value; Munzner's example uses a sequential colour map in discrete steps (Spatial p. 9). Munzner advises showing one attribute at a time, normalizing where appropriate and choosing colours and bins with care; the best case is regions of roughly equal size (Spatial p. 14).
