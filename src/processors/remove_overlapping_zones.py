from operator import index

from processors.hiding_zones import calculate_epsg


class RemoveOverlappingZones:
    def __init__(self, config):
        self.epsg = config.get("epsg",None)
        self.config = config.get("config", {})
        self.default_distance = config.get("distance", 100)
        self.default_size = config.get("size", 250)

    def get_distance_for_type(self, typ):
        config_data = self.config.get(typ, {})
        return config_data.get("distance",self.default_distance)
    def get_allowed_intrusion(self, typ):
        config_data = self.config.get(typ, {})
        return config_data.get("allowed_intrusion", 0)

    def get_size(self, typ):
        config_data = self.config.get(typ, {})
        return config_data.get("size", self.default_size)

    def get_max_size(self):
        res = 0
        for x in self.config:
            res = max(self.config[x].get("size", 0), res)
        return res

    def get_priority(self, typ):
        config_data = self.config.get(typ, {})
        return config_data.get("importance", 1)

    def process(self, df):
        new_df = df.copy()
        new_df.set_crs(4326,inplace=True)
        new_df.reset_index(drop=True,inplace=True)
        if not self.epsg:
            new_df["epsg"] = new_df.apply(calculate_epsg, axis=1)

        new_df.to_crs(new_df["epsg"].unique()[0],inplace=True)
        idx = new_df.sindex

        left_idx, right_idx = idx.query(
            new_df.geometry,
            predicate='dwithin',
            distance=self.get_max_size()*2.1
        )
        while True:
            nbs = {}
            nb_importances = {}
            for ids in zip(left_idx, right_idx):
                idx, idy = ids[0], ids[1]
                if idx == idy:
                    continue

                # Keyerrors occur due to deletions.
                try:
                    x= new_df.loc[idx]
                    y = new_df.loc[idy]
                except KeyError:
                    continue

                # Score only counts for higher prios, or for same prio.
                if self.get_priority(x["type"]) > self.get_priority(y["type"]):
                    continue

                y_size = self.get_size(y["type"])
                x_size = self.get_size(x["type"])
                dist = x["geometry"].distance(y["geometry"])
                allowed_intrusion = self.get_allowed_intrusion(x["type"])
                score = x_size + y_size - allowed_intrusion - dist
                if x_size + y_size > allowed_intrusion + dist:
                    nb_importances[idx] = self.get_priority(x["type"])
                    nbs[idx] = nbs.get(idx,0)+score
            lowest_importance = 1000
            highest_score = 0
            idx_to_drop = -1
            for nb in nbs.keys():
                if nb_importances[nb] <= lowest_importance and  nbs[nb] > highest_score:
                    highest_score = nbs[nb]
                    idx_to_drop = nb
                    lowest_importance = nb_importances[nb]
            if idx_to_drop ==-1:
                break
            new_df.drop(idx_to_drop,inplace=True)


        new_df.to_crs(4326, inplace=True)

        return new_df