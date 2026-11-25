---
id: select
name: Select
origin: munzner
group: manipulate
order: 490
kind: design-choice
form: view
medium: [interactive]
shape: any-data
data: {keys: [], values: []}
tasks: [lookup]
marks: null
channels: null
changes: >-
  Which items are selected. The choices include how many selection types to offer: click or tap,
  hover, several click types such as shift-click, and proximity beyond click and hover, from touching to
  nearby to distant (Interact p. 16). They also include whether a selection adds to the set or replaces
  it, whether it can be empty, as when a click on the background selects nothing, and whether there are
  primary and secondary selections, such as source and target nodes, or group membership
  (Interact p. 16).
fixed: >-
  Munzner doesn't say. Our reading: until a highlight or another change responds to it, the data, the
  encoding and the layout stay the same.
scale: {note: null}
see_also:
  - id: highlight
    when: The question is how the view shows what was selected; highlighting is feedback separable from selection (Interact p. 17).
sources: [Interact p. 15, Interact p. 16, Interact p. 17]
---

## Helps
Selection is the basic operation for most interaction (Interact p. 16). A design can offer several selection types, such as click or tap, hover, and click types such as shift-click (Interact p. 16). Our reading: the selection picks the items that a highlight, a tooltip or a linked view then acts on.

## Hides
Hover, the lightweight way to select, is not available on most touchscreens, where there is no hover, just tap (Interact pp. 15, 16). Clicking or tapping is heavyweight (Interact p. 16). Our reading: a selection made by hovering ends as soon as the pointer moves, so it cannot be kept while the reader looks elsewhere.

## Views
Our reading: selection works in one view, or across several when a selection drives linked views. Munzner's icon for selection shows one scatterplot before and after a pointing hand selects one dot (Interact p. 16). Desktop mice allow hover and several kinds of click; phones allow only a tap (Interact p. 15).
