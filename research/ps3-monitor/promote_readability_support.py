#!/usr/bin/env python3
"""Record supporting functions recovered while expanding packet semantic islands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PS3_LINKED: list[dict[str, Any]] = [
    {
        "role": "Framework UI-module accessor",
        "ps3Address": "0x00017A78",
        "ps3Name": "Client::System::Framework::Framework::GetUIModule",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00017A78",
        "windowsAddress": "0x140013960",
        "windowsName": "Client__System__Framework__Framework__GetUIModule",
        "confidence": "high",
        "evidence": [
            "The PS3 DWARF function and Windows function are one-load accessors returning the UI-module pointer from the Framework object; the member offset changes from PS3 +0x1F20 to Windows +0x2C00.",
            "Both packet dispatchers call this accessor before the same UI command-interface paths, including ChatToChannel and logout-countdown cases.",
        ],
    },
    {
        "role": "EventFramework singleton accessor",
        "ps3Address": "0x00A516F4",
        "ps3Name": "Client::Game::Event::EventFramework::GetInstance",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00A516F4",
        "windowsAddress": "0x1406044E0",
        "windowsName": "Client__Game__Event__EventFramework__GetInstance",
        "confidence": "high",
        "evidence": [
            "The PS3 DWARF function and Windows function both return the process-wide EventFramework singleton.",
            "Confirmed quest, leve, daily-quest, repeat-flag, and instance-content packet handlers obtain their EventFramework receiver through this function.",
        ],
    },
    {
        "role": "InfoModule indexed proxy accessor",
        "ps3Address": "0x0024059C",
        "ps3Name": "Client::UI::Info::InfoModule::GetProxy",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:0024059C",
        "windowsAddress": "0x140032C30",
        "windowsName": "Client__UI__Info__InfoModule__GetProxy",
        "confidence": "high",
        "evidence": [
            "Both functions return the pointer at proxy-array index proxyId; PS3 checks the 17-entry bound and null result while Windows performs the same indexed load from receiver +0x08.",
            "Eight matched retainer and market handlers obtain the receiver through the UIModule InfoModule virtual accessor and use the same fixed proxy IDs; ID 9 feeds the ItemSearch RequestResult path in both builds.",
        ],
    },
    {
        "role": "TreasureManager entity-ID lookup",
        "ps3Address": "0x0098829C",
        "ps3Name": "Client::Game::Object::TreasureManager::GetTreasureFromEntityId",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:0098829C",
        "windowsAddress": "0x1405428B0",
        "windowsName": "Client__Game__Object__TreasureManager__GetTreasureFromEntityId",
        "confidence": "high",
        "evidence": [
            "Both functions scan the static-object table and then the stand-object table, compare entity IDs, and require virtual object kind 4 before returning the object; Windows expands the second bound from 60 to 140.",
            "The matched OpenTreasure, TreasureOpenRight, and LootItems handlers call this lookup with the packet treasure entity ID, while the Windows TreasureFadeOut path uses the dispatcher target actor ID.",
        ],
    },
    {
        "role": "EventFramework quests-initialized notification",
        "ps3Address": "0x00A5A250",
        "ps3Name": "Client::Game::Event::EventFramework::OnQuestsInitialized",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00A5A250",
        "windowsAddress": "0x14066B1C0",
        "windowsName": "Client__Game__Event__EventFramework__OnQuestsInitialized",
        "confidence": "high",
        "evidence": [
            "The matched ReceiveQuests handlers call these methods after populating the full quest-work array.",
            "The Windows target is a one-caller thunk to the common event-handler initialization routine, matching the PS3 method's initialization role.",
        ],
    },
    {
        "role": "EventFramework quest synchronization",
        "ps3Address": "0x00A5A474",
        "ps3Name": "Client::Game::Event::EventFramework::OnSyncQuest",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00A5A474",
        "windowsAddress": "0x1406A8970",
        "windowsName": "Client__Game__Event__EventFramework__OnSyncQuest",
        "confidence": "high",
        "evidence": [
            "Matched ReceiveQuest and ReceiveQuests handlers pass the new work, old work, and work index in the same order in both builds.",
            "Both methods read quest ID at work +0x08 and sequence at +0x0A, resolve the corresponding quest event handler, and propagate sequence/work changes.",
        ],
    },
    {
        "role": "EventFramework quest-complete-flags initialization",
        "ps3Address": "0x00A5A630",
        "ps3Name": "Client::Game::Event::EventFramework::OnQuestCompleteFlagsInitialized",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00A5A630",
        "windowsAddress": "0x14066B230",
        "windowsName": "Client__Game__Event__EventFramework__OnQuestCompleteFlagsInitialized",
        "confidence": "high",
        "evidence": [
            "The matched ReceiveQuestCompleteFlags handlers call these methods only after accepting and copying the complete flag array.",
            "The Windows target is a dedicated one-caller thunk to the same initialization implementation used by related quest-state initialization notifications.",
        ],
    },
    {
        "role": "EventFramework quest-completion synchronization",
        "ps3Address": "0x00A5A6A4",
        "ps3Name": "Client::Game::Event::EventFramework::OnSyncQuestComplete",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00A5A6A4",
        "windowsAddress": "0x14066B240",
        "windowsName": "Client__Game__Event__EventFramework__OnSyncQuestComplete",
        "confidence": "high",
        "evidence": [
            "The matched ReceiveQuestCompleteFlag handlers pass quest ID, completed, and update to these methods after performing identical bitset mutation.",
            "When update is set, both methods issue quest-update type 1 for the quest ID with work index 30 and no handler.",
        ],
    },
    {
        "role": "EventFramework daily-quests initialization",
        "ps3Address": "0x00A5A6E8",
        "ps3Name": "Client::Game::Event::EventFramework::OnDailyQuestsInitialized",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00A5A6E8",
        "windowsAddress": "0x14066B280",
        "windowsName": "Client__Game__Event__EventFramework__OnDailyQuestsInitialized",
        "confidence": "high",
        "evidence": [
            "The matched ReceiveDailyQuests handlers call these methods when the daily-quest state transitions to initialized.",
            "The Windows target is a dedicated one-caller thunk to the common event-handler initialization routine used by the corresponding PS3 method.",
        ],
    },
    {
        "role": "EventFramework daily-quests synchronization",
        "ps3Address": "0x00A5A75C",
        "ps3Name": "Client::Game::Event::EventFramework::OnSyncDailyQuests",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00A5A75C",
        "windowsAddress": "0x140657ED0",
        "windowsName": "Client__Game__Event__EventFramework__OnSyncDailyQuests",
        "confidence": "high",
        "evidence": [
            "The matched bulk ReceiveDailyQuests handlers pass the update boolean to these methods after copying all daily-quest records.",
            "Both methods gate downstream event-handler refresh work on that update boolean; the Windows implementation expands the notification work performed in 3.x.",
        ],
    },
    {
        "role": "EventFramework daily-quest synchronization",
        "ps3Address": "0x00A5A79C",
        "ps3Name": "Client::Game::Event::EventFramework::OnSyncDailyQuest",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00A5A79C",
        "windowsAddress": "0x140657FD0",
        "windowsName": "Client__Game__Event__EventFramework__OnSyncDailyQuest",
        "confidence": "high",
        "evidence": [
            "The matched singular ReceiveDailyQuest handlers pass the update boolean here after validating the slot and copying one record.",
            "Both methods gate downstream event-handler refresh work on that update boolean; the distinct singular call path separates it from OnSyncDailyQuests.",
        ],
    },
    {
        "role": "EventFramework repeat-flags initialization",
        "ps3Address": "0x00A5A7DC",
        "ps3Name": "Client::Game::Event::EventFramework::OnQuestRepeatFlagsInitialized",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00A5A7DC",
        "windowsAddress": "0x14066B290",
        "windowsName": "Client__Game__Event__EventFramework__OnQuestRepeatFlagsInitialized",
        "confidence": "high",
        "evidence": [
            "The matched ReceiveQuestRepeatFlags handlers call these methods only on the first accepted repeat-mask initialization.",
            "The Windows target is a dedicated one-caller thunk to the common event-handler initialization implementation.",
        ],
    },
    {
        "role": "EventFramework repeat-flags synchronization",
        "ps3Address": "0x00A5A850",
        "ps3Name": "Client::Game::Event::EventFramework::OnSyncQuestRepeatFlags",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00A5A850",
        "windowsAddress": "0x14066B2A0",
        "windowsName": "Client__Game__Event__EventFramework__OnSyncQuestRepeatFlags",
        "confidence": "high",
        "evidence": [
            "The matched ReceiveQuestRepeatFlags handlers pass the update boolean here after copying the repeat mask.",
            "When update is set, both methods iterate repeat-flag indices 0 through 8, resolve quest metadata, and refresh the associated event handlers.",
        ],
    },
    {
        "role": "EventFramework singular repeat-flag synchronization",
        "ps3Address": "0x00A5A8D0",
        "ps3Name": "Client::Game::Event::EventFramework::OnSyncQuestRepeatFlag",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00A5A8D0",
        "windowsAddress": "0x14065FD10",
        "windowsName": "Client__Game__Event__EventFramework__OnSyncQuestRepeatFlag",
        "confidence": "high",
        "evidence": [
            "Both methods accept flag ID, value, and update, and only act when update is set.",
            "Both resolve repeat-quest metadata by flag ID and refresh the event handler associated with the nonzero quest ID.",
        ],
    },
    {
        "role": "SyncTag singular repeat-flag receiver",
        "ps3Address": "0x00AE9490",
        "ps3Name": "Client::Game::Network::SyncTagPacket::ReceiveQuestRepeatFlag",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00AE9490",
        "windowsAddress": "0x140CC2630",
        "windowsName": "Client__Game__Network__SyncTagPacket__ReceiveQuestRepeatFlag",
        "confidence": "high",
        "evidence": [
            "Both functions update the one-byte repeat mask with 0x80 shifted by flagId & 7 and reject flag IDs whose byte index is nonzero.",
            "Both are reached from the matched Order handler and forward flag ID, value, and update to EventFramework::OnSyncQuestRepeatFlag.",
        ],
    },
    {
        "role": "EventFramework guildleves initialization",
        "ps3Address": "0x00A5A93C",
        "ps3Name": "Client::Game::Event::EventFramework::OnGuildlevesInitialized",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00A5A93C",
        "windowsAddress": "0x140604600",
        "windowsName": "Client__Game__Event__EventFramework__OnGuildlevesInitialized",
        "confidence": "high",
        "evidence": [
            "The matched ReceiveGuildleves handlers call these methods after populating the full leve-work array.",
            "The 3.x target is a dedicated one-caller no-op, establishing that this notification was retained but no longer performs the PS3 initialization work.",
        ],
    },
    {
        "role": "EventFramework guildleve synchronization",
        "ps3Address": "0x00A5A948",
        "ps3Name": "Client::Game::Event::EventFramework::OnSyncGuildleve",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00A5A948",
        "windowsAddress": "0x1406B4400",
        "windowsName": "Client__Game__Event__EventFramework__OnSyncGuildleve",
        "confidence": "high",
        "evidence": [
            "Matched ReceiveGuildleve and ReceiveGuildleves handlers pass new work, old work, and work index in the same order in both builds.",
            "Both methods compare leve ID at work +0x08 and synchronize the corresponding event-handler state; Windows validates a 16-entry work index.",
        ],
    },
    {
        "role": "EventFramework leve-complete-flags initialization",
        "ps3Address": "0x00A5ABB4",
        "ps3Name": "Client::Game::Event::EventFramework::OnLeveCompleteFlagsInitialized",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00A5ABB4",
        "windowsAddress": "0x140604610",
        "windowsName": "Client__Game__Event__EventFramework__OnLeveCompleteFlagsInitialized",
        "confidence": "high",
        "evidence": [
            "The matched ReceiveLeveCompleteFlags handlers call these methods only after accepting and copying the complete leve flag array.",
            "The 3.x target is a dedicated one-caller no-op, preserving the source-level notification boundary without PS3's former side effects.",
        ],
    },
    {
        "role": "EventFramework leve-completion synchronization",
        "ps3Address": "0x00A5AC00",
        "ps3Name": "Client::Game::Event::EventFramework::OnSyncLeveComplete",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00A5AC00",
        "windowsAddress": "0x140604620",
        "windowsName": "Client__Game__Event__EventFramework__OnSyncLeveComplete",
        "confidence": "high",
        "evidence": [
            "The matched ReceiveLeveCompleteFlag handlers call these methods with the same leve-completion bit index after identical bitset mutation.",
            "The 3.x target is a dedicated one-caller no-op, showing the notification was compiled out while its call boundary remained.",
        ],
    },
    {
        "role": "InfoProxyItemSearch request result",
        "ps3Address": "0x002C5C54",
        "ps3Name": "Client::UI::Info::InfoProxyItemSearch::RequestResult",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:002C5C54",
        "windowsAddress": "0x14004C3F0",
        "windowsName": "Client__UI__Info__InfoProxyItemSearch__RequestResult",
        "confidence": "high",
        "evidence": [
            "The matched ItemSearchResult handlers obtain InfoProxy ID 9 and pass catalog ID, subquality, materia count, count, and result in the same order.",
            "Both methods branch on the result code and drive the ItemSearch UI/agent request-completion path.",
        ],
    },
    {
        "role": "InfoProxyItemSearch retainer-list update",
        "ps3Address": "0x002C694C",
        "ps3Name": "Client::UI::Info::InfoProxyItemSearch::SetRetainerData(Client::Network::Protocol::Zone::ZoneProtoDownRetainerData const*,unsigned int)",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:002C694C",
        "windowsAddress": "0x140037CA0",
        "windowsName": "Client__UI__Info__InfoProxyItemSearch__SetRetainerDataList",
        "confidence": "high",
        "evidence": [
            "The matched GetRetainerListResult handlers call these methods through InfoProxy ID 9 with the record array and count.",
            "Both accept at most eight records, clear the existing retainer list, copy nonzero IDs plus market flags, tax data, and names, and increment the stored count.",
        ],
    },
    {
        "role": "InfoProxyItemSearch market-buy result",
        "ps3Address": "0x002C6594",
        "ps3Name": "Client::UI::Info::InfoProxyItemSearch::MarketBuyResult",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:002C6594",
        "windowsAddress": "0x14004C710",
        "windowsName": "Client__UI__Info__InfoProxyItemSearch__MarketBuyResult",
        "confidence": "high",
        "evidence": [
            "The matched BuyMarketRetainerResult handlers call these methods through InfoProxy ID 9 with catalog ID and result.",
            "Both resolve AgentItemSearch ID 61, complete the buy operation, and branch over the same market-result family.",
        ],
    },
    {
        "role": "InfoProxyItemSearch market callback",
        "ps3Address": "0x002C6588",
        "ps3Name": "Client::UI::Info::InfoProxyItemSearch::MarketCallback",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:002C6588",
        "windowsAddress": "0x140037B00",
        "windowsName": "Client__UI__Info__InfoProxyItemSearch__MarketCallback",
        "confidence": "high",
        "evidence": [
            "The matched MarketStorageUpdate handlers call these dedicated methods through InfoProxy ID 9 with the callback type.",
            "Both build targets implement the method as an empty no-op, and the Windows target has exactly this one caller.",
        ],
    },
    {
        "role": "InfoProxyItemSearch item-history update",
        "ps3Address": "0x002C6448",
        "ps3Name": "Client::UI::Info::InfoProxyItemSearch::SetItemHistory",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:002C6448",
        "windowsAddress": "0x14004C6C0",
        "windowsName": "Client__UI__Info__InfoProxyItemSearch__SetItemHistory",
        "confidence": "high",
        "evidence": [
            "The matched GetItemHistoryResult handlers call these methods through InfoProxy ID 9 with history records and count.",
            "Both enforce count <= 20, call the shared internal history copier in item-history mode, resolve AgentItemSearch ID 61, and refresh history dates.",
        ],
    },
    {
        "role": "InfoProxyItemSearch retainer-sales-history update",
        "ps3Address": "0x002C64C8",
        "ps3Name": "Client::UI::Info::InfoProxyItemSearch::SetRetainerSalesHistory",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:002C64C8",
        "windowsAddress": "0x140037A80",
        "windowsName": "Client__UI__Info__InfoProxyItemSearch__SetRetainerSalesHistory",
        "confidence": "high",
        "evidence": [
            "The matched GetRetainerSalesHistoryResult handlers call these methods through InfoProxy ID 9 with history records and count.",
            "Both enforce count <= 20, use retainer-history mode, refresh AgentItemSearch ID 61, and notify AgentRetainer ID 56.",
        ],
    },
    {
        "role": "InfoProxyItemSearch singular retainer update",
        "ps3Address": "0x002C6A58",
        "ps3Name": "Client::UI::Info::InfoProxyItemSearch::SetRetainerData(unsigned long long,unsigned char,unsigned char)",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:002C6A58",
        "windowsAddress": "0x140037DB0",
        "windowsName": "Client__UI__Info__InfoProxyItemSearch__SetRetainerData",
        "confidence": "high",
        "evidence": [
            "The matched MarketRetainerUpdate handlers call these methods through InfoProxy ID 9 with retainer ID, register-market flag, and is-market flag.",
            "Both scan at most eight retained records for the ID, update the two flags, resolve AgentRetainer ID 56, and notify the agent.",
        ],
    },
    {
        "role": "InfoModule one-argument error printer",
        "ps3Address": "0x002B4898",
        "ps3Name": "Client::UI::Info::InfoModule::PrintError(unsigned int)",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:002B4898",
        "windowsAddress": "0x140046470",
        "windowsName": "Client__UI__Info__InfoModule__PrintError",
        "confidence": "high",
        "evidence": [
            "Matched information-packet handlers call these methods on the same InfoModule receiver with the result/error code, including ItemSearchResult and MarketRetainerUpdate.",
            "Both resolve the UIModule log interface and emit the resulting message ID; the Windows function is shared by seventeen information-result paths.",
        ],
    },
    {
        "role": "InfoModule two-argument error printer",
        "ps3Address": "0x002B4940",
        "ps3Name": "Client::UI::Info::InfoModule::PrintError(unsigned int,int)",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:002B4940",
        "windowsAddress": "0x1400464C0",
        "windowsName": "Client__UI__Info__InfoModule__PrintErrorWithParam",
        "confidence": "high",
        "evidence": [
            "The matched BuyMarketRetainerResult handlers uniquely call these methods on InfoModule with result and quantity parameters.",
            "Both resolve the UIModule log interface and emit the message ID with one integer parameter.",
        ],
    },
]

WINDOWS_SUPPORTING: list[dict[str, Any]] = [
    {
        "windowsAddress": "0x140CC7090",
        "windowsName": "Client__Game__Network__Packet__ReceiveRetainerPackets_Impl",
        "roles": ["RetainerList", "RetainerData"],
        "confidence": "high",
        "mappingKind": "windows-supporting",
        "evidence": [
            "The confirmed RetainerList/RetainerData wrapper calls only this implementation.",
            "This function switches on 0x01AA/0x01AB, finds or creates the owner-context accumulator, copies retainer records, and commits the completed group.",
        ],
    },
    {
        "windowsAddress": "0x140CC7200",
        "windowsName": "Client__Game__Network__Packet__ReceiveMarketPricePackets_Impl",
        "roles": ["MarketPriceHeader", "MarketPrice"],
        "confidence": "high",
        "mappingKind": "windows-supporting",
        "evidence": [
            "The confirmed MarketPriceHeader/MarketPrice wrapper calls only this implementation.",
            "This function switches on 0x01AC/0x01AD, assembles market-price records by owner context, and commits the completed group.",
        ],
    },
    {
        "windowsAddress": "0x140CC7330",
        "windowsName": "Client__Game__Network__Packet__ReceiveItemOperationPackets_Impl",
        "roles": ["ItemOperationBatch", "ItemOperation"],
        "confidence": "high",
        "mappingKind": "windows-supporting",
        "evidence": [
            "The confirmed ItemOperationBatch/ItemOperation wrapper calls only this implementation.",
            "This function switches on 0x01B1/0x01B2, copies operation records into an owner-context accumulator, and commits the completed batch.",
        ],
    },
    {
        "windowsAddress": "0x140CC8870",
        "windowsName": "Client__Game__Network__Packet__ReceiveItemStoragePackets_Impl",
        "roles": ["NormalItem", "ItemSize", "GilItem", "AliasItem"],
        "confidence": "high",
        "mappingKind": "windows-supporting",
        "evidence": [
            "The confirmed item-storage wrapper calls only this implementation.",
            "This function switches on 0x01AF/0x01B0/0x01B3/0x01B7, processes item or size records, and commits complete storage state.",
        ],
    },
    {
        "windowsAddress": "0x140CC67D0",
        "windowsName": "Win335_ItemPacketAssembler__AcquireContext",
        "roles": ["retainer/market/item fragment assembly"],
        "confidence": "high",
        "mappingKind": "windows-supporting",
        "evidence": [
            "All four typed retainer/market/item implementations call this helper after failing to find an active context with the same target actor ID.",
            "It removes one context from the free list, appends it to the active list, stores the target actor ID, clears the fragment list/count, and sets expected count to -1.",
        ],
    },
    {
        "windowsAddress": "0x140CC2070",
        "windowsName": "Win335_ItemPacketAssembler__AppendFragment",
        "roles": ["retainer/market/item fragment assembly"],
        "confidence": "high",
        "mappingKind": "windows-supporting",
        "evidence": [
            "All four typed implementations use this helper to consume a free fragment node and append it to an assembly context.",
            "The helper copies exactly 0x50 payload bytes, links the node at context +0x18/+0x20, and increments the received-fragment count at +0x28.",
        ],
    },
    {
        "windowsAddress": "0x140CC6860",
        "windowsName": "Win335_ItemPacketAssembler__ReleaseContext",
        "roles": ["retainer/market/item fragment assembly"],
        "confidence": "high",
        "mappingKind": "windows-supporting",
        "evidence": [
            "All four typed implementations call this helper after committing or abandoning an assembly context.",
            "It returns every fragment node to the free-fragment list, unlinks the context from the active list, and returns it to the free-context list.",
        ],
    },
]


def write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(value, output, indent=2)
        output.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--matches", type=Path, default=Path(__file__).with_name("packet_matches.json")
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    mapping = json.loads(args.matches.read_text(encoding="utf-8"))
    existing_ps3 = {
        int(item["windowsAddress"], 16) for item in mapping.get("supportingFunctions", [])
    }
    existing_windows = {
        int(item["windowsAddress"], 16)
        for item in mapping.get("windowsSupportingFunctions", [])
    }
    ps3_additions = [
        item for item in PS3_LINKED if int(item["windowsAddress"], 16) not in existing_ps3
    ]
    windows_additions = [
        item
        for item in WINDOWS_SUPPORTING
        if int(item["windowsAddress"], 16) not in existing_windows
    ]
    print(
        json.dumps(
            {
                "ps3LinkedPromotable": len(ps3_additions),
                "windowsSupportingPromotable": len(windows_additions),
                "ps3Linked": ps3_additions,
                "windowsSupporting": windows_additions,
            },
            indent=2,
        )
    )
    if args.apply:
        mapping.setdefault("supportingFunctions", []).extend(ps3_additions)
        mapping["supportingFunctions"].sort(
            key=lambda item: int(item["windowsAddress"], 16)
        )
        mapping.setdefault("windowsSupportingFunctions", []).extend(windows_additions)
        mapping["windowsSupportingFunctions"].sort(
            key=lambda item: int(item["windowsAddress"], 16)
        )
        write_json(args.matches, mapping)


if __name__ == "__main__":
    main()
