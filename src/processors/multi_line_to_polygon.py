class MultiLineToPolygon:
    def __init__(self, _):
        pass

    def process(self, frame):
        def namefix(rw):
            return rw.get("name")
        frame['fixed_name'] = frame.apply(namefix, axis=1)

        grouped_frame = frame.dissolve(by='name',as_index=False)
        pols = grouped_frame.polygonize(node=True)
        while len(pols)> len(grouped_frame):
            grouped_frame.loc[len(grouped_frame)] = {'name':'ghost'}
        grouped_frame["geometry"] =pols
        return grouped_frame
