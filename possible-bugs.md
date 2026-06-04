# Possible Bugs

These are behaviors found while documenting and testing the project that look unlikely to be intentional. Production code was not changed while adding tests.

## Sample TOML config does not match loader expectations

`input/brussels.toml` has top-level `location` and `layers`, but `dict_to_config` requires a `config` object. `load_toml_config` also directly reads `toml_data["config"]`, so this sample file cannot load as-is.

## Empty config objects are treated as missing

`dict_to_config` uses `if config_data := data.get("config")`, so `config: {}` raises `Exception("config not defined")` even though the section exists. A non-empty config object, such as one containing `name`, is required.

## Sample YAML fields are ignored

Several input configs use datasource fields such as `type`, `post_processors`, and style keys. The current config loader ignores these. The datasource key becomes the generated `type`, and only `processors` are loaded.

## `Config.location` is never loaded

`Config` has a `location` attribute, but `dict_to_config` only reads `config.name` and `config.exporters`.

## `HidingZones` configured EPSG path appears broken

`HidingZones.__init__` accepts `epsg`, but `process` only creates an `epsg` column when no EPSG is configured. If `epsg` is configured, `process` later reads `new_df["epsg"]`, which should raise `KeyError` unless the input frame already has that column.

## `RemoveOverlappingZones` configured EPSG path appears broken

`RemoveOverlappingZones` has the same pattern as `HidingZones`: it accepts `epsg`, but only creates an `epsg` column when no EPSG is configured, then reads `new_df["epsg"]` unconditionally.

## `RemoveOverlappingZones` reprojects all rows to the first EPSG

The processor calculates an EPSG per row but then calls `new_df.to_crs(new_df["epsg"].unique()[0])` on the entire frame. Data spanning multiple UTM zones may be processed in the wrong projection.

## `RemoveByNames` fails when `name_list` is omitted

`RemoveByNames` defaults `name_list` to `None`, but `process` uses `x[1]["name"] in self.names_removed`, which raises `TypeError` when `name_list` is absent.

## `HidingZoneExporter` fails when no rows have hiding sizes

`HidingZoneExporter.export` accumulates partial frames and then calls `concat(partials)`. If all dataframes lack `hiding_size`, or all hiding sizes are falsy, `partials` is empty and Pandas raises `ValueError`.

## `HidingZoneExporter.remove_without_size` assumes `hiding_size` is truth-testable

Rows with missing `hiding_size` values such as `NaN` may not be removed because `bool(float("nan"))` is true.

## Exporters keep mutable KML state across exports

Each exporter creates one `simplekml.Kml` instance in `__init__` and reuses it. Calling `export` twice on the same exporter object may duplicate folders or placemarks in the second output.

## `overpass_query` requires a timeout clause

`overpass_query` calls `re.search("timeout:[0-9]+", query).group()`. Queries without that exact timeout syntax raise `AttributeError` before making a request.

## `overpass_query` can retry forever

The query loop has no maximum retry count. If all mirrors keep returning non-200 responses or non-timeout exceptions occur, it may not terminate as expected.

## `order_lines` fails for a single line

`order_lines` reads `lines[index + 1]` when starting a shape. A one-line polygon ring raises `IndexError`.

## `order_lines` can index an empty points list

After initial line checks, `order_lines` unconditionally reads `points[0]` and `points[-1]`. If no branch initialized `points`, it raises `IndexError`.

## `create_hiding_zones` has an invalid dataframe filter

`generator_utils.create_hiding_zones` uses `df["epsg" == epsg]`, comparing the string `"epsg"` to the EPSG value instead of filtering the `epsg` column.

## `output_kml` appears incomplete

`generator_utils.output_kml` ends after reading `geom = row["geometry"]` and never writes or saves the KML.

## `output_csv` mutates its `columns` argument

`output_csv` calls `columns.insert(0, "WKT")`, modifying the caller's list in place.

## `map_generator.py` calculates but does not use `ext`

The command-line script assigns `ext = path.split(".")[-1]` but never uses it.
