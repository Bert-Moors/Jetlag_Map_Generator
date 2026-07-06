import io
import math
import os
import re
import xml.etree.ElementTree as ElementTree
import zlib
from pathlib import Path

import geopandas as gpd
import pandas as pd
from geopandas.geodataframe import GeoDataFrame
from numpy import copysign, floor
from pandas import concat

from shapely import MultiLineString
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString as ShapelyMultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

from .exporter_util import add_to_kml
import simplekml
from typing import Protocol
import requests
from pyproj import Geod


class Exporter(Protocol):
    def export(self):
        pass

class GoogleMyMapsKmlExporter:
    def __init__(self):
        self._kml = simplekml.Kml()

    def export(self, data: dict, output_path):
        for layer_name in data.keys():
            data[layer_name] = gpd.GeoDataFrame(pd.concat(data[layer_name].values()))

        add_to_kml(data, self._kml)

        self._kml.save(f"{output_path} GMM.kml")

class OpenStreetMapA3PdfExporter:
    TILE_SERVERS = {
        "osm": {
            "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            "attribution": "(c) OpenStreetMap contributors",
            "subdomains": [""],
        },
        "carto_light": {
            "url": "https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png",
            "attribution": "Map tiles by CARTO, data (c) OpenStreetMap contributors",
            "subdomains": ["a", "b", "c", "d"],
        },
        "carto_voyager": {
            "url": "https://cartodb-basemaps-{s}.global.ssl.fastly.net/rastertiles/voyager/{z}/{x}/{y}.png",
            "attribution": "Map tiles by CARTO, data (c) OpenStreetMap contributors",
            "subdomains": ["a", "b", "c", "d"],
        },
        "carto_voyager_retina": {
            "url": "https://cartodb-basemaps-{s}.global.ssl.fastly.net/rastertiles/voyager/{z}/{x}/{y}@2x.png",
            "attribution": "Map tiles by CARTO, data (c) OpenStreetMap contributors",
            "subdomains": ["a", "b", "c", "d"],
            "tile_scale": 2,
        },
        "stadia_osm_bright": {
            "url": "https://tiles.stadiamaps.com/tiles/osm_bright/{z}/{x}/{y}.png",
            "attribution": "Map tiles by Stadia Maps, data (c) OpenStreetMap contributors",
            "subdomains": [""],
        },
        "opentopomap": {
            "url": "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
            "attribution": "Map tiles by OpenTopoMap, data (c) OpenStreetMap contributors",
            "subdomains": ["a", "b", "c"],
        },
        "osm_de": {
            "url": "https://tile.openstreetmap.de/{z}/{x}/{y}.png",
            "attribution": "Map tiles by openstreetmap.de, data (c) OpenStreetMap contributors",
            "subdomains": [""],
        },
    }
    DEFAULT_TILE_SERVER = "carto_voyager"
    FALLBACK_TILE_SERVERS = ["carto_voyager_retina", "carto_voyager", "carto_light", "osm_de", "opentopomap"]
    USER_AGENT = "JetlagMapGenerator/1.0 (+https://www.openstreetmap.org/copyright)"
    TILE_SIZE = 256
    A3_LANDSCAPE_MM = (420, 297)
    DPI = 300
    MAX_TILES = 2500
    GEOD = Geod(ellps="WGS84")

    def __init__(self):
        self._round_map_zoom = True

    def configure(self, settings):
        self._round_map_zoom = self._setting_bool(settings.get("round_map_zoom"), True)

    def export(self, data: dict, output_path):
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError as exc:
            raise ImportError("The PDF exporter requires Pillow. Install it with `pip install pillow`.") from exc
        Image.MAX_IMAGE_PIXELS = None

        self._active_tile_server_name = self._tile_server_name()
        self._failed_tile_servers = set()
        self._icon_cache = {}
        self._svg_cache = {}
        frames = self._flatten_frames(data)
        if not frames:
            raise ValueError("No map data available for PDF export")

        self._debug(f"Preparing {sum(len(frame) for _, _, frame in frames)} features from {len(frames)} datatype frame(s)")
        svg_count = sum(frame["style_svg"].notna().sum() for _, _, frame in frames if "style_svg" in frame.columns)
        self._debug(f"Inline SVG markers: {svg_count}")
        bounds = self._calculate_bounds(frames)
        page_size = self._page_size_px()
        zoom = self._choose_zoom(bounds, page_size)
        world_bounds = self._world_bounds_for_page(bounds, zoom, page_size)
        if self._round_map_zoom:
            world_bounds, map_scale = self._round_world_bounds_to_scale(world_bounds, zoom)
        else:
            map_scale = self._world_bounds_scale(world_bounds, zoom)
        final_zoom = self._choose_zoom_for_world_bounds(world_bounds, zoom)
        if final_zoom != zoom:
            zoom_factor = 2 ** (final_zoom - zoom)
            world_bounds = tuple(value * zoom_factor for value in world_bounds)
            zoom = final_zoom
        tile_range = self._world_tile_range(world_bounds, zoom)
        tile_count = (tile_range[2] - tile_range[0] + 1) * (tile_range[3] - tile_range[1] + 1)
        source_size = (round(world_bounds[2] - world_bounds[0]), round(world_bounds[3] - world_bounds[1]))
        self._debug(f"Input bounds lon/lat: {bounds}")
        self._debug(f"A3 page size: {page_size[0]}x{page_size[1]} px at {self.DPI} DPI")
        scale_label = "Rounded map scale" if self._round_map_zoom else "Map scale"
        self._debug(f"{scale_label}: {map_scale:g} cm/km")
        self._debug(f"Selected zoom {zoom}; source map area {source_size[0]}x{source_size[1]} px; fetching/compositing {tile_count} tile(s)")
        image = self._render_tiles(Image, world_bounds, zoom, page_size, output_path)

        self._image = image
        self._Image = Image
        self._ImageDraw = ImageDraw
        draw = ImageDraw.Draw(image, "RGBA")
        color_map = self._datatype_colors(frames)
        legend_entries = self._legend_entries(frames, color_map)
        vector_elements = []
        label_elements = []
        for _, datatype, frame in frames:
            for _, row in frame.iterrows():
                color = self._row_color(row, color_map[datatype])
                secondary_color = self._row_secondary_color(row, (255, 255, 255, 240))
                icon_href = self._row_icon_href(row)
                svg = row.get("style_svg")
                marker_scale = self._row_scale(row)
                stroke_width = self._row_width(row)
                dotted = self._row_dotted(row)
                geometry = row["geometry"]
                vector_elements.extend(self._geometry_to_svg(geometry, color, zoom, world_bounds, page_size, stroke_width, dotted))
                self._draw_point_geometry(draw, geometry, color, secondary_color, zoom, world_bounds, page_size, icon_href, svg, marker_scale)

        font = ImageFont.load_default()
        self._draw_scale_ruler(draw, font, map_scale, page_size)
        attribution = self.TILE_SERVERS[self._active_tile_server_name]["attribution"]
        draw.text((page_size[0] - max(205, len(attribution) * 6), page_size[1] - 18), attribution, fill=(30, 30, 30, 220), font=font)
        self._save_pdf(image, vector_elements, label_elements, legend_entries, page_size, output_path)
        self._debug(f"Saved PDF: {output_path} OSM A3.pdf")

    def _flatten_frames(self, data):
        frames = []
        for layer_name, layer in data.items():
            for datatype, frame in layer.items():
                if frame.empty:
                    continue
                prepared = frame.copy()
                if prepared.crs is None:
                    prepared.set_crs(4326, inplace=True)
                else:
                    prepared = prepared.to_crs(4326)
                frames.append((layer_name, datatype, prepared))
        return frames

    def _calculate_bounds(self, frames):
        bounds_frames = [frame for _, _, frame in frames if not self._frame_ignored_for_map_boundaries(frame)]
        if not bounds_frames:
            bounds_frames = [frame for _, _, frame in frames]
        combined = gpd.GeoDataFrame(pd.concat(bounds_frames), crs="EPSG:4326")
        min_lon, min_lat, max_lon, max_lat = combined.total_bounds
        if min_lon == max_lon:
            min_lon -= 0.01
            max_lon += 0.01
        if min_lat == max_lat:
            min_lat -= 0.01
            max_lat += 0.01
        lon_padding = (max_lon - min_lon) * 0.05
        lat_padding = (max_lat - min_lat) * 0.05
        return (min_lon - lon_padding, min_lat - lat_padding, max_lon + lon_padding, max_lat + lat_padding)

    def _frame_ignored_for_map_boundaries(self, frame):
        if "style_ignore_for_map_boundaries" not in frame.columns or frame.empty:
            return False
        value = frame["style_ignore_for_map_boundaries"].iloc[0]
        if value is None or pd.isna(value):
            return False
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    def _choose_zoom(self, bounds, page_size):
        for zoom in range(18, 0, -1):
            min_x, min_y, max_x, max_y = self._world_tile_range(self._world_bounds_for_page(bounds, zoom, page_size), zoom)
            if (max_x - min_x + 1) * (max_y - min_y + 1) <= self.MAX_TILES:
                return zoom
        return 1

    def _choose_zoom_for_world_bounds(self, world_bounds, current_zoom):
        for zoom in range(18, 0, -1):
            zoom_factor = 2 ** (zoom - current_zoom)
            scaled_bounds = tuple(value * zoom_factor for value in world_bounds)
            min_x, min_y, max_x, max_y = self._world_tile_range(scaled_bounds, zoom)
            if (max_x - min_x + 1) * (max_y - min_y + 1) <= self.MAX_TILES:
                return zoom
        return 1

    def _tile_range(self, bounds, zoom):
        min_lon, min_lat, max_lon, max_lat = bounds
        min_px, max_py = self._lon_lat_to_world_px(min_lon, min_lat, zoom)
        max_px, min_py = self._lon_lat_to_world_px(max_lon, max_lat, zoom)
        return (
            math.floor(min_px / self.TILE_SIZE),
            math.floor(min_py / self.TILE_SIZE),
            math.floor(max_px / self.TILE_SIZE),
            math.floor(max_py / self.TILE_SIZE),
        )

    def _page_size_px(self):
        width_mm, height_mm = self.A3_LANDSCAPE_MM
        return (round(width_mm / 25.4 * self.DPI), round(height_mm / 25.4 * self.DPI))

    def _world_bounds_for_page(self, bounds, zoom, page_size):
        min_lon, min_lat, max_lon, max_lat = bounds
        min_x, max_y = self._lon_lat_to_world_px(min_lon, min_lat, zoom)
        max_x, min_y = self._lon_lat_to_world_px(max_lon, max_lat, zoom)
        width = max_x - min_x
        height = max_y - min_y
        page_ratio = page_size[0] / page_size[1]
        bounds_ratio = width / height
        if bounds_ratio > page_ratio:
            new_height = width / page_ratio
            delta = (new_height - height) / 2
            min_y -= delta
            max_y += delta
        else:
            new_width = height * page_ratio
            delta = (new_width - width) / 2
            min_x -= delta
            max_x += delta
        return (min_x, min_y, max_x, max_y)

    def _round_world_bounds_to_scale(self, world_bounds, zoom):
        current_scale = self._world_bounds_scale(world_bounds, zoom)
        rounded_scale = self._nice_scale(current_scale)
        desired_width_km = self.A3_LANDSCAPE_MM[0] / 10 / rounded_scale
        width_km, _ = self._world_bounds_size_km(world_bounds, zoom)
        scale = desired_width_km / width_km

        min_x, min_y, max_x, max_y = world_bounds
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        width = (max_x - min_x) * scale
        height = (max_y - min_y) * scale
        return (
            center_x - width / 2,
            center_y - height / 2,
            center_x + width / 2,
            center_y + height / 2,
        ), rounded_scale

    def _world_bounds_scale(self, world_bounds, zoom):
        width_km, _ = self._world_bounds_size_km(world_bounds, zoom)
        return self.A3_LANDSCAPE_MM[0] / 10 / width_km

    def _setting_bool(self, value, default):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    def _nice_scale(self, scale):
        exponent = math.floor(math.log10(scale)) if scale > 0 else 0
        base = 10 ** exponent
        previous = base
        for multiplier in [1, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10]:
            nice = multiplier * base
            if nice > scale:
                return previous
            previous = nice
        return 10 * base

    def _world_bounds_size_km(self, world_bounds, zoom):
        min_x, min_y, max_x, max_y = world_bounds
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        left = self._world_px_to_lon_lat(min_x, center_y, zoom)
        right = self._world_px_to_lon_lat(max_x, center_y, zoom)
        top = self._world_px_to_lon_lat(center_x, min_y, zoom)
        bottom = self._world_px_to_lon_lat(center_x, max_y, zoom)
        _, _, width_m = self.GEOD.inv(left[0], left[1], right[0], right[1])
        _, _, height_m = self.GEOD.inv(top[0], top[1], bottom[0], bottom[1])
        return width_m / 1000, height_m / 1000

    def _world_px_to_lon_lat(self, x, y, zoom):
        scale = self.TILE_SIZE * 2 ** zoom
        lon = x / scale * 360.0 - 180.0
        n = math.pi - 2.0 * math.pi * y / scale
        lat = math.degrees(math.atan(math.sinh(n)))
        return lon, lat

    def _draw_scale_ruler(self, draw, font, scale, page_size):
        tick_km = self._scale_tick_km(scale)
        tick_cm = tick_km * scale
        cm_to_px = self.DPI / 2.54
        x0 = round(1.2 * cm_to_px)
        y0 = page_size[1] - round(1.2 * cm_to_px)
        tick_px = tick_cm * cm_to_px
        tick_count = 3
        line_width = 3
        label_color = (20, 20, 20, 230)
        background = (
            x0 - 8,
            y0 - 30,
            round(x0 + tick_px * tick_count + 10),
            y0 + 24,
        )
        draw.rectangle(background, fill=(255, 255, 255, 190))
        draw.line((x0, y0, x0 + tick_px * tick_count, y0), fill=label_color, width=line_width)
        for tick in range(tick_count + 1):
            x = round(x0 + tick_px * tick)
            draw.line((x, y0 - 8, x, y0 + 8), fill=label_color, width=line_width)
            label = self._format_km(tick * tick_km)
            if tick == tick_count:
                label = f"{label} km"
            draw.text((x, y0 + 10), label, fill=label_color, font=font, anchor="ma")
        label_km = self._scale_label_km(scale)
        label_cm = label_km * scale
        draw.text((x0, y0 - 24), f"{self._format_km(label_cm)} cm = {self._format_km(label_km)} km", fill=label_color, font=font)

    def _scale_tick_km(self, scale):
        for tick_km in [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100]:
            if tick_km * scale >= 1.25:
                return tick_km
        return 100

    def _scale_label_km(self, scale):
        for label_km in [0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200]:
            if label_km * scale >= 2.5:
                return label_km
        return 200

    def _format_km(self, value):
        return str(int(value)) if float(value).is_integer() else f"{value:g}"

    def _render_tiles(self, Image, world_bounds, zoom, page_size, output_path):
        min_x, min_y, max_x, max_y = world_bounds
        tile_min_x, tile_min_y, tile_max_x, tile_max_y = self._world_tile_range(world_bounds, zoom)
        tile_scale = self._tile_scale(self._tile_server_name())
        tile_pixel_size = self.TILE_SIZE * tile_scale
        mosaic = Image.new("RGB", ((tile_max_x - tile_min_x + 1) * tile_pixel_size, (tile_max_y - tile_min_y + 1) * tile_pixel_size), "white")
        for x in range(tile_min_x, tile_max_x + 1):
            for y in range(tile_min_y, tile_max_y + 1):
                tile = self._fetch_tile(Image, zoom, x, y, output_path, tile_pixel_size)
                mosaic.paste(tile, ((x - tile_min_x) * tile_pixel_size, (y - tile_min_y) * tile_pixel_size))
        crop = (
            round((min_x - tile_min_x * self.TILE_SIZE) * tile_scale),
            round((min_y - tile_min_y * self.TILE_SIZE) * tile_scale),
            round((max_x - tile_min_x * self.TILE_SIZE) * tile_scale),
            round((max_y - tile_min_y * self.TILE_SIZE) * tile_scale),
        )
        return mosaic.crop(crop).resize(page_size, Image.Resampling.LANCZOS).convert("RGBA")

    def _world_tile_range(self, world_bounds, zoom):
        min_x, min_y, max_x, max_y = world_bounds
        return (
            math.floor(min_x / self.TILE_SIZE),
            math.floor(min_y / self.TILE_SIZE),
            math.floor(max_x / self.TILE_SIZE),
            math.floor(max_y / self.TILE_SIZE),
        )

    def _fetch_tile(self, Image, zoom, x, y, output_path, tile_pixel_size):
        max_tile = 2 ** zoom
        x %= max_tile
        y = min(max(y, 0), max_tile - 1)
        errors = []
        for server_name in self._tile_server_order():
            if server_name in self._failed_tile_servers:
                continue
            cache_path = self._tile_cache_path(output_path, server_name, zoom, x, y)
            if cache_path.exists():
                self._active_tile_server_name = server_name
                self._debug(f"Tile cache hit: {server_name} z={zoom} x={x} y={y}")
                return self._prepare_tile_image(Image, Image.open(cache_path).convert("RGB"), tile_pixel_size)

            server = self.TILE_SERVERS[server_name]
            subdomain = server["subdomains"][(x + y) % len(server["subdomains"])]
            url = server["url"].format(z=zoom, x=x, y=y, s=subdomain)
            self._debug(f"Downloading tile from {server_name}: z={zoom} x={x} y={y}")
            try:
                response = requests.get(url, headers={"User-Agent": self.USER_AGENT}, timeout=20)
                response.raise_for_status()
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(response.content)
                self._active_tile_server_name = server_name
                return self._prepare_tile_image(Image, Image.open(io.BytesIO(response.content)).convert("RGB"), tile_pixel_size)
            except Exception as exc:
                errors.append(f"{server_name}: {exc}")
                self._debug(f"Tile server failed ({server_name}): {exc}")
                self._failed_tile_servers.add(server_name)
        raise RuntimeError(f"Could not fetch tile z={zoom} x={x} y={y}. Tried: {'; '.join(errors)}")

    def _tile_server_name(self):
        name = os.environ.get("JETLAG_TILE_SERVER", self.DEFAULT_TILE_SERVER)
        if name not in self.TILE_SERVERS:
            options = ", ".join(self.TILE_SERVERS.keys())
            raise ValueError(f"Unknown JETLAG_TILE_SERVER '{name}'. Options: {options}")
        return name

    def _tile_server(self):
        return self.TILE_SERVERS[self._tile_server_name()]

    def _tile_scale(self, server_name):
        return self.TILE_SERVERS[server_name].get("tile_scale", 1)

    def _prepare_tile_image(self, Image, tile, tile_pixel_size):
        if tile.size == (tile_pixel_size, tile_pixel_size):
            return tile
        return tile.resize((tile_pixel_size, tile_pixel_size), Image.Resampling.LANCZOS)

    def _tile_cache_path(self, output_path, server_name, zoom, x, y):
        return Path(f"{output_path} OSM tile-cache") / server_name / str(zoom) / str(x) / f"{y}.png"

    def _tile_server_order(self):
        first = self._tile_server_name()
        return [first] + [name for name in self.FALLBACK_TILE_SERVERS if name != first]

    def _debug(self, message):
        print(f"[osmA3Pdf] {message}", flush=True)

    def _datatype_colors(self, frames):
        datatypes = []
        for _, datatype, _ in frames:
            if datatype not in datatypes:
                datatypes.append(datatype)
        return {datatype: self._pseudo_random_color(index) for index, datatype in enumerate(datatypes)}

    def _pseudo_random_color(self, index):
        hue = (index * 137.508) % 360
        c = 0.82
        x = c * (1 - abs((hue / 60) % 2 - 1))
        m = 0.10
        if hue < 60:
            r, g, b = c, x, 0
        elif hue < 120:
            r, g, b = x, c, 0
        elif hue < 180:
            r, g, b = 0, c, x
        elif hue < 240:
            r, g, b = 0, x, c
        elif hue < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
        return (round((r + m) * 255), round((g + m) * 255), round((b + m) * 255), 235)

    def _row_color(self, row, fallback):
        type_to_color = row.get("style_type_to_color")
        row_type = row.get("type")
        if isinstance(type_to_color, dict) and row_type in type_to_color:
            return self._kml_color_to_rgba(str(type_to_color[row_type]), fallback)
        color = row.get("style_color")
        if not color or pd.isna(color):
            return fallback
        return self._kml_color_to_rgba(str(color), fallback)

    def _row_secondary_color(self, row, fallback):
        color = row.get("style_secondary_color")
        if not color or pd.isna(color):
            return fallback
        return self._kml_color_to_rgba(str(color), fallback)

    def _kml_color_to_rgba(self, color, fallback):
        color = color.strip().lstrip("#")
        if len(color) == 6:
            color = "ff" + color
        if len(color) != 8:
            return fallback
        try:
            alpha = int(color[0:2], 16)
            blue = int(color[2:4], 16)
            green = int(color[4:6], 16)
            red = int(color[6:8], 16)
        except ValueError:
            return fallback
        return red, green, blue, alpha

    def _rgba_to_hex(self, color):
        return f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"

    def _row_scale(self, row):
        scale = row.get("style_scale")
        if not scale or pd.isna(scale):
            return 1.0
        return float(scale)

    def _row_width(self, row):
        width = row.get("style_width")
        if not width or pd.isna(width):
            return None
        return max(round(float(width)), 1)

    def _row_icon_href(self, row):
        href = row.get("style_href")
        if not href or pd.isna(href):
            return None
        if str(href).endswith("/bus.png"):
            return None
        return href

    def _row_with_label(self, row):
        value = row.get("style_with_label")
        if value is None or pd.isna(value):
            return False
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    def _row_dotted(self, row):
        value = row.get("style_dotted")
        if value is None or pd.isna(value):
            return False
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    def _row_label_size(self, row):
        size = row.get("style_label_size")
        if not size or pd.isna(size):
            size = 12
        return max(float(size) * 0.7, 1)

    def _row_label_direction(self, row):
        direction = row.get("style_label_direction")
        if not direction or pd.isna(direction):
            return 0.0
        return float(direction)

    def _row_fixed_label(self, row):
        label = row.get("style_fixed_label")
        if not label or pd.isna(label):
            return None
        return str(label).strip()[:1]

    def _legend_entries(self, frames, color_map):
        entries = []
        for layer_name, datatype, frame in frames:
            row = frame.iloc[0]
            entries.append({
                "layer": layer_name,
                "name": str(datatype),
                "shape": self._legend_shape(frame),
                "color": self._row_color(row, color_map[datatype]),
                "stroke_width": self._row_width(row) or 2,
                "dotted": self._row_dotted(row),
                "fixed_label": self._row_fixed_label(row),
            })
        return entries

    def _legend_shape(self, frame):
        geometry_types = set(frame.geometry.geom_type.dropna())
        if geometry_types & {"LineString", "MultiLineString"}:
            return "line"
        if geometry_types & {"Polygon", "MultiPolygon"}:
            return "polygon"
        return "point"

    def _draw_geometry(self, draw, geometry, color, secondary_color, zoom, world_bounds, page_size, icon_href=None, svg=None, scale=1.0, stroke_width=None):
        if geometry is None or geometry.is_empty:
            return
        match geometry:
            case Point():
                self._draw_point(draw, geometry, color, secondary_color, zoom, world_bounds, page_size, icon_href, svg, scale)
            case MultiPoint():
                for point in geometry.geoms:
                    self._draw_point(draw, point, color, secondary_color, zoom, world_bounds, page_size, icon_href, svg, scale)
            case LineString():
                self._draw_line(draw, geometry, color, zoom, world_bounds, page_size, stroke_width)
            case ShapelyMultiLineString():
                for line in geometry.geoms:
                    self._draw_line(draw, line, color, zoom, world_bounds, page_size, stroke_width)
            case Polygon():
                self._draw_polygon(draw, geometry, color, zoom, world_bounds, page_size, stroke_width)
            case MultiPolygon():
                for polygon in geometry.geoms:
                    self._draw_polygon(draw, polygon, color, zoom, world_bounds, page_size, stroke_width)
            case GeometryCollection():
                for child in geometry.geoms:
                    self._draw_geometry(draw, child, color, secondary_color, zoom, world_bounds, page_size, icon_href, svg, scale, stroke_width)

    def _draw_point(self, draw, point, color, secondary_color, zoom, world_bounds, page_size, icon_href=None, svg=None, scale=1.0):
        x, y = self._lon_lat_to_page(point.x, point.y, zoom, world_bounds, page_size)
        svg_icon = self._load_svg(svg, color, secondary_color, scale)
        if svg_icon:
            self._paste_centered(svg_icon, x, y)
            return
        icon = self._load_icon(icon_href)
        if icon:
            self._paste_centered(icon.resize((24, 24), self._Image.Resampling.LANCZOS), x, y)
            return
        radius = 8
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color, outline=secondary_color, width=3)

    def _paste_centered(self, icon, x, y):
        self._image.alpha_composite(icon, (round(x - icon.width / 2), round(y - icon.height / 2)))

    def _load_svg(self, svg, color, secondary_color, scale):
        if not svg or pd.isna(svg):
            return None
        rendered_svg = svg.replace("{color}", self._rgba_to_hex(color)).replace("{secondary_color}", self._rgba_to_hex(secondary_color))
        cache_key = (rendered_svg, scale)
        if cache_key in self._svg_cache:
            return self._svg_cache[cache_key]
        render_size = self._svg_render_size(rendered_svg, round(38 * scale))
        try:
            import cairosvg

            png = cairosvg.svg2png(bytestring=rendered_svg.encode("utf-8"), output_width=render_size[0], output_height=render_size[1])
            icon = self._Image.open(io.BytesIO(png)).convert("RGBA")
        except Exception as exc:
            try:
                icon = self._render_basic_svg(rendered_svg, render_size)
            except Exception as fallback_exc:
                self._debug(f"Inline SVG failed: {exc}; fallback failed: {fallback_exc}")
                icon = None
        self._svg_cache[cache_key] = icon
        return icon

    def _svg_render_size(self, svg, max_size):
        root = ElementTree.fromstring(svg)
        view_box = root.attrib.get("viewBox", f"0 0 {max_size} {max_size}").split()
        width = float(view_box[2])
        height = float(view_box[3])
        if width >= height:
            return max_size, round(max_size * height / width)
        return round(max_size * width / height), max_size

    def _render_basic_svg(self, svg, render_size):
        from PIL import ImageChops, ImageDraw, ImageFont

        root = ElementTree.fromstring(svg)
        view_box = root.attrib.get("viewBox", f"0 0 {render_size[0]} {render_size[1]}").split()
        min_x, min_y, width, height = [float(value) for value in view_box]
        scale_x = render_size[0] / width
        scale_y = render_size[1] / height
        image = self._Image.new("RGBA", render_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image, "RGBA")

        def strip_namespace(tag):
            return tag.split("}", 1)[-1]

        def x(value):
            return (float(value) - min_x) * scale_x

        def y(value):
            return (float(value) - min_y) * scale_y

        def color(value, default=(0, 0, 0, 255)):
            if not value or value == "none":
                return default
            value = value.lstrip("#")
            if len(value) == 6:
                return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
            return default

        def points(value):
            return [tuple(float(part) for part in pair.split(",")) for pair in value.split()]

        def scaled_points(value):
            return [(x(px), y(py)) for px, py in points(value)]

        for element in root.iter():
            match strip_namespace(element.tag):
                case "circle":
                    cx = x(element.attrib["cx"])
                    cy = y(element.attrib["cy"])
                    radius = float(element.attrib["r"]) * min(scale_x, scale_y)
                    stroke_width = round(float(element.attrib.get("stroke-width", 1)) * min(scale_x, scale_y))
                    draw.ellipse(
                        (cx - radius, cy - radius, cx + radius, cy + radius),
                        fill=color(element.attrib.get("fill")),
                        outline=color(element.attrib.get("stroke")),
                        width=max(stroke_width, 1),
                    )
                case "text":
                    font_size = round(float(element.attrib.get("font-size", 12)) * min(scale_x, scale_y))
                    try:
                        font = ImageFont.truetype("Arial Bold.ttf", font_size)
                    except OSError:
                        font = ImageFont.load_default(size=font_size)
                    draw.text(
                        (x(element.attrib.get("x", 0)), y(element.attrib.get("y", 0))),
                        element.text or "",
                        fill=color(element.attrib.get("fill")),
                        font=font,
                        anchor="mm" if element.attrib.get("text-anchor") == "middle" else None,
                    )
                case "polyline":
                    stroke_width = round(float(element.attrib.get("stroke-width", 1)) * min(scale_x, scale_y))
                    draw.line(
                        scaled_points(element.attrib["points"]),
                        fill=color(element.attrib.get("stroke")),
                        width=max(stroke_width, 1),
                        joint="curve",
                    )
                case "polygon":
                    draw.polygon(
                        scaled_points(element.attrib["points"]),
                        fill=color(element.attrib.get("fill"), None),
                        outline=color(element.attrib.get("stroke")),
                    )
                case "path":
                    fill = color(element.attrib.get("fill"))
                    mask = self._Image.new("L", render_size, 0)
                    for polygon in self._path_to_polygons(element.attrib["d"]):
                        polygon_mask = self._Image.new("L", render_size, 0)
                        ImageDraw.Draw(polygon_mask).polygon([(x(px), y(py)) for px, py in polygon], fill=255)
                        mask = ImageChops.difference(mask, polygon_mask)
                    fill_image = self._Image.new("RGBA", render_size, fill)
                    image.paste(fill_image, (0, 0), mask)
        return image

    def _path_to_polygons(self, path):
        tokens = re.findall(r"[A-Za-z]|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", path.replace(",", " "))
        polygons = []
        polygon = []
        current = (0.0, 0.0)
        start = None
        command = None
        index = 0

        def is_command(value):
            return re.fullmatch(r"[A-Za-z]", value) is not None

        def number():
            nonlocal index
            value = float(tokens[index])
            index += 1
            return value

        def line_to(point):
            nonlocal current
            current = point
            polygon.append(current)

        while index < len(tokens):
            if is_command(tokens[index]):
                command = tokens[index]
                index += 1

            match command:
                case "M":
                    current = (number(), number())
                    start = current
                    polygon = [current]
                    command = "L"
                case "m":
                    current = (current[0] + number(), current[1] + number())
                    start = current
                    polygon = [current]
                    command = "l"
                case "L":
                    line_to((number(), number()))
                case "l":
                    line_to((current[0] + number(), current[1] + number()))
                case "H":
                    line_to((number(), current[1]))
                case "h":
                    line_to((current[0] + number(), current[1]))
                case "V":
                    line_to((current[0], number()))
                case "v":
                    line_to((current[0], current[1] + number()))
                case "C":
                    controls = [(number(), number()), (number(), number())]
                    end = (number(), number())
                    polygon.extend(self._cubic_points(current, controls[0], controls[1], end))
                    current = end
                case "c":
                    controls = [
                        (current[0] + number(), current[1] + number()),
                        (current[0] + number(), current[1] + number()),
                    ]
                    end = (current[0] + number(), current[1] + number())
                    polygon.extend(self._cubic_points(current, controls[0], controls[1], end))
                    current = end
                case "Z" | "z":
                    if start and current != start:
                        polygon.append(start)
                    if start:
                        current = start
                    if polygon:
                        polygons.append(polygon)
                    polygon = []
                    start = None
                case _:
                    raise ValueError(f"Unsupported SVG path command: {command}")

        if polygon:
            polygons.append(polygon)
        return polygons

    def _cubic_points(self, p0, p1, p2, p3, steps=12):
        points = []
        for step in range(1, steps + 1):
            t = step / steps
            mt = 1 - t
            points.append((
                mt ** 3 * p0[0] + 3 * mt ** 2 * t * p1[0] + 3 * mt * t ** 2 * p2[0] + t ** 3 * p3[0],
                mt ** 3 * p0[1] + 3 * mt ** 2 * t * p1[1] + 3 * mt * t ** 2 * p2[1] + t ** 3 * p3[1],
            ))
        return points

    def _load_icon(self, icon_href):
        if not icon_href or pd.isna(icon_href):
            return None
        if icon_href in self._icon_cache:
            return self._icon_cache[icon_href]
        try:
            response = requests.get(icon_href, headers={"User-Agent": self.USER_AGENT}, timeout=20)
            response.raise_for_status()
            icon = self._Image.open(io.BytesIO(response.content)).convert("RGBA")
        except Exception as exc:
            self._debug(f"Icon failed ({icon_href}): {exc}")
            icon = None
        self._icon_cache[icon_href] = icon
        return icon

    def _save_pdf(self, image, vector_elements, label_elements, legend_entries, page_size, output_path):
        pdf_path = f"{output_path} OSM A3.pdf"
        if not vector_elements and not label_elements and not legend_entries:
            image.save(pdf_path, "PDF", resolution=self.DPI)
            return
        image_bytes = zlib.compress(image.convert("RGB").tobytes(), level=9)
        page_width = self.A3_LANDSCAPE_MM[0] / 25.4 * 72
        page_height = self.A3_LANDSCAPE_MM[1] / 25.4 * 72
        content = self._pdf_content_stream(vector_elements, label_elements, legend_entries, page_size, page_width, page_height)
        self._write_pdf(pdf_path, image_bytes, page_size, page_width, page_height, content)

    def _pdf_content_stream(self, vector_elements, label_elements, legend_entries, page_size, page_width, page_height):
        width, height = page_size
        parts = [f"q\n{page_width:.4f} 0 0 {page_height:.4f} 0 0 cm\n/Im0 Do\nQ\n"]
        for element in vector_elements:
            color = element["color"]
            stroke_width = element["stroke_width"] / width * page_width
            r, g, b = color[0] / 255, color[1] / 255, color[2] / 255
            dash = f"[0 {stroke_width * 2:.4f}] 0 d\n" if element.get("dotted") else "[] 0 d\n"
            parts.append(f"{r:.4f} {g:.4f} {b:.4f} RG\n{stroke_width:.4f} w\n1 J\n1 j\n{dash}")
            for index, (x, y) in enumerate(element["points"]):
                pdf_x = x / width * page_width
                pdf_y = page_height - (y / height * page_height)
                operator = "m" if index == 0 else "l"
                parts.append(f"{pdf_x:.4f} {pdf_y:.4f} {operator}\n")
            if element["close"]:
                parts.append("h\n")
            parts.append("S\n")
        for label in label_elements:
            x, y = label["point"]
            pdf_x = x / width * page_width
            pdf_y = page_height - (y / height * page_height)
            size = label["size"]
            angle = math.radians(-label["direction"])
            cos_angle = math.cos(angle)
            sin_angle = math.sin(angle)
            text = self._pdf_escape_text(label["text"])
            label_width = len(label["text"]) * size * 0.5
            align = label.get("align", "center")
            anchor_x = 0 if align == "left" else -label_width / 2
            anchor_y = -size / 2
            offset_x = anchor_x * cos_angle - anchor_y * sin_angle
            offset_y = anchor_x * sin_angle + anchor_y * cos_angle
            if label["text"].startswith("✈"):
                parts.append(self._pdf_plane_icon(pdf_x + offset_x, pdf_y + offset_y, size))
                continue
            parts.append(
                "q\nBT\n"
                f"/F1 {size:.4f} Tf\n"
                "0 0 0 rg\n"
                f"{cos_angle:.6f} {sin_angle:.6f} {-sin_angle:.6f} {cos_angle:.6f} {pdf_x + offset_x:.4f} {pdf_y + offset_y:.4f} Tm\n"
                f"({text}) Tj\n"
                "ET\nQ\n"
            )
        parts.append(self._pdf_legend(legend_entries, page_width, page_height))
        return "".join(parts).encode("cp1252", errors="replace")

    def _pdf_legend(self, entries, page_width, page_height):
        if not entries:
            return ""
        groups = []
        for entry in entries:
            if not groups or groups[-1][0] != entry["layer"]:
                groups.append((entry["layer"], []))
            groups[-1][1].append(entry)

        width = 185
        margin = 16
        top_padding = 10
        row_height = 10.5
        heading_height = 12
        height = top_padding * 2 + sum(heading_height + len(group_entries) * row_height for _, group_entries in groups)
        x = page_width - margin - width
        y = 30
        parts = [
            "q\n",
            "1 1 1 rg\n0.88 0.88 0.88 RG\n0.6 w\n",
            f"{x:.4f} {y:.4f} {width:.4f} {height:.4f} re\nB\n",
        ]
        cursor = y + height - top_padding - 7
        for layer_name, group_entries in groups:
            parts.append(self._pdf_text_at(layer_name, x + 8, cursor, 7.4, bold=True))
            cursor -= heading_height
            for entry in group_entries:
                sample_x = x + 14
                sample_y = cursor + 3
                text_x = x + 32
                parts.append(self._pdf_legend_sample(entry, sample_x, sample_y))
                parts.append(self._pdf_text_at(entry["name"], text_x, cursor, 6.7))
                cursor -= row_height
        parts.append("Q\n")
        return "".join(parts)

    def _pdf_legend_sample(self, entry, x, y):
        color = entry["color"]
        r, g, b = color[0] / 255, color[1] / 255, color[2] / 255
        if entry["shape"] == "line":
            width = max(entry["stroke_width"] * 0.7, 0.5)
            dash = f"[0 {width * 2:.4f}] 0 d\n" if entry["dotted"] else "[] 0 d\n"
            return (
                "q\n"
                f"{r:.4f} {g:.4f} {b:.4f} RG\n{width:.4f} w\n1 J\n1 j\n{dash}"
                f"{x - 8:.4f} {y:.4f} m\n{x + 8:.4f} {y:.4f} l\nS\nQ\n"
            )
        if entry["shape"] == "polygon":
            return (
                "q\n"
                f"{r:.4f} {g:.4f} {b:.4f} RG\n0.9 w\n[] 0 d\n"
                f"{x - 6:.4f} {y - 4:.4f} m\n{x + 6:.4f} {y - 4:.4f} l\n{x + 6:.4f} {y + 4:.4f} l\n{x - 6:.4f} {y + 4:.4f} l\nh\nS\nQ\n"
            )
        label = entry.get("fixed_label")
        if label and label.startswith("✈"):
            return self._pdf_plane_icon(x, y, 6.2)
        parts = [
            "q\n",
            f"{r:.4f} {g:.4f} {b:.4f} rg\n1 1 1 RG\n0.7 w\n",
            f"{x - 4.2:.4f} {y - 4.2:.4f} 8.4 8.4 re\nB\nQ\n",
        ]
        if label:
            parts.append(self._pdf_text_at(label, x + 6, y - 2.2, 6.4))
        return "".join(parts)

    def _pdf_text_at(self, text, x, y, size, bold=False):
        escaped = self._pdf_escape_text(text)
        return (
            "q\nBT\n"
            f"/F1 {size:.4f} Tf\n0 0 0 rg\n"
            f"1 0 0 1 {x:.4f} {y:.4f} Tm\n({escaped}) Tj\n"
            "ET\nQ\n"
        )

    def _pdf_escape_text(self, text):
        return str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def _pdf_plane_icon(self, x, y, size):
        half = size / 2
        nose = x + size * 0.62
        tail = x - size * 0.55
        body_top = y + size * 0.08
        body_bottom = y - size * 0.08
        wing_top = y + size * 0.38
        wing_bottom = y - size * 0.34
        return (
            "q\n0 0 0 rg\n0 0 0 RG\n0.8 w\n1 J\n1 j\n"
            f"{tail:.4f} {body_bottom:.4f} m\n"
            f"{x + size * 0.32:.4f} {body_bottom:.4f} l\n"
            f"{nose:.4f} {y:.4f} l\n"
            f"{x + size * 0.32:.4f} {body_top:.4f} l\n"
            f"{tail:.4f} {body_top:.4f} l\n"
            f"{tail - size * 0.12:.4f} {y + size * 0.28:.4f} l\n"
            f"{tail + size * 0.08:.4f} {body_top:.4f} l\n"
            f"{tail + size * 0.08:.4f} {body_bottom:.4f} l\n"
            f"{tail - size * 0.08:.4f} {y - size * 0.22:.4f} l\n"
            f"{tail + size * 0.18:.4f} {body_bottom:.4f} l\nh\nf\n"
            f"{x - size * 0.08:.4f} {body_top:.4f} m\n"
            f"{x + size * 0.16:.4f} {body_top:.4f} l\n"
            f"{x - size * 0.22:.4f} {wing_top:.4f} l\n"
            f"{x - size * 0.36:.4f} {wing_top:.4f} l\nh\nf\n"
            f"{x - size * 0.03:.4f} {body_bottom:.4f} m\n"
            f"{x + size * 0.15:.4f} {body_bottom:.4f} l\n"
            f"{x - size * 0.18:.4f} {wing_bottom:.4f} l\n"
            f"{x - size * 0.3:.4f} {wing_bottom:.4f} l\nh\nf\n"
            "Q\n"
        )

    def _write_pdf(self, pdf_path, image_bytes, page_size, page_width, page_height, content):
        image_width, image_height = page_size
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width:.4f} {page_height:.4f}] "
                "/Resources << /XObject << /Im0 5 0 R >> /Font << /F1 6 0 R >> >> /Contents 4 0 R >>"
            ).encode("ascii"),
            b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"endstream",
            (
                f"<< /Type /XObject /Subtype /Image /Width {image_width} /Height {image_height} "
                f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length {len(image_bytes)} >>\nstream\n"
            ).encode("ascii") + image_bytes + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]
        pdf = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for index, obj in enumerate(objects, start=1):
            offsets.append(len(pdf))
            pdf.extend(f"{index} 0 obj\n".encode("ascii"))
            pdf.extend(obj)
            pdf.extend(b"\nendobj\n")
        xref_offset = len(pdf)
        pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        pdf.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        pdf.extend(
            (
                f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref_offset}\n%%EOF\n"
            ).encode("ascii")
        )
        Path(pdf_path).write_bytes(pdf)

    def _draw_point_geometry(self, draw, geometry, color, secondary_color, zoom, world_bounds, page_size, icon_href=None, svg=None, scale=1.0):
        if geometry is None or geometry.is_empty:
            return
        match geometry:
            case Point():
                self._draw_point(draw, geometry, color, secondary_color, zoom, world_bounds, page_size, icon_href, svg, scale)
            case MultiPoint():
                for point in geometry.geoms:
                    self._draw_point(draw, point, color, secondary_color, zoom, world_bounds, page_size, icon_href, svg, scale)
            case GeometryCollection():
                for child in geometry.geoms:
                    self._draw_point_geometry(draw, child, color, secondary_color, zoom, world_bounds, page_size, icon_href, svg, scale)

    def _geometry_to_svg(self, geometry, color, zoom, world_bounds, page_size, stroke_width=None, dotted=False):
        if geometry is None or geometry.is_empty:
            return []
        match geometry:
            case LineString():
                element = self._line_to_svg(geometry, color, zoom, world_bounds, page_size, stroke_width, dotted)
                return [element] if element else []
            case ShapelyMultiLineString():
                return [element for line in geometry.geoms if (element := self._line_to_svg(line, color, zoom, world_bounds, page_size, stroke_width, dotted))]
            case Polygon():
                element = self._polygon_to_svg(geometry, color, zoom, world_bounds, page_size, stroke_width)
                return [element] if element else []
            case MultiPolygon():
                return [element for polygon in geometry.geoms if (element := self._polygon_to_svg(polygon, color, zoom, world_bounds, page_size, stroke_width))]
            case GeometryCollection():
                elements = []
                for child in geometry.geoms:
                    elements.extend(self._geometry_to_svg(child, color, zoom, world_bounds, page_size, stroke_width, dotted))
                return elements
        return []

    def _geometry_to_labels(self, row, geometry, zoom, world_bounds, page_size):
        if geometry is None or geometry.is_empty:
            return []
        text = row.get("name")
        if not text or pd.isna(text):
            return []
        point = self._label_point(geometry)
        if point is None:
            return []
        return [{
            "text": str(text),
            "point": self._lon_lat_to_page(point.x, point.y, zoom, world_bounds, page_size),
            "size": self._row_label_size(row),
            "direction": self._row_label_direction(row),
        }]

    def _geometry_to_fixed_labels(self, row, geometry, zoom, world_bounds, page_size):
        label = self._row_fixed_label(row)
        if not label or geometry is None or geometry.is_empty:
            return []
        return [
            {
                "text": label,
                "point": (point[0] + 14, point[1] - 14),
                "size": self._row_label_size(row),
                "direction": 0.0,
                "align": "left",
            }
            for point in self._point_label_points(geometry, zoom, world_bounds, page_size)
        ]

    def _point_label_points(self, geometry, zoom, world_bounds, page_size):
        match geometry:
            case Point():
                return [self._lon_lat_to_page(geometry.x, geometry.y, zoom, world_bounds, page_size)]
            case MultiPoint():
                return [self._lon_lat_to_page(point.x, point.y, zoom, world_bounds, page_size) for point in geometry.geoms]
            case GeometryCollection():
                points = []
                for child in geometry.geoms:
                    points.extend(self._point_label_points(child, zoom, world_bounds, page_size))
                return points
        return []

    def _label_point(self, geometry):
        match geometry:
            case Point():
                return geometry
            case MultiPoint() | MultiPolygon() | ShapelyMultiLineString() | GeometryCollection():
                return geometry.representative_point()
            case Polygon():
                return geometry.representative_point()
            case LineString():
                return geometry.interpolate(0.5, normalized=True)
        return None

    def _line_to_svg(self, line, color, zoom, world_bounds, page_size, stroke_width=None, dotted=False):
        points = self._coords_to_page(line.coords, zoom, world_bounds, page_size)
        if len(points) < 2:
            return None
        return {"points": points, "close": False, "color": color, "stroke_width": stroke_width or 5, "dotted": dotted}

    def _polygon_to_svg(self, polygon, color, zoom, world_bounds, page_size, stroke_width=None):
        outline = self._coords_to_page(polygon.exterior.coords, zoom, world_bounds, page_size)
        if len(outline) < 3:
            return None
        return {"points": outline, "close": True, "color": color, "stroke_width": stroke_width or 2}

    def _draw_line(self, draw, line, color, zoom, world_bounds, page_size, stroke_width=None):
        points = self._coords_to_page(line.coords, zoom, world_bounds, page_size)
        if len(points) > 1:
            draw.line(points, fill=color, width=stroke_width or 5, joint="curve")

    def _draw_polygon(self, draw, polygon, color, zoom, world_bounds, page_size, stroke_width=None):
        outline = self._coords_to_page(polygon.exterior.coords, zoom, world_bounds, page_size)
        if len(outline) < 3:
            return
        draw.line(outline, fill=color, width=stroke_width or 2, joint="curve")

    def _coords_to_page(self, coords, zoom, world_bounds, page_size):
        return [self._lon_lat_to_page(coord[0], coord[1], zoom, world_bounds, page_size) for coord in coords]

    def _lon_lat_to_page(self, lon, lat, zoom, world_bounds, page_size):
        world_x, world_y = self._lon_lat_to_world_px(lon, lat, zoom)
        min_x, min_y, max_x, max_y = world_bounds
        return (
            (world_x - min_x) / (max_x - min_x) * page_size[0],
            (world_y - min_y) / (max_y - min_y) * page_size[1],
        )

    def _lon_lat_to_world_px(self, lon, lat, zoom):
        lat = min(max(lat, -85.05112878), 85.05112878)
        scale = self.TILE_SIZE * 2 ** zoom
        x = (lon + 180.0) / 360.0 * scale
        lat_rad = math.radians(lat)
        y = (0.5 - math.log((1 + math.sin(lat_rad)) / (1 - math.sin(lat_rad))) / (4 * math.pi)) * scale
        return x, y

class FullKmlExporter:
    def __init__(self):
        self._kml = simplekml.Kml()

    def export(self, data: dict, output_path):
        for layer_name in data.keys():
            folder = self._kml.newfolder(name=layer_name)
            add_to_kml(data[layer_name], folder)
        self._kml.save(f"{output_path} FULL.kml")

class HidingZoneExporter:
    def __init__(self):
        self._kml = simplekml.Kml()

    @staticmethod
    def calculate_epsg(row):
        point = row["geometry"]
        return int(32700 - (copysign(1, point.y) + 1) / 2 * 100 + (floor((180 + point.x) / 6) + 1))

    @staticmethod
    def remove_without_size( df):
        new_df = df.copy()
        new_df.reset_index(drop=True,inplace=True)
        for x in new_df.iterrows():
            if not x[1]["hiding_size"]:
                new_df.drop(x[0],inplace=True)
        return new_df

    def export(self, data: dict, output_path):
        layer = self._kml.newfolder(name="Hiding Zones")
        partials = []

        for layer_name in data.keys():
            for ln in data[layer_name].keys():
                    row = data[layer_name][ln]
                    if 'hiding_size' not in row.columns:
                        continue
                    rw = self.remove_without_size(row)

                    rw.set_crs(4326, inplace=True)
                    rw["epsg"] = rw.apply(HidingZoneExporter.calculate_epsg, axis=1)

                    for epsg in rw["epsg"].unique():
                        partial_df = rw[rw["epsg"] == epsg]
                        partial_df.to_crs(epsg, inplace=True)

                        circles = partial_df.buffer(partial_df["hiding_size"], 12).boundary
                        circles = circles.apply(lambda x: MultiLineString([x.coords, x.coords[-2::]]))
                        partial_df['geometry'] = circles
                        partial_df.to_crs(4326, inplace=True)
                        partials.append(partial_df)

        dat = GeoDataFrame(concat(partials), crs="EPSG:4326")
        add_to_kml({'Hiding Zones':dat}, layer)
        self._kml.save(f"{output_path} HZ.kml")
