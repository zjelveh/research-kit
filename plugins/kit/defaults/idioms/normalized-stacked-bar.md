---
id: normalized-stacked-bar
name: Normalized stacked bar chart
origin: munzner
group: orientation
order: 140
kind: idiom
form: encoding
medium: [static, interactive]
shape: 2-keys
data:
  keys: [{type: categorical}, {type: categorical}]
  values: [{type: quantitative}]
  optional: []
tasks: [part-to-whole]
marks: [{level: 1, mark: point}, {level: 2, mark: glyph}]
channels:
  encoded:
    - {channel: position-common, carries: main key, where: horizontal at equal intervals}
    - {channel: length, carries: share of the bar's total, where: segment height}
    - {channel: hue, carries: stacked key, where: segment fill}
  uniform: [{channel: length, where: total bar height}, {channel: size, where: bar width}]
  varying: [{channel: position-common, where: vertical start of each middle segment}]
  inherited: [{channel: hue, where: whole bar from its segments}]
scale: {note: null}
see_also:
  - id: pie-chart
    when: There is a single whole with two or a few parts (Layout p. 41).
  - id: stacked-bar
    when: The totals matter as well as the shares.
sources: [Layout p. 20, Layout p. 41, Layout p. 44]
---

## Helps
Serves part-to-whole judgements: each bar is a stacked bar stretched to the full height, so the relative sizes of its segments show proportions (Layout p. 44). One such bar carries what a whole pie carries, in a narrow rectangle instead of a large circle, which gives a high information density (Layout p. 44). Munzner's example fits a bar for every US state into one view, each split into seven age groups (Layout p. 44). Our reading: the bottom segments share the baseline and the top segments share the top edge, so the first and last parts compare across bars as easily as plain bars.

## Hides
Our reading: the totals disappear, since a small whole and a large one get bars of the same height, so show the totals elsewhere when they matter. Our reading: middle segments start at a different height in each bar, so they are hard to compare across bars. Our reading: as in a stacked bar chart, only a modest number of segments per bar stay readable.

## Arrange
A stacked bar chart normalized to the full vertical height (Layout p. 44). Our reading: a list of bars along one axis, one per level of the main key, with the second key stacked inside each bar; segments touch and do not overlap. In Munzner's example the plain stacked bars are sorted by total population, California first, and the normalized bars appear in a different order (Layout p. 44). In a stacked bar chart each segment is a point mark, each bar is a glyph made of them, and the bar takes its colour from its segments (Layout p. 20). Our reading: the normalized chart keeps those marks and channels.
