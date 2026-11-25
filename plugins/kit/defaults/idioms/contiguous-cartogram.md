---
id: contiguous-cartogram
name: Contiguous cartogram
origin: munzner
group: spatial
order: 230
kind: idiom
form: encoding
medium: [static, interactive]
shape: geographic
data:
  keys: [{type: categorical}]
  values: [{type: quantitative}]
  optional: [{type: [categorical, quantitative], channel: colour}]
  spatial: regions
tasks: [spatial-pattern]
marks: [{level: 1, mark: area}]
channels:
  encoded:
    - {channel: area, carries: value, where: region}
    - {channel: shape, carries: original boundary combined with the value, where: region outline}
  uniform: []
  varying: [{channel: position-common, where: set by the algorithm}]
  inherited: []
scale: {note: null}
see_also:
  - id: dorling-cartogram
    when: Readers need marks they can understand easily; stylized circles usually beat distorted regions (Spatial p. 26).
  - id: proportional-symbol-map
    when: Region shapes must stay undistorted, with one symbol per region over the base map.
  - id: choropleth-map
    when: Region shapes and areas must stay geographic, with colour carrying the value.
sources: [Spatial p. 20, Spatial p. 21, Spatial p. 25, Spatial p. 26, Spatial p. 30]
---

## Helps
Resizes every region by a value, such as greenhouse emissions or child mortality by country, while neighbouring regions keep their shared borders (Spatial p. 21). It can catch readers' interest, and works best when sizes differ in striking, unexpected ways (Spatial p. 25). Our reading: regions that are large or small on the new value stand out, while each stays next to its neighbours.

## Hides
Readers must know the original map well, since they compare the distorted regions with their memory of the real ones; transitions or side-by-side views help (Spatial p. 25). Strong distortion can be unattractive and can leave regions unrecognizable, and exact quantities are hard to read (Spatial p. 25). Our reading: areas are read less accurately than lengths, and the shapes compared are irregular, so only large differences are reliable.

## Arrange
A cartogram replaces all the map's regions at once with a new set of interlocking regions, since regions that share borders cannot change one at a time, and it keeps their relative positions as far as possible (Spatial p. 20). Taking the value as each region's target size, the algorithm keeps shapes as close to the original as it can, while keeping the shared borders with neighbours and the east–west and north–south order; the regions touch and do not overlap (Spatial p. 21). Colour can be added as in a choropleth (Spatial p. 30); Munzner's US example colours each state red or blue (Spatial p. 21). Our reading: regions move as their areas change, so a region's final position is set by the algorithm and carries no value; by the logic Munzner applies to the Dorling cartogram, position varies rather than encodes.
