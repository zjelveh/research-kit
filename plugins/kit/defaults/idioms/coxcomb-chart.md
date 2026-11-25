---
id: coxcomb-chart
name: Coxcomb chart
origin: munzner
group: orientation
order: 370
kind: idiom
form: encoding
medium: [static, interactive]
shape: 1-key
data:
  keys: [{type: categorical}]
  values: [{type: quantitative}]
  optional: []
tasks: [part-to-whole]
marks: [{level: 1, mark: point}]
channels:
  encoded:
    - {channel: position-unaligned, carries: key, where: angle of each wedge at equal intervals}
    - {channel: position-unaligned, carries: value, where: radial position of each wedge's outer edge}
    - {channel: length, carries: value, where: radial span from the centre}
    - {channel: hue, carries: key, where: wedge fill}
  uniform: [{channel: tilt, where: angular spread of every wedge}]
  varying: [{channel: area, where: wedge area}]
  inherited: []
scale: {note: null}
see_also:
  - id: pie-chart
    when: Angular spread should carry the value, with every wedge reaching the same radius (Layout p. 37).
  - id: radial-bar-chart
    when: A polar layout is wanted without the area distortion; radial bars keep a uniform width (Layout p. 38).
  - id: bar-chart
    when: Values must be compared accurately; uniform width keeps a bar's area linear with its length (Layout p. 38).
sources: [Layout p. 37, Layout p. 38, Layout p. 39, Layout p. 55]
---

## Helps
Serves part-to-whole judgements for one categorical key and one quantitative value, as the pie chart does (Layout p. 37). It is a more direct analog of the bar chart in a polar layout: each value is a radial length out from the centre, with the key at equal angles (Layout p. 37). Our reading: with a cyclic key, such as the months in Nightingale's diagram, the wedges run around the circle in order and the year closes on itself.

## Hides
Wedges widen as their radial length grows, so a wedge's area grows nonlinearly with the length that encodes its value (Layout p. 38). The value is encoded as a 1D radial length but perceived as a 2D area: two lines drawn across one wedge at different distances from the centre differ in length, where on a bar they match (Layout p. 38). Radial distance is read less precisely than aligned rectilinear position (Layout p. 55). Our reading: small values shrink to slivers near the centre, and large values take up more of the picture than their size warrants.

## Arrange
Wedges share one centre at equal angles, share borders and do not overlap; every wedge has the same angular spread (Layout p. 37). Munzner's text orders the wedges by the value, but her figure runs clockwise from the top in clarity order (Layout p. 37). Florence Nightingale invented the idiom, also called a Nightingale rose or polar area chart, for her monthly diagram of the causes of army deaths in the East (Layout p. 39). In that diagram the wedges for three causes of death are each measured from the centre, so within a month they overlap, and its note says the wedges show the deaths area for area (Layout p. 39). Our reading: sizing wedges by area, as Nightingale did, rather than by radial length avoids the gap between the encoded length and the perceived area.
