---
id: focus-context
name: Focus and context
origin: munzner
group: reduce
order: 450
kind: design-choice
form: view
medium: [interactive]
shape: any-data
data: {keys: [], values: []}
tasks: [lookup]
marks: null
channels: null
changes: >-
  With elision, as in DOITrees, the view keeps changing which items are hidden, which are merged into
  summaries and which are drawn in full (Reduce p. 28). With distortion, the geometry is distorted
  around the focus: in Munzner's fisheye lens the region is radial, a single local extent under a
  draggable lens, and in Cartesian distortion it is rectilinear (Reduce p. 30). The choices for
  distortion are the region shape, radial, rectilinear or complex; how many regions, one or many; their
  extent, local or global; and the interaction metaphor (Reduce p. 31).
fixed: >-
  Distortion leaves topology comparisons unaffected, such as connection and containment (Reduce p. 32).
  Our reading: with elision the geometry is not distorted, and what changes is which items are shown in
  detail, summarized or hidden; with distortion every item stays in view, and the geometry changes
  around the focus.
scale: {note: null}
see_also:
  - id: navigate
    when: The reader should move through the data instead; Munzner sets focus and context against standard navigation within a view (Reduce p. 31).
  - id: overview-detail
    when: The focus and the context can sit in two views side by side, the multiple-views alternative (Reduce p. 31).
  - id: filter
    when: Items away from the focus can be removed outright, with no need to keep them in view as context.
  - id: aggregate
    when: Summaries of the whole set are enough, with no part of it needed in detail.
  - id: superimposed-layers
    when: The focus can be drawn as a layer over the context instead of distorting it (Reduce p. 32).
sources: [Reduce p. 28, Reduce p. 30, Reduce p. 31, Reduce p. 32]
---

## Helps
Focus and context share one view (Reduce p. 31). Our reading: it helps readers keep track of where they are in a very large dataset.

## Hides
Distortion impairs length comparisons (Reduce p. 32). Its effects are unclear if the original structure is unfamiliar, and tracking objects may be impaired (Reduce p. 32). Our reading: elided items appear only as summary markers, such as the item counts in DOITrees, so their contents cannot be read until the reader expands them.

## Views
One view that combines focus and context, set against standard navigation within a view and against multiple views (Reduce p. 31). Munzner names two ways to embed the focus: elide data, by filtering and aggregating selectively, or distort geometry (Reduce p. 31). Our reading: the focus moves within the view as the reader selects or drags; there is no second view to coordinate.
