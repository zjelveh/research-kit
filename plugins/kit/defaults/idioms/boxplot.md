---
id: boxplot
name: Box plot
origin: munzner
group: reduce
order: 70
kind: idiom
form: encoding
medium: [static, interactive]
shape: 1-key
data:
  keys: [{type: categorical}]
  values: [{type: quantitative}]
  optional: []
  intervals: true
tasks: [distribution]
marks: [{level: 1, mark: point}, {level: 1, mark: line}]
channels:
  encoded:
    - {channel: position-common, carries: key, where: one axis at equal intervals}
    - {channel: position-common, carries: median, where: central line}
    - {channel: position-common, carries: lower and upper quartiles (role interval), where: ends of the box}
    - {channel: position-common, carries: lower and upper fences (role interval), where: ends of the whiskers}
    - {channel: position-common, carries: outliers, where: points beyond the whiskers}
  uniform: [{channel: size, where: box width}, {channel: hue}]
  varying: []
  inherited: []
scale: {note: Unlimited number of items (Reduce p. 15).}
see_also:
  - id: histogram
    when: The shape of one distribution matters, such as whether it has more than one mode.
  - id: interval-plot
    when: Each group has one estimate with an interval, not a spread of items.
sources: [Reduce p. 5, Reduce p. 15, Layout p. 18]
---

## Helps
Shows a distribution through five derived values: the median, the lower and upper quartiles, and the lower and upper fences (Reduce p. 15). Items beyond the fences are drawn explicitly as outliers (Reduce p. 15). It scales to an unlimited number of items (Reduce p. 15). Our reading: boxes side by side on a shared value axis make the centres and spreads of several groups easy to compare.

## Hides
Our reading: the five values say nothing about the shape between them, so a distribution with two modes can have the same box as one with a single mode. Aggregation makes it difficult to avoid losing signal (Reduce p. 5). Our reading: the box does not show how many items each distribution holds, so a box drawn from a handful of items looks as solid as one drawn from thousands. Our reading: the rule that sets the fences, often 1.5 times the interquartile range beyond the box, is not visible in the marks, so the caption should state it.

## Arrange
Each distribution is one box: a central line at the median, a box from the lower to the upper quartile, whiskers out to the fences, and points for the outliers beyond them (Reduce p. 15). Munzner's example puts four boxes side by side, one per distribution, on a shared vertical value axis (Reduce p. 15). A categorical key needs an ordering: by name, or by a value used elsewhere in the encoding, such as the median (Layout p. 18). Our reading: the violin plot is a variant that draws each distribution as a mirrored density curve, which shows the modes a box hides; its smoothing, like a histogram's bin size, can change the shape. Our reading: a figure spec lists the median as the value, and the quartiles and fences as attributes with role interval, as for an interval plot.
