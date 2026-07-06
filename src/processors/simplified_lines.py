import json
import math
import re

import geopandas
import pandas as pd
from shapely import LineString

from processors.hiding_zones import calculate_epsg


class SimplifiedLines:
    def __init__(self, config):
        self.file = config.get("file")
        self.min_stops = config.get("min_stops", 2)
        self.key_column = config.get("key_column", "name")
        self.prefix_ignores = config.get("prefix_ignores", [])
        self.normalization_list = config.get("normalization_list", [])
        self.aliases = config.get("aliases", {})
        self.candidate_distance_cutoff = config.get("candidate_distance_cutoff")
        self.source_layer = config.get("source_layer")
        self.source_type = config.get("source_type")
        self._context = {}
        if not self.file:
            raise Exception("simplified_lines processor requires a file")

    def set_context(self, context):
        self._context = context

    def process(self, frame):
        with open(self.file, encoding="utf-8") as file:
            data = json.load(file)

        points_by_name = self._points_by_name(self._source_frame(frame))
        rows = []
        for line in data.get("lines", []):
            points = []
            if self.candidate_distance_cutoff is None and not self.source_layer:
                for stop in line.get("stops", []):
                    point = self._find_point(stop, points_by_name)
                    if point is not None:
                        points.append(point)
            else:
                points = self._resolve_line_points(line.get("stops", []), points_by_name)
            if len(points) < self.min_stops:
                continue
            rows.append({
                "name": line.get("name", line.get("ref", "line")),
                "type": line.get("ref", line.get("name", "line")),
                "geometry": LineString(points),
            })

        return geopandas.GeoDataFrame(pd.DataFrame(rows), geometry="geometry", crs="EPSG:4326")

    def _source_frame(self, frame):
        if not self.source_layer:
            return frame

        layer = self._context.get(self.source_layer)
        if layer is None:
            raise Exception(f"source layer {self.source_layer} is not available")

        if self.source_type:
            source = layer.get(self.source_type)
            if source is None:
                raise Exception(f"source type {self.source_type} is not available in layer {self.source_layer}")
            return source

        return geopandas.GeoDataFrame(pd.concat(layer.values()), geometry="geometry", crs="EPSG:4326")

    def _points_by_name(self, frame):
        points_by_name = {}
        for _, row in frame.iterrows():
            name = row.get(self.key_column)
            geometry = row.get("geometry")
            if not name or geometry is None or geometry.is_empty:
                continue
            fixed_name = self._normalize_name(name)
            points_by_name.setdefault(fixed_name, []).append(geometry)
        if self.source_layer:
            return points_by_name
        if self.candidate_distance_cutoff is not None:
            return {name: self._cluster_candidates(points) for name, points in points_by_name.items()}
        return {name: geopandas.GeoSeries(points, crs="EPSG:4326").union_all().centroid for name, points in points_by_name.items()}

    def _cluster_candidates(self, points):
        if len(points) <= 1:
            return points

        frame = geopandas.GeoDataFrame(geometry=points, crs="EPSG:4326")
        frame["epsg"] = frame.apply(calculate_epsg, axis=1)
        projected = frame.to_crs(frame["epsg"].iloc[0])
        left_idx, right_idx = projected.sindex.query(
            projected.geometry,
            predicate="dwithin",
            distance=self.candidate_distance_cutoff,
        )

        neighbours = {idx: set() for idx in projected.index}
        for left, right in zip(left_idx, right_idx):
            left = projected.index[left]
            right = projected.index[right]
            if left == right:
                continue
            neighbours[left].add(right)
            neighbours[right].add(left)

        candidates = []
        visited = set()
        for idx in projected.index:
            if idx in visited:
                continue
            component = set()
            stack = [idx]
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                component.add(current)
                stack.extend(neighbours[current] - visited)
            component_indices = [idx for idx in frame.index if idx in component]
            candidates.append(frame.loc[component_indices].geometry.union_all().centroid)
        return candidates

    def _find_point(self, stop, points_by_name):
        names = [stop, *self.aliases.get(stop, [])]
        for name in names:
            point = points_by_name.get(self._normalize_name(name))
            if point is not None:
                return point
        return None

    def _find_candidates(self, stop, points_by_name):
        candidates = []
        names = [stop, *self.aliases.get(stop, [])]
        seen = set()
        for name in names:
            for point in points_by_name.get(self._normalize_name(name), []):
                key = point.wkb
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(point)
        return candidates

    def _resolve_line_points(self, stops, points_by_name):
        candidates_by_stop = []
        for stop in stops:
            candidates = self._find_candidates(stop, points_by_name)
            if candidates:
                candidates_by_stop.append(candidates)

        if not candidates_by_stop:
            return []

        costs = [[0] * len(candidates_by_stop[0])]
        previous = [[None] * len(candidates_by_stop[0])]

        for stop_idx in range(1, len(candidates_by_stop)):
            stop_costs = []
            stop_previous = []
            for candidate in candidates_by_stop[stop_idx]:
                best_cost = None
                best_previous = None
                for previous_idx, previous_candidate in enumerate(candidates_by_stop[stop_idx - 1]):
                    cost = costs[stop_idx - 1][previous_idx] + self._distance(previous_candidate, candidate)
                    if best_cost is None or cost < best_cost:
                        best_cost = cost
                        best_previous = previous_idx
                stop_costs.append(best_cost)
                stop_previous.append(best_previous)
            costs.append(stop_costs)
            previous.append(stop_previous)

        selected_idx = min(range(len(costs[-1])), key=lambda idx: costs[-1][idx])
        selected_points = []
        for stop_idx in range(len(candidates_by_stop) - 1, -1, -1):
            selected_points.append(candidates_by_stop[stop_idx][selected_idx])
            selected_idx = previous[stop_idx][selected_idx]
        selected_points.reverse()
        return selected_points

    def _distance(self, a, b):
        lat = math.radians((a.y + b.y) / 2)
        x = math.radians(b.x - a.x) * math.cos(lat)
        y = math.radians(b.y - a.y)
        return math.sqrt(x * x + y * y) * 6371000

    def _normalize_name(self, name):
        normalized = str(name).upper()
        for prefix in self.prefix_ignores:
            normalized = normalized.removeprefix(prefix.upper())
        for normalization in self.normalization_list:
            normalized = normalized.replace(normalization.get("from", "").upper(), normalization.get("to", "").upper())
        normalized = re.sub(r"[^A-Z0-9]+", "", normalized)
        return normalized
