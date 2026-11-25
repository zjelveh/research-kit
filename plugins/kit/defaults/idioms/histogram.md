---
id: histogram
name: Histogram
origin: munzner
group: reduce
order: 50
kind: idiom
form: encoding
medium: [static, interactive]
shape: 1-key
data:
  keys: [{type: ordinal}]
  values: [{type: quantitative}]
  optional: []
tasks: [distribution]
marks: [{level: 1, mark: point}]
channels:
  encoded:
    - {channel: position-common, carries: bin (key), where: horizontal in bin order}
    - {channel: position-common, carries: count, where: top of each bar}
    - {channel: length, carries: count, where: bar height}
  uniform: [{channel: size, where: bar width}, {channel: hue}]
  varying: []
  inherited: []
scale: {note: null}
see_also:
  - id: bar-chart
    when: The key is categorical and the values are given in the data, not counted.
  - id: boxplot
    when: Several distributions are compared side by side and a summary of each is enough.
  - id: aggregate
    when: The choice to make is what to aggregate and at what level.
  - id: cross-filtering
    when: Several histograms are linked, so a range set in one filters the items in the others.
sources: [Reduce p. 5, Reduce p. 10]
---

## Helps
Shows how the items are distributed over one attribute: they are counted into bins, giving a derived table whose keys are the bins and whose values are the counts (Reduce p. 10). This aggregation informs about the whole set (Reduce p. 5). Our reading: with the bins in order, the shape of the distribution shows at a glance: where it peaks, how widely it spreads, and whether it is skewed or has more than one mode.

## Hides
The bin size is crucial, since dividing the attribute into bins differently can change the pattern a great deal (Reduce p. 10). Munzner sees an opportunity for interaction here, a control that changes the bin size on the fly (Reduce p. 10). Aggregation makes it difficult to avoid losing signal (Reduce p. 5). Our reading: the items within a bin cannot be told apart, so a gap or a cluster narrower than a bin does not show.

## Arrange
Munzner's example draws one bar per bin, with the bins in order along the horizontal axis and the count as each bar's height (Reduce p. 10). Our reading: in a static figure the bin size is fixed, so the caption should give it. Our reading: a density plot is a variant that draws a smoothed curve in place of the bars; its bandwidth, like the bin size, can change the pattern.
