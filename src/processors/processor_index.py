from processors.average_stations_same_name import AverageStationsSameName


def get_processor(processor_name, config):
    mp = {
        "name_collapse": AverageStationsSameName
    }
    return mp[processor_name](config)