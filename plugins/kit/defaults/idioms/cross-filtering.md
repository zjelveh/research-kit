---
id: cross-filtering
name: Cross filtering
origin: munzner
group: reduce
order: 460
kind: idiom
form: view
medium: [interactive]
shape: multiple-views
data: {keys: [], values: [{type: quantitative}, {type: quantitative}]}
tasks: [distribution, relationship]
marks: null
channels: null
changes: >-
  The reader sets a range in any histogram to filter the items, and all the scented histogram bisliders
  update (Reduce p. 8). In Munzner's figure, late hours from about 21 to 24 are selected in the
  time-of-day histogram, whose bars inside the range are blue and the rest grey (Reduce p. 8). Our
  reading: the other three histograms, all blue, show only the selected items.
fixed: >-
  Our reading: each histogram keeps its attribute, its bins and its axis. Our reading: in Munzner's
  coordination terms, the histograms share all the items and show different attributes, as linked
  highlighting does.
scale: {note: null}
see_also:
  - id: filter
    when: Only one view, with its own controls, needs filtering.
  - id: linked-highlighting
    when: The selected items should be highlighted in the other views instead of filtering out the rest.
  - id: aggregate
    when: The choice is what to aggregate and at what level.
sources: [Reduce p. 8, Reduce p. 10]
---

## Helps
Cross filtering combines coordinated views and controls: each histogram shows an attribute and is also a slider for filtering the items by it (Reduce p. 8). Our reading: the reader sees at once how the items in a range of one attribute are distributed on the others. Each histogram is an aggregation for finding a distribution, with bins as keys and counts as values (Reduce p. 10).

## Hides
Our reading: items outside the selected range drop out of the other views, so the reader has to keep in mind what the filter removed. Our reading: when the other histograms show only the selected items, as in Munzner's figure, they show how those items are distributed but not what share of the whole they are. Our reading: with many attributes each histogram is small, and the bars for a small selection can be too short to read.

## Views
The views are also the controls: coordinated views and controls are combined (Reduce p. 8). Munzner's example has four histograms, of time of day, arrival delay, distance and date, with date running the full width (Reduce p. 8). A range set in any histogram updates all the others, so the linking runs in every direction (Reduce p. 8).
