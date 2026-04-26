class HidingZones:
    def __init__(self, config):
        self.size = config.get('size',.25)
        self.epsg = config.get('epsg',32531)

    def process(self, df):
        new_df = df.copy()
        new_df.set_crs(4326,inplace=True)
        new_df.to_crs(self.epsg, inplace=True)

        new_df['geometry'] = new_df['geometry'].buffer(distance=self.size)
        new_df.to_crs(4326,inplace=True)
        return new_df