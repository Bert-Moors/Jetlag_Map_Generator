from typing import List



def order_lines(lines: List) -> List[List]:
    shapes = []
    remaining = [line for line in lines if line]

    while remaining:
        points = remaining.pop(0)
        matched = True
        while points[0] != points[-1] and matched:
            matched = False
            for index, line in enumerate(remaining):
                if points[-1] == line[0]:
                    points += line[1:]
                elif points[-1] == line[-1]:
                    points += line[-2::-1]
                elif points[0] == line[-1]:
                    points = line[:-1] + points
                elif points[0] == line[0]:
                    points = line[:0:-1] + points
                else:
                    continue
                remaining.pop(index)
                matched = True
                break

        if points[0] == points[-1]:
            shapes.append(points)
    return shapes
