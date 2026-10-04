"""Gil shop commands the server does not implement must not close the window.

A real client (capture of 2026-10-04) sends buyback as a five-result scene return.
The server used to treat it as "close", which left the client stuck as occupied.
"""
import pytest

from .support.catalog import load_shop_catalog
from .support.worker import Bot

pytestmark = pytest.mark.live


def test_unknown_shop_command_keeps_shop_open(server, live_worker):
    path = server.profile.get("shop_catalog")
    assert path, "shop scenarios require profile.shop_catalog"
    catalog = load_shop_catalog(path)
    fixture = server.fresh_character(catalog["route"][-1])
    player = Bot(live_worker, "shopper")
    player.login_via_lobby(fixture["auth"], fixture["name"])

    player.open_gil_shop(catalog["shop"]["layout_id"], catalog["shop"]["event_id"])
    # Buyback with nothing sold: the server has nothing to give back, but it must
    # answer by re-listing, not by finishing the event.
    state = player.shop_buyback_request(catalog["shop"]["event_id"], index=0, count=1, price=catalog["sale"]["gil"])
    assert state["event_id"] == catalog["shop"]["event_id"]
    gil = state["rewards"]["inventory"].get("2000:0", {}).get("count", 0)
    assert gil == 0, "a phantom buyback must not move gil"

    # The window still works normally afterwards.
    player.exit_gil_shop(catalog["shop"]["event_id"])
    player.open_gil_shop(catalog["shop"]["layout_id"], catalog["shop"]["event_id"])
    player.exit_gil_shop(catalog["shop"]["event_id"])
    player.logout(wait_server_close=True)
    player.close()
