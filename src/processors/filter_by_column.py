class FilterByColumn:
    def __init__(self, config):
        self.filters = config.get("columns")
        if not self.filters:
            column = config.get("column")
            values = config.get("values", config.get("value"))
            self.filters = {column: values} if column else {}

    def process(self, frame):
        filtered = frame.copy()
        for column, values in self.filters.items():
            if column not in filtered.columns:
                return filtered.iloc[0:0]
            if isinstance(values, list | tuple | set):
                filtered = filtered[filtered[column].isin(values)]
            else:
                filtered = filtered[filtered[column] == values]
        return filtered.reset_index(drop=True)
