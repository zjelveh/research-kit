---
id: highlight
name: Highlight
origin: munzner
group: manipulate
order: 480
kind: design-choice
form: view
medium: [interactive]
shape: any-data
data: {keys: [], values: []}
tasks: [compare-values]
marks: null
channels: null
changes: >-
  The encoding of the selected items, on typical channels: a change of colour, an added outline mark, a
  change of size, such as a thicker outline, or a change of shape, such as a link line from solid to
  dashed (Interact p. 17).
fixed: >-
  The selection: highlighting is visual feedback tied closely to the selection but separable from it
  (Interact p. 17). Our reading: the data and the layout stay the same, and unselected items keep their
  encoding or are faded so the selection stands out more.
scale: {note: null}
see_also:
  - id: select
    when: The question is how the reader picks the items; selection comes first and is separable from highlighting (Interact p. 17).
  - id: superimposed-layers
    when: The selected items should form a layer of their own over the rest, as in one-hop neighbour highlighting (Interact p. 58).
  - id: linked-highlighting
    when: The same items should be highlighted in several views at once.
sources: [Interact p. 17, Interact p. 58]
---

## Helps
Highlighting changes the visual encoding of the selected items, so the reader sees what was selected (Interact p. 17). Munzner treats it as separable from selection, so how a selection is shown is a design choice of its own (Interact p. 17). Our reading: a highlight lets the reader compare the selected items with the rest.

## Hides
Changing the colour of the selected items hides the existing colour coding (Interact p. 17). Our reading: if the highlight colour is also used in the encoding, readers cannot tell highlighted items from items that carry that value.

## Views
One view or several: motion is usually avoided in a single view, but with several views it could be justified to draw attention to the others (Interact p. 17). Our reading: in several views, highlighting the same items in each is linked highlighting.
