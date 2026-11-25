---
id: line-chart
name: Line chart
origin: munzner
group: keys
order: 10
kind: idiom
form: encoding
medium: [static, interactive]
shape: 1-key
data:
  keys: [{type: ordinal}]
  values: [{type: quantitative}]
  optional: [{type: categorical, channel: hue}]
tasks: [trend]
marks: [{level: 1, mark: line}]
channels:
  encoded:
    - {channel: position-common, carries: key, where: horizontal}
    - {channel: position-common, carries: value, where: vertical}
    - {channel: connection, carries: succession of key levels}
  uniform: [{channel: size, where: line thickness}, {channel: hue, where: single line}]
  varying: []
  inherited: []
scale: {note: Hundreds of levels for both key and value (Layout p. 22).}
see_also:
  - id: bar-chart
    when: The key is categorical, not ordered (Layout p. 23).
  - id: interval-plot
    when: Each value carries an interval, such as estimates over event time.
sources: [Layout p. 22, Layout p. 23, Layout p. 25, Layout p. 26, Marks p. 22]
---

## Helps
Shows trends along an ordered key, such as time: the path joins successive values, so the change from one key level to the next, and the overall shape, are easy to see (Layout p. 22). Readers are guided to read each connection as a step up or down from the previous point, which draws their attention to trends (Marks p. 22).

## Hides
A line implies a trend so strongly that it misleads on a categorical key, which belongs in a bar chart (Layout p. 23). The vertical positions of single points can still be read, but their horizontal positions are much harder to read (Marks p. 22). Our reading: a line also implies values between the measured points, which misleads when the key levels are few or unevenly spaced.

## Arrange
The key runs along the horizontal axis and the value along the vertical axis; several lines may share the axes and overlap (Layout p. 22). Munzner's own data line for this idiom names a quantitative key; any ordered key fits, since lines are for ordered keys and bars for categorical ones (Layout pp. 22, 23). The value axis includes zero unless zero is arbitrary or a small change matters (Layout pp. 25, 26). Our reading: a step line, as in a Kaplan–Meier survival curve, is a variant for values that change only at events.
