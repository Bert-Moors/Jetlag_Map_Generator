import geopandas
import pandas as pd


# Take all stations with the same name together, and give them their centroid as location.
class AverageStationsSameName:
    def __init__(self, config):
        self.prefix_ignores = config.get("prefix_ignores", [])


    def process(self, frame: pd.DataFrame)->pd.DataFrame:
        new = geopandas.GeoDataFrame(columns=['name', 'geometry'])
        def namefix(rw):
            nm = rw.get('name','').upper()
            for ig in self.prefix_ignores:
                nm = nm.removeprefix(ig.upper())
            return nm
        frame['fixed_name'] = frame.apply(namefix, axis=1)
        bframe = frame.dissolve(by='fixed_name')

        for x in bframe.iloc:
            new.loc[len(new)]= {'name':x.get('name'), 'geometry': x["geometry"].centroid}
        return new