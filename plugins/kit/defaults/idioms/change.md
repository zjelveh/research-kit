---
id: change
name: Change the view
origin: munzner
group: manipulate
order: 500
kind: design-choice
form: view
medium: [interactive]
shape: any-data
data: {keys: [], values: []}
tasks: [lookup]
marks: null
channels: null
changes: >-
  Any of the view's other design choices: the encoding itself, its parameters, the arrangement or
  order, the aggregation level, or what is filtered (Interact p. 6). Parameters are set with widgets
  and controls, such as sliders, buttons, radio buttons, checkboxes and dropdowns (Interact p. 8).
fixed: >-
  Munzner doesn't say. Our reading: the dataset stays the same; what changes is how it is drawn, or
  which part of it is shown.
scale: {note: null}
see_also:
  - id: change-order
    when: The change is to the order of the items (Interact p. 6).
  - id: small-multiples
    when: Several states should sit side by side, so the reader moves the eyes instead of remembering the earlier state (Interact p. 42).
  - id: filter
    when: The change is to which items are shown (Interact p. 6).
  - id: aggregate
    when: The change is to the aggregation level (Interact p. 6).
sources: [Interact p. 3, Interact p. 6, Interact p. 7, Interact p. 8, Interact p. 26, Interact p. 27, Interact p. 42]
---

## Helps
Changing the view is powerful and flexible: any other design choice can change, from the encoding and its parameters to the order, the aggregation level and the filter (Interact p. 6). Different encodings support different tasks, so changing the encoding lets one view serve several tasks in turn (Interact p. 26). Our reading: a changed view serves the task of the new view, and the reader can look up what the earlier view hid. Widgets and controls have clear affordances, and with labels they document themselves (Interact p. 8).

## Hides
A changed view replaces the earlier one, so comparing the two relies on the reader's memory of the earlier state, which adds cognitive load (Interact pp. 27, 42). Readers may not interact as the designer planned: New York Times logs show that about 90 percent of readers do not interact beyond scrolling through a story (Interact p. 27). Our reading: a reader who never changes the view sees only its first state, so that state has to work on its own. Widgets and controls use screen space (Interact p. 8).

## Views
One view that changes over time (Interact p. 3). Controls and the canvas can be kept separate or interleaved, a design choice (Interact p. 8). In Munzner's re-encode example, one table of sales is drawn several ways in Tableau, among them bars for each product category, the same bars split by region, and a map of store locations (Interact p. 7). In her change-parameters example, a map of railroads and cities in a chosen year has its controls below the map, among them a year slider and a button that plays the sequence (Interact p. 8).
