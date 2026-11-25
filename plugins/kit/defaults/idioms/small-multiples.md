---
id: small-multiples
name: Small multiples
origin: munzner
group: facet
order: 90
kind: idiom
form: view
medium: [static, interactive]
shape: multiple-views
data: {keys: [{type: categorical}], values: []}
tasks: [compare-values, trend]
marks: null
channels: null
changes: >-
  Our reading: in a static set of small multiples nothing changes. Interactive small multiples add
  linked highlighting of the analogous item or attribute across views: hovering in any chart highlights
  the same year in all of them (Interact p. 40).
fixed: >-
  The encoding is the same in every view, such as a line chart, and no data is shared: each view shows
  a different slice of the dataset, by items or by attributes (Interact p. 39). In Munzner's MetaFilter
  example every chart has the same vertical axis, from 0 to 3,000 (Interact p. 40).
scale:
  note: >-
    Our reading: the display limits how many views fit, since each added view takes a share of its
    area.
see_also:
  - id: change
    when: One view changes instead; comparing it with memory of the earlier state costs more than moving the eyes between views (Interact p. 42).
  - id: overview-detail
    when: The views share one encoding and a subset of the data (Interact p. 45).
  - id: linked-highlighting
    when: The views should be linked by the analogous item or attribute (Interact p. 40).
  - id: superimposed-layers
    when: A few series should share one frame for local comparisons (Interact p. 57).
  - id: partition-views
    when: The choice is which attribute splits the data into views (Interact p. 49).
  - id: glyphmap
    when: Many small charts are placed on a map, or packed densely as glyphs.
sources: [Interact p. 39, Interact p. 40, Interact p. 42, Interact p. 44, Interact p. 45, Interact p. 49, Interact p. 57]
---

## Helps
Moving the eyes between juxtaposed views costs less cognitive load than comparing one changing view with memory of its earlier state (Interact p. 42). Small multiples are easier to compare than an animation, which is hard to follow when many parts change at once or it runs long (Interact p. 44). In Munzner's Cerebral example, each view keeps the same layout of the genes and shows a different experimental condition in colour (Interact p. 44).

## Hides
Each juxtaposed view gets a share of the display; two views get half each (Interact p. 42). In small-multiple bar charts split by age, comparing within an age group is easy, but comparing the age groups of one state, across charts, is harder (Interact p. 49). Our reading: each chart is small, so fine detail and exact values are hard to read. Our reading: charts far apart in the grid are harder to compare than neighbours, so the order of the charts matters.

## Views
Several small views side by side, each with the same encoding and a different slice of the data (Interact p. 39). In Munzner's stock-price example, seven line charts, one per series, are stacked one above another (Interact p. 39). In her MetaFilter example, 15 charts, one per category, sit in five columns and three rows (Interact p. 40). Partitioning by an attribute into one chart per region gives small multiples, as in bar charts split by age (Interact p. 49).
