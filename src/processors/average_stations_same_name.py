import geopandas
import pandas as pd

from processors.hiding_zones import calculate_epsg


# Take all stations with the same name together, and give them their centroid as location.
class AverageStationsSameName:
    def __init__(self, config):
        self.prefix_ignores = config.get("prefix_ignores", [])
        self.distance_cutoff = config.get("distance_cutoff")
        self.equivalent_station_names = config.get("equivalent_station_names", [])
        self._equivalent_names, self._replacement_station_names = self._build_equivalent_names()
        self._overlapping_equivalent_names = self._find_overlapping_equivalent_names()

    def process(self, frame: pd.DataFrame)->pd.DataFrame:
        new = geopandas.GeoDataFrame(columns=['name', 'geometry', 'type', 'description'], crs="EPSG:4326")
        def namefix(rw):
            nm = self._normalize_name(rw.get('name',''))
            return self._equivalent_names.get(nm, nm)

        frame = geopandas.GeoDataFrame(frame.copy(), geometry="geometry", crs=getattr(frame, "crs", None) or "EPSG:4326")

        if self.distance_cutoff is None:
            frame['fixed_name'] = frame.apply(namefix, axis=1)
            bframe = frame.dissolve(by='fixed_name')

            for x in bframe.iloc:
                source = frame[frame['fixed_name'] == x.name]
                new.loc[len(new)] = {
                    'name': self._replacement_station_names.get(x.name, x.get('name')),
                    'geometry': x["geometry"].centroid,
                    'type': x.get('type'),
                    'description': self._description_for_frame(source),
                }
            return new

        frame['normalized_name'] = frame.apply(lambda rw: self._normalize_name(rw.get('name','')), axis=1)
        frame['fixed_name'] = frame['normalized_name']
        self._assign_equivalent_names_by_distance(frame)

        for _, name_frame in frame.groupby('fixed_name'):
            for component in self._distance_components(name_frame):
                dissolved = component.geometry.union_all()
                row = name_frame.loc[component.index[0]]
                new.loc[len(new)] = {
                    'name': self._replacement_station_names.get(row.get('fixed_name'), row.get('name')),
                    'geometry': dissolved.centroid,
                    'type': row.get('type'),
                    'description': self._description_for_frame(component),
                }

        return new

    def _distance_components(self, frame):
        if len(frame) <= 1:
            return [frame]

        projected = frame.copy()
        projected["epsg"] = projected.apply(calculate_epsg, axis=1)
        projected = projected.to_crs(projected["epsg"].iloc[0])
        left_idx, right_idx = projected.sindex.query(
            projected.geometry,
            predicate='dwithin',
            distance=self.distance_cutoff,
        )

        neighbours = {idx: set() for idx in projected.index}
        for left, right in zip(left_idx, right_idx):
            left = projected.index[left]
            right = projected.index[right]
            if left == right:
                continue
            neighbours[left].add(right)
            neighbours[right].add(left)

        components = []
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
            components.append(frame.loc[component_indices])
        return components

    def _build_equivalent_names(self):
        equivalents = {}
        replacement_station_names = {}
        for station_group in self.equivalent_station_names:
            names = station_group.get("station_list", [])
            replacement_station_name = station_group.get("replacement-station-name")
            if not names or not replacement_station_name:
                continue
            canonical = self._normalize_name(replacement_station_name)
            replacement_station_names[canonical] = replacement_station_name
            for name in names:
                equivalents[self._normalize_name(name)] = canonical
        return equivalents, replacement_station_names

    def _find_overlapping_equivalent_names(self):
        occurrences = {}
        for station_group in self.equivalent_station_names:
            for name in station_group.get("station_list", []):
                normalized_name = self._normalize_name(name)
                occurrences[normalized_name] = occurrences.get(normalized_name, 0) + 1
        return {name for name, count in occurrences.items() if count > 1}

    def _assign_equivalent_names_by_distance(self, frame):
        for station_group in self.equivalent_station_names:
            names = {self._normalize_name(name) for name in station_group.get("station_list", [])}
            replacement_station_name = station_group.get("replacement-station-name")
            if not names or not replacement_station_name:
                continue

            canonical = self._normalize_name(replacement_station_name)
            is_overlapping_group = bool(names & self._overlapping_equivalent_names)
            group_frame = frame[frame['normalized_name'].isin(names)]
            if group_frame.empty:
                continue

            for component in self._distance_components(group_frame):
                component_names = set(component['normalized_name'])
                if is_overlapping_group and len(component_names) < 2:
                    continue
                frame.loc[component.index, 'fixed_name'] = canonical

    def _normalize_name(self, name):
        normalized = str(name).upper()
        for prefix in self.prefix_ignores:
            normalized = normalized.removeprefix(prefix.upper())
        return normalized

    def _description_for_frame(self, frame):
        descriptions = []
        for column in ('description', 'Description'):
            if column not in frame.columns:
                continue
            for value in frame[column].dropna():
                if value and value not in descriptions:
                    descriptions.append(value)
        return '; '.join(descriptions) if descriptions else None
