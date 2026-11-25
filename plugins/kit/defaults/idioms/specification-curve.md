---
id: specification-curve
name: Specification curve
origin: kit
group: facet
order: 120
kind: idiom
form: encoding
medium: [static]
shape: 1-key
data:
  keys: [{type: categorical}]
  values: [{type: quantitative}]
  optional: [{type: categorical, channel: position-common, repeats: true}]
  intervals: true
tasks: [distribution, relationship]
marks: [{level: 1, mark: point}, {level: 1, mark: line}]
channels:
  encoded:
    - channel: position-common
      carries: specification (key)
      where: horizontal in both views, ordered by the estimate
    - {channel: position-common, carries: estimate, where: vertical in the upper view}
    - channel: position-common
      carries: interval bounds
      where: ends of each segment in the upper view, when shown
    - {channel: position-common, carries: option of each choice, where: rows of the lower view}
  uniform: [{channel: size, where: point size}, {channel: hue}, {channel: shape}]
  varying: []
  inherited: []
scale: {note: null}
see_also:
  - id: interval-plot
    when: There are few specifications, and the choices behind each fit in its label.
  - id: histogram
    when: Only the spread of the estimates matters, not which choices produce them.
  - id: small-multiples
    when: One choice matters most, so the estimates are split into one view per option.
sources: [Interact p. 10, Interact p. 42, Interact p. 45, Layout p. 18, Layout p. 29, Marks p. 9]
---

## Helps
Our reading: shows how one estimate varies across the many specifications of an analysis, and which analytic choices go with high or low estimates. Munzner's reorder idiom sorts a table with many attributes by one of them, to find correlations between attributes (Interact p. 10). Our reading: sorted by the estimate, the lower view works the same way, since its rows show which options gather among the high or the low estimates. Each estimate is a point placed by position on a common scale, the channel Munzner ranks most effective for ordered values (Marks p. 9). Juxtaposed views keep cognitive load low: readers move their eyes between two views instead of comparing one changing view with their memory of its previous state (Interact p. 42).

## Hides
Our reading: sorting by the estimate makes the upper view rise by construction, so its shape shows only how widely the estimates spread; which choices move them must be read column by column from the lower view. Each juxtaposed view gets a share of the display; two views get half each (Interact p. 42). Our reading: with hundreds of specifications the columns grow too narrow to follow one specification from its estimate down to its choices. Our reading: every specification counts the same, so the figure cannot show which are more defensible, and the set of specifications run decides the picture.

## Arrange
Views that share all the data but encode it differently are what Munzner calls multiform (Interact p. 45). Our reading: here the upper view is an interval or dot plot of each specification's estimate, and the lower view a matrix with one row per option of each choice and one column per specification, marked where the specification uses that option. The specifications are ordered by a value shown elsewhere in the figure, the estimate (Layout p. 18). The lower view is a matrix, Munzner's layout for two keys, here the specification and the option (Layout p. 29). Our reading: the views are stacked with the estimate view on top, so both share one horizontal axis and each column lines up across them.
