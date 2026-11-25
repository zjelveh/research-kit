---
id: aggregate
name: Aggregate
origin: munzner
group: reduce
order: 410
kind: design-choice
form: view
medium: [static, interactive]
shape: any-data
data: {keys: [], values: []}
tasks: [distribution]
marks: null
channels: null
changes: >-
  The aggregation level, which Munzner lists among the choices a view can change (Interact p. 6). For a
  histogram, the bin size can be controlled on the fly (Reduce p. 10). Our reading: in a static figure
  the designer fixes the aggregation level.
fixed: >-
  The original table: aggregation derives a new one, which for a histogram has bins as keys and counts
  as values (Reduce p. 10). Our reading: the original items are not deleted; they are drawn only through
  the derived elements.
scale:
  note: >-
    A box plot scales to an unlimited number of items (Reduce p. 15). A continuous scatterplot has no
    limit on overplotting and scales to millions of items (Reduce p. 16).
see_also:
  - id: filter
    when: Some items or attributes can be removed instead of combined; filtering is another way to reduce (Reduce p. 3).
  - id: histogram
    when: Items are counted in bins of one attribute, to find its distribution (Reduce p. 10).
  - id: choropleth-map
    when: Items are aggregated by region; changing the boundaries can change the result dramatically (Reduce p. 17).
  - id: bar-chart
    when: The values are given in the data, not derived counts; a histogram looks like a bar chart but counts items per bin.
  - id: one-to-one-dot-map
    when: Each item is drawn at its own location instead of aggregated by region.
sources: [Interact p. 6, Reduce p. 3, Reduce p. 5, Reduce p. 9, Reduce p. 10, Reduce p. 15, Reduce p. 16, Reduce p. 17, Reduce p. 18]
---

## Helps
Aggregation informs about the whole set (Reduce p. 5). Aggregation replaces a group of items or attributes with fewer elements derived from them (Reduce p. 9). A histogram, a static item aggregation, serves the task of finding a distribution (Reduce p. 10).

## Hides
Aggregation makes it difficult to avoid losing signal (Reduce p. 5). In a histogram the choice of bin size matters greatly, since another discretization can show a very different pattern (Reduce p. 10). In spatial aggregation, the modifiable areal unit problem means that redrawing the regions' boundaries can change the result a great deal, through zone and scale effects (Reduce p. 17). Gerrymandering uses it for political gain: Munzner's figure divides 50 people, 60 percent blue, into five districts three ways, which gives three blue districts, five, or two (Reduce p. 18).

## Views
Munzner's icons show items aggregated as rows merged into fewer rows, and attributes as columns merged into fewer columns (Reduce p. 9). Filtering and aggregation are not mutually exclusive: they can be combined with each other, and with change and facet (Reduce p. 5). Our reading: aggregation reduces what one view shows, so the aggregated view can stand alone in a static figure.
