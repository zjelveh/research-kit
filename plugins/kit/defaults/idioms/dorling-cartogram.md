---
id: dorling-cartogram
name: Dorling cartogram
origin: munzner
group: spatial
order: 240
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
marks: [{level: 1, mark: point}]
channels:
  encoded:
    - {channel: size, carries: value, where: circle span}
  uniform: [{channel: tilt, where: circles are symmetric}, {channel: shape, where: always a circle}, {channel: hue}]
  varying:
    - channel: position-common
      where: relative order kept strongly and true location loosely, by circle packing
  inherited: []
scale: {note: null}
see_also:
  - id: contiguous-cartogram
    when: Neighbouring regions must keep their shared borders, at the cost of distorted shapes (Spatial p. 21).
  - id: grid-cartogram
    when: Every region should get the same size and shape, with colour carrying the value (Spatial p. 23).
  - id: proportional-symbol-map
    when: Circles should stay at their regions' centres over the base map, at the cost of overlap.
sources: [Spatial p. 21, Spatial p. 22, Spatial p. 23, Spatial p. 26]
---

## Helps
Shows one value per region by the size of a circle, with the circles packed so that they touch, roughly where their regions are (Spatial p. 22). Circles are easier to read than warped regions, and other encodings can be layered on them (Spatial p. 26). Our reading: the circles do not overlap, so every region's value stays visible, and sizes can be compared across the map.

## Hides
Region shapes are thrown away, and readers still need some familiarity with the original map; the quasi-geographic positions may need explaining (Spatial pp. 22, 26). Our reading: a circle may sit some distance from its region's true location, so readers find regions by position and label alone. Our reading: circle areas are compared less precisely than lengths, so close values are hard to rank.

## Arrange
Each region becomes a circle, a point mark, sized by the value through its span in a polar local layout; the circles touch, in the original map's global layout, usually rectilinear (Spatial p. 22). The circles are packed under constraints that keep them near their regions: the algorithm strongly preserves the regions' relative order and loosely keeps each circle close to its true location, so order and position vary without encoding anything (Spatial p. 22). Orientation and symbol are uniform, since every mark is a circle, and colour may encode another attribute or stay uniform, as in Munzner's example of US states in red or blue (Spatial p. 22).
