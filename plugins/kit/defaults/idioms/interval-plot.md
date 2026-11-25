---
id: interval-plot
name: Interval plot
origin: kit
group: keys
order: 30
kind: idiom
form: encoding
medium: [static]
shape: 1-key
data:
  keys: [{type: categorical}]
  values: [{type: quantitative}]
  optional: [{type: categorical, channel: hue}]
  intervals: true
tasks: [compare-values, trend]
marks: [{level: 1, mark: point}, {level: 1, mark: line}]
channels:
  encoded:
    - {channel: position-common, carries: key, where: one axis at equal intervals}
    - {channel: position-common, carries: estimate, where: the other axis}
    - {channel: position-common, carries: interval bounds, where: ends of the segment}
  uniform: [{channel: hue}, {channel: shape}, {channel: size, where: point size}]
  varying: []
  inherited: []
scale: {note: null}
see_also:
  - id: bar-chart
    when: Values are exact counts or totals with no interval and a meaningful zero.
  - id: line-chart
    when: The key is ordered and the trend matters more than each estimate's uncertainty.
sources: [Layout p. 18, Layout p. 19, Layout p. 23, Marks p. 9]
---

## Helps
Our reading: compares estimates across the levels of one key with each estimate's uncertainty in view, which a table of coefficients hides. Each estimate is a point mark and each interval a line mark, both placed by position on a common scale, the channel Munzner ranks most effective for ordered values (Marks p. 9). Our reading: a reference line, usually at zero, shows at a glance which intervals exclude it. Our reading: on an ordered key, such as time relative to an event, the same layout shows how the estimate changes across the key, as in an event-study plot.

## Hides
Our reading: the marks do not say what the interval is, such as a confidence interval or one standard error, so the caption or a legend must. Our reading: two intervals that overlap do not show that the two estimates are not significantly different, and readers often read them that way. A categorical key needs an ordering: by name, which is good for lookup but hides trends and the distribution, or by a value shown in the figure, such as the estimate (Layout p. 18). Joining the points with a line implies a trend so strongly that lines suit only ordered keys (Layout p. 23). Our reading: on an ordered key a line also implies values between key levels, which misleads when the levels are few or unevenly spaced.

## Arrange
A list along one axis, one key level at equal intervals as in a bar chart, with the estimate and its interval on the other axis (Layout p. 19). Our reading: the key may run horizontally, as in an event-study plot, or vertically, as in a coefficient or forest plot, where long labels fit. Our reading: several estimates per key level, such as one per estimator, are offset slightly along the key axis and told apart by hue and shape, or put in small multiples. Our reading: the marginal-effects plot is a variant along a quantitative key, with a line for the estimate and a band for its interval.
