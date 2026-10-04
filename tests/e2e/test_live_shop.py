"""Gil shop commands beyond buy and sell: buyback, as a real client sends it.

A real client (capture of 2026-10-04) sends buyback as a five-result scene return
`[0, 3, index, count, unit price]`. The server used to treat it as "close", which
left the client stuck as occupied; it now gives the item back for the sale price
and re-lists the window.
"""
import pytest

from .support.catalog import load_shop_catalog
from .support.worker import Bot

pytestmark = pytest.mark.live


def _gil(state):
    return state["rewards"]["inventory"].get("2000:0", {}).get("count", 0)


def _bag_stacks(state, item):
    return {key: row for key, row in state["rewards"]["inventory"].items()
            if row["storage"] in range(4) and row["id"] == item}


def test_buyback_returns_the_sold_item(server, live_worker):
    path = server.profile.get("shop_catalog")
    assert path, "shop scenarios require profile.shop_catalog"
    catalog = load_shop_catalog(path)
    sale = catalog["starter_body_liquidation"]
    fixture = server.fresh_character(catalog["route"][-1])
    player = Bot(live_worker, "buyback-shopper")
    state = player.login_via_lobby(fixture["auth"], fixture["name"])
    work_index = state["rewards"]["level_by_index"].index(1)
    inventory = live_worker.snapshot(player.name)["rewards"]["inventory"]
    assert _gil(state) == 0 and not _bag_stacks(state, sale["item"])

    # A fresh character owns nothing to sell but its starter gear; unequip the body piece.
    gear_key = next(key for key, row in inventory.items() if row["storage"] == 1000 and row["id"] == sale["item"])
    gear_slot = inventory[gear_key]["slot"]
    destination = next(f"{bag}:{slot}" for bag in range(4) for slot in range(25) if f"{bag}:{slot}" not in inventory)
    storage, slot = map(int, destination.split(":"))
    player.request_item_unequip(gear_slot, storage, slot, sale["item"])
    # The acknowledgement is not the mutation; a fresh login shows where the piece went.
    player.logout(wait_server_close=True)
    player.close()
    player = Bot(live_worker, "buyback-shopper-selling")
    state = player.login_via_lobby(server.relogin(fixture), fixture["name"])
    state = live_worker.wait_state(player.name, lambda s: s["rewards"]["inventory_ready"], "inventory after relogin")
    assert state["rewards"]["inventory"].get(destination, {}).get("id") == sale["item"]

    player.open_gil_shop(catalog["shop"]["layout_id"], catalog["shop"]["event_id"])
    player.sell_shop_item(storage, slot, sale["item"])
    state = live_worker.wait_state(player.name, lambda s: _gil(s) == sale["gil"], "sale paid out")
    assert not _bag_stacks(state, sale["item"])

    # Buyback with nothing in the list first: must re-list, must not move gil.
    state = player.shop_buyback_request(catalog["shop"]["event_id"], index=5, count=1, price=sale["gil"])
    assert _gil(state) == sale["gil"]

    state = player.shop_buyback_request(catalog["shop"]["event_id"], index=0, count=1, price=sale["gil"])
    state = live_worker.wait_state(player.name, lambda s: _gil(s) == 0, "buyback charged the sale price")
    stacks = _bag_stacks(state, sale["item"])
    assert len(stacks) == 1 and next(iter(stacks.values()))["count"] == 1

    # The entry is gone from the list: buying it back again must not move anything.
    state = player.shop_buyback_request(catalog["shop"]["event_id"], index=0, count=1, price=sale["gil"])
    assert _gil(state) == 0 and len(_bag_stacks(state, sale["item"])) == 1

    # The window still works normally afterwards.
    player.exit_gil_shop(catalog["shop"]["event_id"])
    player.open_gil_shop(catalog["shop"]["layout_id"], catalog["shop"]["event_id"])
    player.exit_gil_shop(catalog["shop"]["event_id"])
    player.logout(wait_server_close=True)
    player.close()

    # The item survives a fresh login as an ordinary bag item.
    auth = server.relogin(fixture)
    reloaded = Bot(live_worker, "buyback-shopper-reloaded")
    state = reloaded.login_via_lobby(auth, fixture["name"])
    state = live_worker.wait_state(reloaded.name, lambda s: s["rewards"]["inventory_ready"],
                                   "inventory after fresh login")
    assert len(_bag_stacks(state, sale["item"])) == 1 and _gil(state) == 0
    reloaded.logout()
    reloaded.close()
