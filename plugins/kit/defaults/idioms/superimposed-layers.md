---
id: superimposed-layers
name: Superimposed layers
origin: munzner
group: facet
order: 170
kind: design-choice
form: view
medium: [static, interactive]
shape: any-data
data: {keys: [], values: []}
tasks: [compare-values, trend]
marks: null
channels: null
changes: >-
  Our reading: static layers do not change; the design fixes them. Dynamic visual layering is
  interactive and based on selection, as in one-hop neighbour highlighting by click or hover
  (Interact p. 58).
fixed: >-
  Each layer extends over the whole view, so the layers share one frame (Interact p. 54). Layers are
  told apart by encoding them with different, nonoverlapping channels (Interact p. 54). In Munzner's road
  map, the roads use hue and size to distinguish main from minor roads and high luminance contrast from
  the background, while the regions use desaturated colours (Interact p. 55).
scale:
  note: >-
    At most two layers, or three if carefully designed (Interact p. 54). With few layers a view can
    hold more lines, up to a few dozen but not hundreds (Interact p. 57).
see_also:
  - id: small-multiples
    when: Many series need global comparison; juxtaposed views suit global tasks, especially for many charts (Interact p. 57).
  - id: partition-views
    when: The data should also be split into views by an attribute, as trellis plots split by site (Interact p. 56).
  - id: highlight
    when: The layering should follow the reader's selection, as in one-hop neighbour highlighting (Interact p. 58).
  - id: line-chart
    when: There is one series, or only a few lines on shared axes.
sources: [Interact p. 54, Interact p. 55, Interact p. 56, Interact p. 57, Interact p. 58]
---

## Helps
With roads as a foreground layer and regions as a background layer, the reader can selectively focus attention (Interact p. 55). In Munzner's trellis plot, two years of barley yields are superimposed in the same frame and coloured by year (Interact p. 56). Our reading: in that figure, Morris stands out as the one site where most varieties yielded more in 1932 than in 1931. In an empirical study she cites, comparing one superimposed view with small multiples of the same size, the superimposed view suited local tasks (Interact p. 57).

## Hides
Few layers fit: two are achievable and three need careful design (Interact p. 54). For global tasks, especially with many charts, juxtaposed views do better (Interact p. 57). Our reading: marks in one layer can cover marks in another, and if two layers share a channel, readers may not tell which layer a mark belongs to.

## Views
One view that holds every layer (Interact p. 54). The layers can be a small static set, or chosen dynamically from many possible ones (Interact p. 54). Trellis plots superimpose the years within each view and partition the views by site, ordering the rows and the views by their medians (Interact p. 56).
