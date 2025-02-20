# Global variable to store the StationManager instance
station_manager = None

def set_station_manager(instance):
    global station_manager
    station_manager = instance

def get_station_manager():
    return station_manager 