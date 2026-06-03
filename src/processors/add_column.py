class AddColumn:
    def __init__(self, config):
        self.columns = config.get('columns', {})

    def process(self, frame):
        for x in self.columns.keys():
            frame[x]= self.columns[x]
        return frame
