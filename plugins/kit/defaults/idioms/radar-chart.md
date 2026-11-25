---
id: radar-chart
name: Radar chart
origin: munzner
group: orientation
order: 380
kind: idiom
form: encoding
medium: [static, interactive]
shape: 1-key
data:
  keys: [{type: ordinal}]
  values: [{type: quantitative}]
  optional: [{type: categorical, channel: hue}]
tasks: [trend]
marks: [{level: 1, mark: area}]
channels:
  encoded:
    - {channel: position-unaligned, carries: key, where: angle of each spoke around the centre}
    - {channel: position-unaligned, carries: value, where: radial position along each spoke}
    - {channel: connection, carries: succession of key levels}
  uniform: [{channel: size, where: line thickness}, {channel: hue, where: single polygon}]
  varying: [{channel: area, where: area enclosed by each polygon}]
  inherited: []
scale: {note: null}
see_also:
  - id: line-chart
    when: The key is ordered but not cyclic; Munzner's redesign of a radar example uses rectilinear axes (Layout p. 35).
  - id: bar-chart
    when: There is one series over a categorical key; aligned bars are read more precisely than radial positions.
  - id: star-plot
    when: Each value should be its own line from the centre, with no closed shape whose area can mislead.
  - id: parallel-coordinates
    when: There are many items with several quantitative attributes, better on axes lined up in a row than around a circle.
sources: [Layout p. 34, Layout p. 35, Layout p. 55]
---

## Helps
Shows one set of values around a circle as a closed shape, which stands out most when its interior is filled (Layout p. 34). Munzner's guidance is to avoid it unless the data is cyclic (Layout p. 34). A cyclic representation is the strength of polar layouts when it matches the data (Layout p. 55). Our reading: it suits a cyclic key, such as the month of the year (Layout p. 55). Our reading: the closed polygon then shows a whole cycle as one shape, with its end beside its start.

## Hides
When the axes are categorical and in an arbitrary order, the shape is salient but means very little (Layout p. 34). The enclosed area does not change linearly with the values, and radial values are read less precisely than positions on aligned rectilinear axes (Layout p. 34). Sectors of a polar layout widen, and grow in area, with distance from the centre (Layout p. 55). Munzner's example, a radar chart of how each Brazilian state voted in 2010, is marked difficult to interpret beside a redesign on rectilinear axes (Layout p. 35). Our reading: reordering the axes changes the shape and its area, and overlaid polygons can hide one another.

## Arrange
A line chart in a polar global layout: one spoke per key level around a centre, and each polygon joins successive spokes at the radial positions of its values (Layout p. 34). Its mark is a poly, not the line chart's open path, because its boundary is closed (Layout p. 34). Munzner's examples put school subjects on the axes, overlay up to three polygons coloured by person, and give the idiom's other names as spider chart, Kiviat diagram and polar chart (Layout p. 34). Our reading: her guidance limits the idiom to cyclic keys, which are ordered, so the key here is ordinal; the order of the axes around the circle is a design choice that changes the shape.
