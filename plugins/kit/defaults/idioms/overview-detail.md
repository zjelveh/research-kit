---
id: overview-detail
name: Overview and detail
origin: munzner
group: facet
order: 440
kind: idiom
form: view
medium: [interactive]
shape: multiple-views
data: {keys: [], values: []}
tasks: [lookup]
marks: null
channels: null
changes: >-
  Navigation is shared between the views, and in Munzner's map example the linking is bidirectional, so
  moving either view moves the other (Interact p. 36). In her time-series example, the reader selects
  in the small overview and the extent of the large detail view changes (Interact p. 37).
fixed: >-
  The views share a subset of the data, from their different viewpoints, and their encoding may be the
  same or different; in the map it is the same bird's-eye map (Interact p. 36). The time-series example
  has the same properties: the encoding same or different, a subset of the data shared, and navigation
  shared (Interact p. 37).
scale: {note: null}
see_also:
  - id: small-multiples
    when: The views share one encoding but no data (Interact p. 45).
  - id: navigate
    when: One view is panned and zoomed, without an overview beside it.
  - id: linked-highlighting
    when: The views share all the items and differ in the attributes they show.
  - id: focus-context
    when: The focus and its context should sit in one view instead of two.
sources: [Interact p. 36, Interact p. 37, Interact p. 42, Interact p. 45]
---

## Helps
Our reading: the reader can study one part closely and still see where it sits in the whole. In Munzner's map example, a small map of all of New Zealand sits in the corner of a larger map of one region, with a rectangle marking the part the large map shows (Interact p. 36). In her time-series example, a selection in a small overview sets the extent of a large detail view (Interact p. 37).

## Hides
Our reading: the overview is small, so it shows only the coarse shape of the data, and the detail view shows only one part at a time. Each juxtaposed view gets a share of the display; two views get half each (Interact p. 42). Our reading: comparing two distant parts in detail means moving the extent back and forth.

## Views
Two views that differ in window size: a small overview and a large detail view (Interact pp. 36, 37). The linking can run both ways, as in the map, or one way, from the overview to the detail view, as in the time series (Interact pp. 36, 37). In Munzner's table of coordination choices, overview and detail is the column where a subset of the data is shared, with the same encoding or with different ones (Interact p. 45).
