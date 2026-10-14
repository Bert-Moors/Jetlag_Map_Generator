class Rename:
    def __init__(self, config):
        self.columns = config.get('columns', {})

    def process(self, frame):
        return frame.rename(columns=self.columns)
