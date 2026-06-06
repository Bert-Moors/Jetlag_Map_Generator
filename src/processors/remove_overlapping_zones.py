from operator import index

from processors.hiding_zones import calculate_epsg


class RemoveOverlappingZones:
    def __init__(self, config):
        self.epsg = config.get("epsg",None)
        self.config = config.get("config", {})
        self.default_allowed_intrusion = config.get("allowed_intrusion", 80)
        self.default_importance = config.get("importance", 1)
        self.default_size = config.get("size", 500)


    def get_allowed_intrusion(self, typ):
        config_data = self.config.get(typ, {})
        return config_data.get("allowed_intrusion", self.default_allowed_intrusion)

    def get_size(self, typ):
        config_data = self.config.get(typ, {})
        return config_data.get("size", self.default_size)

    def get_max_size(self):
        res = self.default_size
        for x in self.config:
            res = max(self.config[x].get("size", 0), res)
        return res

    def get_importance(self, typ):
        config_data = self.config.get(typ, {})
        return config_data.get("importance", self.default_importance)

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
                if self.get_importance(x["type"]) > self.get_importance(y["type"]):
                    continue

                y_size = self.get_size(y["type"])
                x_size = self.get_size(x["type"])
                if "hiding_size" in x and x["hiding_size"]:
                    x_size = x["hiding_size"]
                if "hiding_size" in y and y["hiding_size"]:
                    y_size = y["hiding_size"]
                dist = x["geometry"].distance(y["geometry"])
                allowed_intrusion = self.get_allowed_intrusion(x["type"])
                score = x_size + y_size - (x_size*allowed_intrusion/100) - dist
                if x_size + y_size > (x_size*allowed_intrusion/100) + dist:
                    nb_importances[idx] = self.get_importance(x["type"])
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