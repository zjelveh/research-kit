---
id: filter
name: Filter
origin: munzner
group: reduce
order: 420
kind: design-choice
form: view
medium: [static, interactive]
shape: any-data
data: {keys: [], values: []}
tasks: [lookup]
marks: null
channels: null
changes: >-
  Which items or attributes are shown (Reduce p. 6). Any rule that splits the data in two will do,
  such as attribute values bigger or smaller than a threshold, or noise against signal (Reduce p. 6).
  Filters start with everything and remove elements, while queries start with nothing and add
  elements (Reduce p. 6).
fixed: >-
  Our reading: the encoding stays the same, and the kept items move only if the axes change range. In
  FilmFinder the axes do change: after filtering, the year axis runs from about 1960 to 1995 and the
  popularity axis from about 4 up (Reduce p. 7).
scale:
  note: Whether to filter or to query depends on the dataset's size (Reduce p. 6).
see_also:
  - id: aggregate
    when: The whole set should stay in view; aggregation informs about it but can lose signal (Reduce p. 5).
  - id: cross-filtering
    when: Several coordinated views should filter one another (Reduce p. 8).
  - id: change
    when: What is filtered should change as the reader works, one of the view's changes (Interact p. 6).
sources: [Reduce p. 4, Reduce p. 5, Reduce p. 6, Reduce p. 7, Reduce p. 8, Interact p. 6]
---

## Helps
Filtering is straightforward and intuitive, both to understand and to compute (Reduce p. 4). In FilmFinder, dynamic query filters are tightly coupled with the visual encoding, so the reader sees the result of each action immediately (Reduce p. 7). In its figure, choosing one actor and a narrower range of lengths cuts the films shown from 1455 to 24, and the remaining films are labelled with their titles (Reduce p. 7).

## Hides
Filtered items are out of sight, and so out of mind (Reduce p. 4). Our reading: inferring what is missing from what is shown is hard, even for the reader who set the filter. Our reading: a filtered view gives no sign of how much was removed unless it reports a count, as FilmFinder does with its count of films shown. Our reading: a static figure filters once, so it must say what it dropped, in the caption or a note.

## Views
One view with its controls: in FilmFinder, a scatterplot of films by year of production and popularity, coloured by genre, has beside it sliders for title, actor, actress and director, a range slider for length, checkboxes for ratings and buttons for genres (Reduce p. 7). Filtering and aggregation are not mutually exclusive, and both can be combined with change and facet (Reduce p. 5).
