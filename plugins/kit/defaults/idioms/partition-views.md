---
id: partition-views
name: Partition into views
origin: munzner
group: facet
order: 180
kind: design-choice
form: view
medium: [static, interactive]
shape: multiple-views
data: {keys: [{type: categorical}], values: []}
tasks: [compare-values]
marks: null
channels: null
changes: >-
  The order of the splits and the encoding in the regions: HIVE can switch the order of splits, to type
  then neighbourhood, and switch the colour, to price variation (Interact p. 51). Second-level regions can
  have a different encoding, such as choropleth maps (Interact p. 52).
fixed: >-
  In HIVE's type-first layout, each of the four type blocks repeats the same grid of neighbourhoods
  (Interact p. 51). Our reading: partitioned views usually share one encoding, and every item appears in
  exactly one region.
scale: {note: null}
see_also:
  - id: small-multiples
    when: Each region should be its own chart, as in small-multiple bar charts split by age (Interact p. 49).
  - id: choropleth-map
    when: The second-level regions should be maps, as in HIVE's choropleth maps (Interact p. 52).
  - id: superimposed-layers
    when: Some levels should share one frame instead of being split, as the years do in a trellis plot (Interact p. 56).
  - id: bar-chart
    when: There is one split only, a single bar chart with one key.
sources: [Interact p. 48, Interact p. 49, Interact p. 50, Interact p. 51, Interact p. 52, Interact p. 56]
---

## Helps
Splitting by attributes puts related items near each other, so position shows which belong together (Interact p. 48). A grouped bar chart split by state makes comparison easy within a state, and small-multiple bar charts split by age make it easy within an age group (Interact p. 49). Split by neighbourhood first, Munzner's house-price example shows where it is expensive and where detached houses cost much more (Interact p. 50). Split by type first and coloured by price variation, it shows which neighbourhoods are inconsistent within a type (Interact p. 51).

## Hides
Which attribute splits first decides which patterns the reader can see (Interact p. 48). Each order makes some comparisons hard: grouped bars split by state are hard to compare across ages, and small multiples split by age are harder to compare across states (Interact p. 49). Our reading: each further split makes more, smaller regions, so after several splits each view is small.

## Views
Side-by-side views, one per region (Interact p. 48). The regions can also sit inside one chart, as in grouped bars, where each state's region holds a complex glyph showing all ages (Interact p. 49). Partitioning can be recursive: HIVE splits by neighbourhood, then by type, then by time, with years as rows and months as columns (Interact p. 50).
