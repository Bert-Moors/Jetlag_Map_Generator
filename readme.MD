


## Processors

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
In this example, hiding zones of size 300 are created, and no intrusion is allowed. 
Metro stations are seen as more important than other stations.