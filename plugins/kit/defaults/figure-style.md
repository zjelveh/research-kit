# Figure style

The kit's default conventions for figures. To change them, run `kit customize figure-style` and edit your copy; your copy then replaces this file. The kit's fixed figure rules (the title names what is plotted, numbers come from code, the output is a vector PDF) live in the figures skill, not here.

- **Colour for categories:** the Okabe–Ito palette, which stays distinguishable for the common kinds of colour blindness. Use hue only for categorical attributes, and no more than about six hues in one figure.
- **Colour for quantities:** a sequential scale (one hue, light to dark) for a quantity with one meaningful end; a diverging scale (two hues around a neutral midpoint) only when the midpoint means something, such as zero or a threshold.
- **Redundant encoding:** when series are told apart by hue, also tell them apart by shape or line type, so the figure survives greyscale printing.
- **Text size:** tick labels and axis titles no smaller than the paper's footnote text at the size the figure is printed.
- **Labels:** label lines and points directly where they fit, instead of with a legend. Axis titles name the quantity and its unit.
- **Reference marks:** a reference line or band is thin and grey, drawn beneath the data, and its meaning is labelled.
- **Size:** design at the printed width (one column or the full page width), not at screen size.
- **Never:** 3D effects, dual value axes, background shading, or gridlines heavier than the data.
