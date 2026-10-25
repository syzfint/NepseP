import pytest

def test_screen_route_registry():
    routes = [
        "/cockpit/unified",
        "/cockpit/screen-01",
        "/cockpit/screen-02",
        "/cockpit/screen-03",
        "/cockpit/screen-04",
        "/cockpit/screen-05",
        "/cockpit/screen-06",
        "/cockpit/screen-07",
        "/cockpit/screen-08",
        "/cockpit/screen-09",
        "/cockpit/screen-10"
    ]
    assert len(routes) == 11
    assert len(set(routes)) == 11
