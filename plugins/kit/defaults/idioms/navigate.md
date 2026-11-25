---
id: navigate
name: 'Navigate: pan and zoom'
origin: munzner
group: manipulate
order: 520
kind: design-choice
form: view
medium: [interactive]
shape: any-data
data: {keys: [], values: []}
tasks: [lookup]
marks: null
channels: null
changes: >-
  The viewpoint, in a camera metaphor: pan, translate or scroll to move up, down or sideways; rotate,
  typically in 3D; and zoom in or out, which enlarges or shrinks the world as the camera moves closer or
  further (Interact p. 22). Zoom can be geometric or semantic (Interact p. 18). In constrained
  navigation the trajectory is computed from a selection, typically with an animated transition
  (Interact p. 23).
fixed: >-
  In Munzner's map example, only the viewport changes and the shapes are preserved (Interact p. 24).
  Our reading: with geometric zoom the data and the encoding stay the same, and only the part in view
  and its size on screen change; semantic zoom also changes how items are drawn.
scale: {note: null}
see_also:
  - id: change
    when: The encoding or a parameter should change, not the viewpoint.
  - id: select
    when: The question is how the reader picks the item that constrained navigation then frames (Interact p. 23).
  - id: focus-context
    when: The focus and its context should stay in one view; Munzner sets it against standard navigation within a view (Reduce p. 31).
sources: [Interact p. 18, Interact p. 22, Interact p. 23, Interact p. 24, Reduce p. 31]
---

## Helps
Navigating changes the viewpoint, and so which items are visible in the view (Interact p. 22). Geometric zoom is the standard kind, like moving a physical object (Interact p. 22). Constrained navigation lets the reader just click: the trajectory is computed from the selection, and the selection ends up framed in the final viewport (Interact p. 23). Our reading: it suits data whose view is larger, or denser, than the screen can show at once, such as a detailed map.

## Hides
Our reading: zoomed in, the reader cannot see the rest of the data, and zoomed out, the details disappear. Unconstrained navigation is easy for the designer to build but hard for the reader to control, since it is easy to overshoot or undershoot (Interact p. 23). Our reading: after zooming and panning across a large dataset, a reader can lose track of where they are.

## Views
One view seen through a camera, whose viewpoint the reader moves (Interact p. 22). Rotation is typically for 3D views (Interact p. 22). Munzner's example is a geographic map with constrained navigation and an animated transition, a zoom to the bounding box of a selected state (Interact p. 24).
