import json


class TransitLineBasedTags(object):
    def __init__(self, config):
        self.file = config.get("file")
        self.equivalent_station_names = config.get("equivalent_station_names", [])
    def process(self, frame):
        with open(self.file, encoding="utf-8") as file:
            data = json.load(file)

        def process_lines(point):
            equivalent_names = [point.get("name")]
            if equivalent_names[0] is None:
                return None
            for rw in self.equivalent_station_names:
                if point.get("name") == rw.get("replacement-station-name", None):
                    equivalent_names = equivalent_names + (rw.get("station_list", []))
            lines = []
            for line in data.get("lines", []):
                if len((set(equivalent_names) & set(line.get("stops", [])))) >0:
                    lines.append(line["ref"])
            return "\n".join(lines)

        def process_neighbour_stops(point):
            equivalent_names = [point.get("name")]
            if equivalent_names[0] is None:
                return None
            for rw in self.equivalent_station_names:
                if point.get("name") == rw.get("replacement-station-name", None):
                    equivalent_names = equivalent_names + (rw.get("station_list", []))
            neighbour_stops = []
            for line in data.get("lines", []):
                prev = None
                nxt = False
                for stop in line.get("stops", []):
                    if nxt:
                        neighbour_stops.append(stop)
                        nxt = False
                    if stop in equivalent_names:
                        nxt = True
                        if prev != stop and prev is not None:
                            neighbour_stops.append(prev)
                    prev = stop
            return "\n".join(list(set(neighbour_stops)))

        frame["_tag.lines"] = frame.apply(process_lines, axis=1)
        frame["_tag.neighbours"] = frame.apply(process_neighbour_stops, axis=1)

        return frame
