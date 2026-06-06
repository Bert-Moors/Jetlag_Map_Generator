from operator import index

from processors.hiding_zones import calculate_epsg


class RemoveByNames:
    def __init__(self, config):
        self.names_removed = config.get("name_list",None)

    def process(self, df):
        new_df = df.copy()
        new_df.reset_index(drop=True,inplace=True)
        for x in new_df.iterrows():
            if x[1]["name"] in self.names_removed:
                new_df.drop(x[0],inplace=True)

        return new_df