import numpy as np
import shapely
from shapely import get_coordinates, reverse, LineString


class MultiLineToPolygon:
    def __init__(self, _):
        pass

    def process(self, frame):
        new_df = frame.copy()
        new_df = frame.iloc[0:0]


        indices_dict = {}

        def get_random_new():
            for k,v  in enumerate(frame.iloc):
                if k not in indices_dict:
                    return k,v
            return None, None
        cursor = None

        def get_neighbour(pt):
            for k,v  in enumerate(frame.iloc):
                if k not in indices_dict:
                    if get_coordinates(v.geometry)[0][0] == pt[0] and get_coordinates(v.geometry)[0][1] == pt[1]:
                        return k, v.geometry
                    if get_coordinates(v.geometry)[-1][0] == pt[0] and get_coordinates(v.geometry)[-1][1] == pt[1]:
                        return k, reverse(v.geometry)
            return None
        loops = []

        current_loop = []
        end_point = None

        while True:
            if cursor is None:
                k, pt = get_random_new()
                if pt is None:
                    break
                indices_dict[k] = pt
                current_loop = get_coordinates(pt.geometry)
                cursor = current_loop[0]
                end_point = current_loop[-1]

            i, nb = get_neighbour(cursor)
            if i is None:
                print("ERROR")
                loops.append({
                    "name":"A",
                    "loop": current_loop
                })

                cursor = None
            else:
                current_loop = np.append(current_loop, get_coordinates(nb), axis=0)
                indices_dict[i] = nb
                cursor = current_loop[-1]
                if cursor[0] == end_point[0] and cursor[1] == end_point[1]:
                    loops.append({
                        "name": "A",
                        "loop": current_loop
                    })
                    cursor = None

        for loop in loops:
            poly = shapely.Polygon( loop.get("loop"))
            new_df.loc[len(new_df)] = {'name': loop["name"], "geometry": poly}


        return new_df
