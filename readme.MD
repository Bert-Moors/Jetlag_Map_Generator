# Jetlag Map Generator
This is a tool for generating maps for playing Hide and Seek. It uses a singular config file to load data, process this data and export the data to a format that can be used for playing the game.

## Data Loading
Can load either by overpass query or using geojson/kml/csv files.
...

## Processors
### Averaging Stations With The Same Name
In a lot of cases there may exist multiple stops (eg. bus stops) with exactly the same name. These often need to be merged together.
The `name_based_deduplicate` processor does exactly that.

### Hiding Zones
The `hiding_zones` turns points into circles around these points.

### Remove Items By Names
The `remove_by_names` processor removes all items with their name in the `name_list` that is provided to the processor.

### Column Rename

### Remove Overlapping Zones
For smaller games, an issue that often occurs is that a lot of hiding zones overlap, especially in city centres.
The `remove_overlapping_zones` offers an automated way out of this.

This processor can be used both on layers, and on individual datasources. 
If you use it on a layer, you can configure the parameters for this processor both globally, as well as per type.

There processor has a couple of parameters:
- size: how large is the circle around a specific stop? Default: 250m
- allowed_intrusion: percentage: how much is another stop's circle allowed to intrude into this stop's circle before it is a problem. Default: 80%
- importance: higher = more important: lower importance stops will be removed before higher importance stops. This means if both a tram-stop and a metro-stop are listed for removal, the tram-stop will be removed first.

Example config:
```yaml
processors: [
  {
    name: "remove_overlapping_zones",
    size: 300,
    allowed_intrusion: 0,
    config: {
      "metro": {
        importance: 2
      }
    }
  },
]
```
In this example, the size of the zones is set to be 300, and no intrusion is allowed. 
Metro stations are seen as more important than other stations.

Note that you may want to use a `name_based_deduplicate` on the data-layers. This (among other situations) merges north- and southbound bus stops together into one point (at the center). The `remove_overlapping_zones` processor will work without doing that, but may then pick either of the two bus stops, based on which one is more overlapping.

On a technical level, the processor eagerly deletes the points with the highest amount of overlap. This algorithm is not guaranteed to result in the best possible maps in all cases, but it was relatively straightforward to implement. In most cases it should not matter a lot.

## Exporters
...