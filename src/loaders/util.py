from typing import List



def order_lines(lines: List) -> List[List]:
    shapes = []
    points = []
    if len(lines) == 0:
        return shapes

    for index, line in enumerate(lines):
        if not points:
            if index + 1 < len(lines):
                # there is a next line
                if line[-1] == lines[index+1][0] or line[-1] == lines[index+1][-1]:
                    points += line
                if line[0] == lines[index+1][0] or line[0] == lines[index+1][-1]:
                    points += line[::-1]
            else:
                # no next line, just add line as-is
                points += line
        else:
            # check if the last point in points is the same as the start of the current line
            if points[len(points) - 1] == line[0]:
                points += line[1:]
            elif points[len(points) - 1] == line[-1]:
                points += line[::-1]

        # if first and last point are the same add points to shapes and clear out points
        if points[0] == points[-1]:
            shapes.append(points)
            points = []
    return shapes

    for index, line in enumerate(lines):
        ## if points is currently empty check if the first line needs to be added in reverse or not
        if len(lines) < index+1:
            print("HI")
        if not points:
            if line[-1] == lines[index+1][0] or line[-1] == lines[index+1][-1]:
                points += line
            if line[0] == lines[index +1][0] or line[0] == lines[index +1][-1]:
                points += line[::-1]
        ## check if the last point in points is the same as the start of the current line
        ## if so add line to points if not add line but in reverse
        elif points[len(points) - 1] == line[0]:
            points += line[1:]
        elif points[len(points) - 1] == line[-1]:
            points += line[::-1]

        ## if first and last point are the same add points to shapes and clear out points
        if points[0] == points[-1]:
            shapes.append(points)
            points = []
    return shapes