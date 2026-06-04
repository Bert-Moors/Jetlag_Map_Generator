# Functionality Inventory

This project generates Hide and Seek map outputs from a single configuration file. The pipeline is:

1. Load a config file.
2. Build loader, processor, layer, and exporter objects from that config.
3. Import geospatial data into per-layer, per-datasource GeoDataFrames.
4. Run datasource processors and then layer processors.
5. Export the gathered data to KML files.

## Command-Line Entry Point

`map_generator.py` is the executable script.

- With no arguments, it uses `input/arnhem.yaml`.
- With one argument, it treats the argument as a file name under `input/`.
- It writes output under `output/<input file name without extension>`.
- It instantiates `src.generator.Generator` and calls `generate()`.
- The local `ext` variable is calculated but not used.

Example:

```sh
python map_generator.py rotterdam.yaml
```

This reads `input/rotterdam.yaml` and writes into `output/rotterdam`.

## Configuration Loading

Config loading is implemented in `src/generator/config/config_loaders.py`.

Supported file types:

- `.json`, loaded with `json.load`.
- `.toml`, loaded with `tomllib.load`.
- `.yml` and `.yaml`, loaded with `yaml.load(..., Loader=yaml.FullLoader)`.

Unsupported extensions raise `Exception("Wrong config loading format")`.

Passing `None` as the file name raises `Exception("file_name cannot be None")`.

### Expected Config Shape

The normalized config dictionary must contain:

- `config`: project-level config.
- `layers`: map layers.

The `config` object supports:

- `name`: output name prefix. Defaults to an empty string.
- `exporters`: list of exporter names. If omitted or empty, the default exporter is `googleMMaps`.

The `layers` object maps layer names to layer definitions.

Each layer supports:

- `processors`: optional list of layer-level processors.
- Any other key is treated as a datasource name.

Each datasource supports:

- `processors`: optional list of datasource-level processors.
- `query`: creates an `OverpassLoader`.
- `geom_type`: passed to the `OverpassLoader`.
- `file`: creates a `GeoJsonLoader`.

The datasource key itself becomes the generated frame's `type` value. The `type` config field used in some sample input files is not read by the current loader.

### TOML Normalization

For TOML files, `load_toml_config` expects a `[config]` table and optionally a `[layers]` table. Any top-level table other than `config` and `layers` is merged into `config_dict["layers"]`.

## Config Data Classes

Defined in `src/generator/config/config.py`:

- `Config` contains `name`, `location`, `exporters`, and `layers`.
- `Layer` contains `name`, `processors`, and `datasources`.
- `Datasource` contains `loader`, `processors`, and `name_type`.

`Config.location` is initialized to an empty string and is not filled by the config loader.

## Loaders

Loaders are implemented in `src/loaders/loaders.py`.

### OverpassLoader

`OverpassLoader(query, geo_type)` calls `overpass_query_with_cache(query)` and parses the returned Overpass JSON according to `geo_type`.

Supported `geo_type` values:

- `border`
- `points`
- `routes`
- `polygons`

`lines` is present in the match statement but has no implementation. Unsupported or empty parsed frames raise `Exception("geom type not supported")`.

#### Border Parsing

For each Overpass element:

- It reads relation members with `type == "way"`.
- Each way member's `geometry` points are converted to `[lon, lat]` coordinates.
- The result is a `shapely.MultiLineString`.
- The row name is always `border`.

If `elements` is empty, it raises `Exception("Response is empty")`.

#### Point Parsing

For each Overpass element:

- `node` elements become `Point(lon, lat)`.
- `way` and `relation` elements use `center` when present.
- `way` and `relation` elements use the center of `bounds` when `center` is absent.
- If neither `center` nor `bounds` is present for a `way` or `relation`, it raises `Exception("Point has no valid data")`.
- The row name is `element["tags"]["name"]`.

If `elements` is empty, it raises `Exception("Response is empty")`.

#### Polygon Parsing

For each Overpass element:

- It reads way members.
- Member geometries are passed to `loaders.util.order_lines`.
- Each ordered closed shape becomes a `shapely.Polygon`.
- The row geometry is a `shapely.MultiPolygon`.
- The row name is `element["tags"]["name"]`.

If `elements` is empty, it raises `Exception("Response is empty")`.

#### Route Parsing

For each Overpass element:

- It reads way members except members whose `role` is `platform`.
- Each retained way member becomes one line in a `shapely.MultiLineString`.
- The row name is `element["tags"]["name"]`.

If `elements` is empty, it raises `Exception("Response is empty")`.

### GeoJsonLoader

`GeoJsonLoader(file_name)` reads a file immediately with `geopandas.read_file(file_name)`.

- Passing `None` raises `Exception("file_name cannot be None")`.
- Calling `load()` returns the GeoDataFrame read during construction.
- The class name mentions GeoJSON, but any format supported by GeoPandas can be read.

## Overpass Querying And Cache

Implemented in `src/loaders/overpass.py`.

### overpass_query

`overpass_query(query)`:

- Extracts timeout from the query with the regex `timeout:[0-9]+`.
- Cycles through three Overpass mirrors.
- Sends `requests.get(..., data=query, timeout=timeout, headers={"User-Agent": "mapgenerator/1.0"})`.
- Retries forever until it receives HTTP 200.
- Retries on request timeouts.
- Prints response status codes and retry information.
- Returns `json.loads(response.text)`.

### overpass_query_with_cache

`overpass_query_with_cache(query)`:

- Computes a SHA-256 digest of the query.
- Creates `_cache` if it does not exist.
- Looks for `_cache/<sha256>.json`.
- If present, loads and returns the JSON.
- If absent, calls `overpass_query(query)`, writes the JSON to the cache file, and returns it.

## Utility: order_lines

`src/loaders/util.py` contains `order_lines(lines)`.

- It attempts to join a list of line coordinate lists into closed shapes.
- It starts with an empty `points` list.
- It chooses the direction of the first line by comparing it to the next line.
- It appends later lines forward or reversed when they connect to the current end point.
- When the first and last points match, it stores the closed coordinate list in `shapes` and resets `points`.
- It returns the list of closed shapes.

## Processors

Processors are resolved by `src/processors/processor_index.py` using the processor config's `name` field.

Supported processor names:

- `name_based_deduplicate`
- `hiding_zones`
- `rename_column`
- `remove_by_names`
- `remove_overlapping_zones`
- `add_column`

Unknown processor names raise `KeyError`.

### add_column

Implemented by `AddColumn`.

- Reads `columns` from config, defaulting to `{}`.
- For each configured column, sets `frame[column] = value`.
- Returns the same mutated frame object.

### rename_column

Implemented by `Rename`.

- Reads `columns` from config, defaulting to `{}`.
- Calls `frame.rename(columns=self.columns)`.
- Returns the renamed frame.

### remove_by_names

Implemented by `RemoveByNames`.

- Reads `name_list` from config.
- Copies the frame and resets its index.
- Drops every row whose `name` is exactly present in `name_list`.
- Returns the filtered copy.

### name_based_deduplicate

Implemented by `AverageStationsSameName`.

- Reads `prefix_ignores` from config, defaulting to `[]`.
- Creates a `fixed_name` for each row by uppercasing `name` and removing every configured prefix from the start.
- Dissolves rows by `fixed_name`.
- Returns a new GeoDataFrame with columns `name`, `geometry`, and `type`.
- Each output geometry is the centroid of the dissolved geometry.
- The output `name` and `type` come from the dissolved row.

### hiding_zones

Implemented by `HidingZones`.

- Reads `size`, defaulting to `250` meters.
- Reads `epsg`, defaulting to `None`.
- Reads `draw_polygons`, defaulting to `False`.
- Copies the frame and sets CRS to EPSG:4326.
- When no EPSG is configured, calculates a UTM EPSG code per row from the point coordinates.
- For each EPSG group:
- Reprojects to that EPSG.
- If `draw_polygons` is true, replaces each geometry with a buffer polygon.
- Otherwise, replaces each geometry with a `MultiLineString` boundary of a buffer circle.
- Reprojects each group back to EPSG:4326.
- Concatenates all groups into a new GeoDataFrame with CRS EPSG:4326.

### remove_overlapping_zones

Implemented by `RemoveOverlappingZones`.

Configuration:

- `epsg`, default `None`.
- `config`, per-type overrides, default `{}`.
- `allowed_intrusion`, default `80`.
- `importance`, default `1`.
- `size`, default `500`.

Per-type overrides can set:

- `allowed_intrusion`
- `importance`
- `size`

Processing behavior:

- Copies the frame, sets CRS to EPSG:4326, and resets the index.
- When no EPSG is configured, calculates a UTM EPSG code per row.
- Reprojects the entire frame to the first EPSG in the `epsg` column.
- Uses the spatial index to find nearby geometry pairs within `get_max_size() * 2.1`.
- Ignores self-pairs.
- Ignores pairs where the candidate row is more important than the neighbor.
- Allows row-specific `hiding_size` values to override configured sizes.
- Computes an overlap score for rows whose hiding zone overlap exceeds the allowed intrusion.
- Repeatedly drops the row with the highest score among the lowest importance rows until no row is selected.
- Reprojects the result back to EPSG:4326.

## Generator Pipeline

Implemented in `src/generator/generator.py`.

`Generator(config_file, output_path)`:

- Loads the config file immediately.
- Stores the output path.
- Initializes `_gathered_data` as an empty dictionary.

`generate()` runs three private phases in order:

1. Import data.
2. Process data.
3. Export data.

### Import Phase

For each layer and datasource:

- Calls `data.loader.load()`.
- Sets `frame["type"] = data.name_type`.
- Stores it as `_gathered_data[layer.name][data.name_type]`.

### Processing Phase

For each layer:

- Runs every datasource processor on that datasource's frame.
- If the layer has processors, concatenates all datasource frames in the layer.
- Runs each layer processor on the concatenated frame.
- Splits the resulting frame by unique `type` values.
- Replaces the layer's stored data with that split dictionary.

### Export Phase

- Creates the output directory if it does not already exist.
- Calls every configured exporter's `export(data, output_path_with_config_name)`.
- The data argument is a shallow copy of `_gathered_data`.

## Exporters

Exporters are resolved by `src/generator/exporters/exporter_index.py`.

Supported exporter names:

- `googleMMaps`
- `fullkml`
- `kmlHidingZones`

Unknown exporter names raise `KeyError`.

### KML Serialization Utility

`add_to_kml(frames, folder)` serializes a mapping of layer names to GeoDataFrames.

For each layer:

- Creates a new KML folder named after the layer.
- Serializes every row based on `row["geometry"].geom_type`.

Supported geometry types:

- `Point`: creates a point with row name and extended data `type`.
- `Polygon`: creates a multigeometry containing one polygon and extended data `type`.
- `MultiLineString`: creates a multigeometry containing one linestring per member and extended data `type`.
- `LineString`: skips rows without a name; otherwise creates a linestring, applies width `3`, and uses row `color` as line color.
- `MultiPolygon`: creates a multigeometry containing one polygon per member and extended data `type`.

Unsupported geometry types are silently ignored by the match statement.

### googleMMaps Exporter

Implemented by `GoogleMyMapsKmlExporter`.

- Owns a `simplekml.Kml` instance.
- For each layer, concatenates all datasource frames into one GeoDataFrame.
- Writes the combined layers with `add_to_kml`.
- Saves to `<output_path> GMM.kml`.

### fullkml Exporter

Implemented by `FullKmlExporter`.

- Owns a `simplekml.Kml` instance.
- Creates a top-level KML folder per layer.
- Writes each datasource under that layer folder with `add_to_kml`.
- Saves to `<output_path> FULL.kml`.

### kmlHidingZones Exporter

Implemented by `HidingZoneExporter`.

- Owns a `simplekml.Kml` instance.
- Creates a top-level `Hiding Zones` KML folder.
- Iterates all layer datasource frames.
- Skips frames without a `hiding_size` column.
- Drops rows whose `hiding_size` value is falsy.
- Sets CRS to EPSG:4326.
- Calculates a UTM EPSG per row.
- Reprojects rows per EPSG.
- Replaces geometry with a `MultiLineString` boundary of a buffer circle using each row's `hiding_size`.
- Reprojects back to EPSG:4326.
- Concatenates all hiding-zone frames.
- Writes the result to KML.
- Saves to `<output_path> HZ.kml`.

## Legacy Utility Functions

`src/generator/generator_utils.py` contains functions that are not used by the current `Generator` pipeline.

- `read_station_frame(file_path, station_type)`: reads a file, sets CRS EPSG:4326, adds `type`, `latitude`, and `longitude` columns.
- `dedup_frame(df, distance)`: removes nearby points using a priority order of train, subway, tram, bus.
- `create_hiding_zones(df, distance)`: intended to generate hiding-zone boundaries per EPSG.
- `output_csv(frame, filepath, columns)`: adds a WKT column and writes selected columns to CSV.
- `output_kml(frame, filepath, columns)`: starts a KML export but is incomplete in the current file.

`src/generator/station_types.py` defines a `StationType` enum with `BUS`, `TRAM`, `METRO`, and `TRAIN`.
