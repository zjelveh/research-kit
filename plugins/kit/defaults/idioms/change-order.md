---
id: change-order
name: Change order
origin: munzner
group: manipulate
order: 510
kind: idiom
form: view
medium: [interactive]
shape: any-data
data: {keys: [], values: []}
tasks: [compare-values, relationship]
marks: null
channels: null
changes: >-
  The order of the items, by data-driven reordering (Interact p. 9). In a table with many attributes,
  the reader selects the column that sets the order (Interact p. 10). In stacked bars, the segment the
  bars are aligned to can change (Interact p. 11).
fixed: >-
  In Munzner's letter example each bar keeps its height; only the order changes, from A to Z to tallest
  first (Interact p. 9). Our reading: the encoding stays the same.
scale: {note: null}
see_also:
  - id: change
    when: Something other than the order should change, such as the encoding, a parameter, the filter or the aggregation level (Interact p. 6).
  - id: stacked-bar
    when: Parts of each whole are stacked in bars, where only the first segment and the total compare easily (Interact p. 11).
  - id: bar-chart
    when: One fixed order is chosen by the designer, such as bars sorted by value.
  - id: heatmap
    when: The rows and columns of a matrix are reordered so that similar items sit together.
sources: [Interact p. 6, Interact p. 9, Interact p. 10, Interact p. 11, Layout p. 18]
---

## Helps
Reordering the items by a value helps find extreme values and trends (Interact p. 9). In a table with many attributes, reordering by a column the reader selects helps find correlations between attributes: in Munzner's example the sorted column falls in a smooth staircase, and another column in a rougher one (Interact p. 10). In stacked bars only the first segment and the total bar are easy to compare; aligning to another segment lets the reader compare that segment across bars instead (Interact p. 11).

## Hides
Sorting by value gives up alphabetical order, the one that is good for lookup by name (Layout p. 18). Our reading: each new order moves every item, so a reader following one item has to find it again. Our reading: aligned to a middle segment, stacked bars no longer share a start, so the first segments and the totals become hard to compare.

## Views
One view with a control: in Munzner's letter-frequency example, a Sort values checkbox switches the bars between alphabetical and sorted order (Interact p. 9). In DataStripes, the reader selects the column to sort the table by (Interact p. 10). In LineUp, the stacked bars can be aligned to a different segment (Interact p. 11).
