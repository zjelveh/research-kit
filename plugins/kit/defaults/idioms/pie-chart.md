---
id: pie-chart
name: Pie chart
origin: munzner
group: orientation
order: 350
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
    - {channel: tilt, carries: value, where: angular spread of each wedge}
    - {channel: hue, carries: key, where: wedge fill}
  uniform:
    - {channel: position-unaligned, where: radial position}
    - {channel: length, where: radial span of every wedge}
    - {channel: shape, where: wedge symbol}
  varying: [{channel: position-unaligned, where: angular position of every wedge after the first}]
  inherited: []
scale: {note: Two or a few key levels; several are doubtful when details matter and many fail (Layout p. 43).}
see_also:
  - id: normalized-stacked-bar
    when: There are many wholes to show side by side; one normalized bar carries what one pie carries in far less space (Layout p. 44).
  - id: bar-chart
    when: There are several levels and the details matter (Layout p. 42).
  - id: coxcomb-chart
    when: Each value should be a radial length at equal angles, closer to a bar chart (Layout p. 37).
  - id: stacked-bar
    when: Each whole is split by a second key and the totals matter too.
sources: [Layout p. 37, Layout p. 40, Layout p. 41, Layout p. 42, Layout p. 43, Layout p. 44, Layout p. 55]
---

## Helps
Serves part-to-whole judgements for one categorical key and one quantitative value (Layout p. 37). It works reasonably for two or a few levels, for that task (Layout p. 41). There is some evidence that viewers judge a wedge by its arc length rather than its angle, and perhaps by its area (Layout p. 40). A donut chart, a pie with its centre cut out, does no worse than a pie (Layout p. 40).

## Hides
With several levels it is doubtful when details matter: in Munzner's example three pies of five wedges look alike, while bar charts of the same values show one set rising, one flat and one falling (Layout p. 42). With many levels, as in a pie of US state populations, it fails (Layout p. 43). Angular position is read less precisely than rectilinear position (Layout p. 55). Our reading: wedges are compared by angle or arc around the circle, not along a shared baseline, so close values are hard to rank and small wedges leave little room for labels. Our reading: each wedge after the first starts where the one before it ends, so its angular position does not carry its own value, as with the upper segments of a stacked bar.

## Arrange
Wedges around one centre that share borders and do not overlap; each wedge is a parametrized point mark, structurally the same as a bar (Layout p. 37). The wedges differ in angular position and spread, while their radial position, span and symbol are the same (Layout p. 37). In Munzner's example the wedges run clockwise from the top in order of the key, clarity, and are coloured by it (Layout p. 37). Our reading: together the wedges fill the circle.
