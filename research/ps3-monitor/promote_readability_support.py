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
    {
        "role": "InfoProxyItemSearch page-record append",
        "ps3Address": "0x002C54E8",
        "ps3Name": "Client::UI::Info::InfoProxyItemSearch::Add",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:002C54E8",
        "windowsAddress": "0x14004C090",
        "windowsName": "Client__UI__Info__InfoProxyItemSearch__Add",
        "confidence": "high",
        "evidence": [
            "The methods occupy the Add slot at vtable +0x08 in both class vtables and are invoked from the matched AddPage implementations with a count of ten.",
            "Both append market-search records to a counted result array, clamp materia count to five, and update the same ItemSearch UI arrays.",
        ],
    },
    {
        "role": "InfoProxyItemSearch page-record subtraction",
        "ps3Address": "0x002C5A44",
        "ps3Name": "Client::UI::Info::InfoProxyItemSearch::Sub",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:002C5A44",
        "windowsAddress": "0x140037740",
        "windowsName": "Client__UI__Info__InfoProxyItemSearch__Sub",
        "confidence": "high",
        "evidence": [
            "The methods occupy the Sub slot immediately after Add in the independently recovered PS3 and Windows class vtables.",
            "Both build targets implement the method as an empty no-op.",
        ],
    },
    {
        "role": "InfoProxyItemSearch result clear",
        "ps3Address": "0x002C5A50",
        "ps3Name": "Client::UI::Info::InfoProxyItemSearch::Clear",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:002C5A50",
        "windowsAddress": "0x140037750",
        "windowsName": "Client__UI__Info__InfoProxyItemSearch__Clear",
        "confidence": "high",
        "evidence": [
            "The methods occupy the Clear slot in both class vtables and are called by AddPage on page zero or request-key mismatch.",
            "Both consist of setting the result count member to zero; the member moves from the PS3 class layout to Windows +0x10.",
        ],
    },
    {
        "role": "InfoProxyItemSearch search request",
        "ps3Address": "0x002C5A64",
        "ps3Name": "Client::UI::Info::InfoProxyItemSearch::Request",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:002C5A64",
        "windowsAddress": "0x14004C210",
        "windowsName": "Client__UI__Info__InfoProxyItemSearch__Request",
        "confidence": "high",
        "evidence": [
            "The methods occupy the Request slot in both class vtables.",
            "Both obtain the network module and send Info packet 260 with catalog ID, subquality, and materia count from the proxy's request state.",
        ],
    },
    {
        "role": "InfoProxyItemSearch request finish",
        "ps3Address": "0x002C5AF8",
        "ps3Name": "Client::UI::Info::InfoProxyItemSearch::Finish",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:002C5AF8",
        "windowsAddress": "0x140037760",
        "windowsName": "Client__UI__Info__InfoProxyItemSearch__Finish",
        "confidence": "high",
        "evidence": [
            "The methods occupy the Finish slot in both class vtables and are invoked by AddPage after the final page.",
            "Both build targets implement the method as an empty no-op.",
        ],
    },
    {
        "role": "InfoProxyItemSearch page dispatcher",
        "ps3Address": "0x002C5B04",
        "ps3Name": "Client::UI::Info::InfoProxyItemSearch::AddPage",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:002C5B04",
        "windowsAddress": "0x14004C2B0",
        "windowsName": "Client__UI__Info__InfoProxyItemSearch__AddPage",
        "confidence": "high",
        "evidence": [
            "GetItemSearchListResult invokes the method through InfoProxy ID 9; the recovered Windows class vtable identifies its target at slot +0x50.",
            "Both compare request key at packet +0x462, clear on page zero or mismatch, append ten records when enabled, send continuation packet 261 from bytes +0x460/+0x462, and finish when no next page remains.",
        ],
    },
    {
        "role": "InfoProxyItemSearch internal history copier",
        "ps3Address": "0x002C605C",
        "ps3Name": "Client::UI::Info::InfoProxyItemSearch::_SetItemHistory",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:002C605C",
        "windowsAddress": "0x140037870",
        "windowsName": "Client__UI__Info__InfoProxyItemSearch__SetItemHistory_Impl",
        "confidence": "high",
        "evidence": [
            "In both builds this helper has exactly the SetItemHistory and SetRetainerSalesHistory methods as semantic callers.",
            "Both copy a bounded history-record array into proxy storage and use the final boolean to distinguish item-history from retainer-history mode.",
        ],
    },
    {
        "role": "InfoProxyInterface result count",
        "ps3Address": "0x01364E34",
        "ps3Name": "Client::UI::Info::InfoProxyInterface::Count",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:01364E34",
        "windowsAddress": "0x14007C740",
        "windowsName": "Client__UI__Info__InfoProxyInterface__Count",
        "confidence": "high",
        "evidence": [
            "The function occupies the Count slot in the PS3 InfoProxyItemSearch vtable and the corresponding +0x38 slot in the Windows vtable after the Windows-only intervening base slot.",
            "Both are one-load accessors returning the proxy result count; Windows reads the independently confirmed member at +0x10.",
        ],
    },
    {
        "role": "Treasure fade-out transition",
        "ps3Address": "0x00986DE0",
        "ps3Name": "Client::Game::Object::Treasure::FadeOut",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00986DE0",
        "windowsAddress": "0x1409EC240",
        "windowsName": "Client__Game__Object__Treasure__FadeOut",
        "confidence": "high",
        "evidence": [
            "The PS3 method is called by the PS3 treasure fade path and the Windows method is the sole target after the confirmed TreasureFadeOut lookup.",
            "Both set graphical state to opened/fading state 3 and set the fade-out byte; Windows confirms offsets +0x190 and +0x1F0.",
        ],
    },
    {
        "role": "Treasure maximum-timer update",
        "ps3Address": "0x00987260",
        "ps3Name": "Client::Game::Object::Treasure::SetMaxTimer",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00987260",
        "windowsAddress": "0x1409ED5D0",
        "windowsName": "Client__Game__Object__Treasure__SetMaxTimer",
        "confidence": "high",
        "evidence": [
            "Matched CreateTreasure and TreasureOpenRight handlers call these methods with the packet maximum timer.",
            "Both store maxTimer and clamp the current timer to the lesser value; Windows confirms timer +0x194 and maxTimer +0x198.",
        ],
    },
    {
        "role": "Treasure item-slot accessor",
        "ps3Address": "0x00987290",
        "ps3Name": "Client::Game::Object::Treasure::GetItemSlot",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00987290",
        "windowsAddress": "0x1409EBEF0",
        "windowsName": "Client__Game__Object__Treasure__GetItemSlot",
        "confidence": "high",
        "evidence": [
            "Matched CreateTreasure handlers iterate the packet catalogue IDs and call these accessors with the same slot index.",
            "Both return a four-byte item slot from a 16-entry array; Windows computes self +0x1A0 + 4*index while relying on the caller's proven bound.",
        ],
    },
    {
        "role": "Treasure open transition",
        "ps3Address": "0x00987344",
        "ps3Name": "Client::Game::Object::Treasure::Open()",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00987344",
        "windowsAddress": "0x1409EC030",
        "windowsName": "Client__Game__Object__Treasure__Open",
        "confidence": "high",
        "evidence": [
            "Matched CreateTreasure handlers call these no-argument methods when the creation payload says the treasure is already opened.",
            "Both guard on isOpened, set it, play shared-group timeline zero when available, and set graphical state to opening state 1.",
        ],
    },
    {
        "role": "Treasure timed open transition",
        "ps3Address": "0x009873A8",
        "ps3Name": "Client::Game::Object::Treasure::Open(float,float,float)",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:009873A8",
        "windowsAddress": "0x1409EC080",
        "windowsName": "Client__Game__Object__Treasure__OpenWithTimers",
        "confidence": "high",
        "evidence": [
            "Matched OpenTreasure handlers resolve the treasure and pass timer, maximum timer, and maximum loot timer to these methods.",
            "Both guard on isOpened, store all three timers, play shared-group timeline zero when available, and enter graphical opening state 1.",
        ],
    },
    {
        "role": "StaticObjectManager indexed lookup",
        "ps3Address": "0x00986098",
        "ps3Name": "Client::Game::Object::StaticObjectManager::GetObject",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00986098",
        "windowsAddress": "0x1409EBA30",
        "windowsName": "Client__Game__Object__StaticObjectManager__GetObject",
        "confidence": "high",
        "evidence": [
            "Both accessors reject indices above 39 and return the pointer from the manager's 40-entry object array.",
            "The confirmed TreasureManager lookup and CreateTreasure paths use the accessor identically in both builds.",
        ],
    },
    {
        "role": "StandObjectManager indexed lookup",
        "ps3Address": "0x0098377C",
        "ps3Name": "Client::Game::Object::StandObjectManager::GetObject",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:0098377C",
        "windowsAddress": "0x140DC6040",
        "windowsName": "Client__Game__Object__StandObjectManager__GetObject",
        "confidence": "high",
        "evidence": [
            "Both are the second indexed object-table accessor used by TreasureManager::GetTreasureFromEntityId after the static-object scan.",
            "Windows expands the PS3 60-entry direct array to 140 logical entries and adds indirection handling, but preserves indexed GameObject lookup semantics.",
        ],
    },
    {
        "role": "EventHandlerModule typed initialization",
        "ps3Address": "0x0099D458",
        "ps3Name": "Client::Game::Event::EventHandlerModule::InitializeEventHandlers(unsigned short)",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:0099D458",
        "windowsAddress": "0x14065F1E0",
        "windowsName": "Client__Game__Event__EventHandlerModule__InitializeEventHandlers",
        "confidence": "high",
        "evidence": [
            "The PS3 scalar overload forwards one handler type to the array implementation; the optimized Windows function directly iterates the same event-handler tree for one handler type.",
            "Both compare each handler's type and invoke its initialization virtual method; the confirmed quest-initialization path passes handler type 1.",
        ],
    },
    {
        "role": "EventFramework quest-update core",
        "ps3Address": "0x00A5A2C4",
        "ps3Name": "Client::Game::Event::EventFramework::onQuestUpdate",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00A5A2C4",
        "windowsAddress": "0x14065FF10",
        "windowsName": "Client__Game__Event__EventFramework__onQuestUpdate",
        "confidence": "high",
        "evidence": [
            "Confirmed OnSyncQuest and OnSyncQuestComplete methods call these functions with the same update type, quest ID, work index, and handler semantics.",
            "Both switch over quest-update types 0/1/2, update the corresponding event handlers, clear a quest marker for completion indices below 30, and notify the UI quest path.",
        ],
    },
    {
        "role": "EventHandlerModule handler lookup",
        "ps3Address": "0x009971A8",
        "ps3Name": "Client::Game::Event::EventHandlerModule::GetEventHandler",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:009971A8",
        "windowsAddress": "0x140656ED0",
        "windowsName": "Client__Game__Event__EventHandlerModule__GetEventHandler",
        "confidence": "high",
        "evidence": [
            "Confirmed OnSyncQuest methods in both builds resolve questId | 0x10000 through this accessor before notifying onQuestUpdate.",
            "The Windows implementation handles several singleton IDs and otherwise performs the same ordered event-handler tree lookup, returning the node's handler pointer or null.",
        ],
    },
    {
        "role": "EventHandlerModule typed visibility update",
        "ps3Address": "0x0099CF28",
        "ps3Name": "Client::Game::Event::EventHandlerModule::UpdateEventVisibility(unsigned short)",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:0099CF28",
        "windowsAddress": "0x14065EA80",
        "windowsName": "Client__Game__Event__EventHandlerModule__UpdateEventVisibility",
        "confidence": "high",
        "evidence": [
            "Both scalar methods iterate the event-handler tree, select handlers by the same 16-bit handler type, and invoke the update and visibility virtual boundaries.",
            "The matched onQuestUpdate path calls this method with handler type 26 after a type-0 quest update in both builds.",
        ],
    },
    {
        "role": "TreasureManager hunt reward presentation",
        "ps3Address": "0x0098957C",
        "ps3Name": "Client::Game::Object::TreasureManager::OnTreasureHuntReward",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:0098957C",
        "windowsAddress": "0x14054FE20",
        "windowsName": "Client__Game__Object__TreasureManager__OnTreasureHuntReward",
        "confidence": "high",
        "evidence": [
            "The matched TreasureHuntReward handlers forward rank, experience, money, item catalogue ID, and stack to these unique downstream methods; Windows adds an event-handler ID before the shared arguments.",
            "Both resolve the UI module, normalize rank identically, clear item ID when stack is zero, and open the treasure-hunt reward UI with the same reward values.",
        ],
    },
    {
        "role": "GameObject entity-ID setter",
        "ps3Address": "0x0097AED8",
        "ps3Name": "Client::Game::Object::GameObject::SetEntityId",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:0097AED8",
        "windowsAddress": "0x1409DE380",
        "windowsName": "Client__Game__Object__GameObject__SetEntityId",
        "confidence": "high",
        "evidence": [
            "Both compare and store the entity ID before notifying the global object manager of an entity-ID change.",
            "The confirmed CreateTreasure handlers call these setters with the packet entity ID after object creation.",
        ],
    },
    {
        "role": "GameObject layout-ID setter",
        "ps3Address": "0x0097AF28",
        "ps3Name": "Client::Game::Object::GameObject::SetLayoutId",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:0097AF28",
        "windowsAddress": "0x1409DE350",
        "windowsName": "Client__Game__Object__GameObject__SetLayoutId",
        "confidence": "high",
        "evidence": [
            "Both compare and store the layout ID before notifying the global object manager of a layout-ID change.",
            "The confirmed CreateTreasure handlers call these setters with the packet layout ID after object creation.",
        ],
    },
    {
        "role": "GameObject content-ID setter",
        "ps3Address": "0x0097DEF8",
        "ps3Name": "Client::Game::Object::GameObject::SetContentId",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:0097DEF8",
        "windowsAddress": "0x1409DE4B0",
        "windowsName": "Client__Game__Object__GameObject__SetContentId",
        "confidence": "high",
        "evidence": [
            "Both store the 32-bit content ID and mark object-state flags dirty.",
            "The confirmed CreateTreasure handlers call these setters with the packet content ID between timer and treasure metadata updates.",
        ],
    },
    {
        "role": "GameObject permission-invisibility setter",
        "ps3Address": "0x0097DF30",
        "ps3Name": "Client::Game::Object::GameObject::SetPermissionInvisibility",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:0097DF30",
        "windowsAddress": "0x1409DE4F0",
        "windowsName": "Client__Game__Object__GameObject__SetPermissionInvisibility",
        "confidence": "high",
        "evidence": [
            "Both store the one-byte permission-invisibility value and mark object-state flags dirty.",
            "The confirmed CreateTreasure handlers call these setters with the same packet field immediately after object lookup.",
        ],
    },
    {
        "role": "StaticObjectManager treasure creation",
        "ps3Address": "0x00986438",
        "ps3Name": "Client::Game::Object::StaticObjectManager::CreateTreasure",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00986438",
        "windowsAddress": "0x1409EE530",
        "windowsName": "Client__Game__Object__StaticObjectManager__CreateTreasure",
        "confidence": "high",
        "evidence": [
            "Both allocate or replace one of 40 indexed static-object slots, construct a Treasure in the object buffer, assign the slot-specific object ID, set the entity ID, run Treasure::Setup, notify the object manager, and return the slot index.",
            "The confirmed CreateTreasure handlers pass entity ID, base ID, zero layer/layout placeholders, and packet index in the same order.",
        ],
    },
    {
        "role": "Treasure setup",
        "ps3Address": "0x00986F98",
        "ps3Name": "Client::Game::Object::Treasure::Setup",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00986F98",
        "windowsAddress": "0x1409EBE30",
        "windowsName": "Client__Game__Object__Treasure__Setup",
        "confidence": "high",
        "evidence": [
            "Both initialize the object through adjacent virtual boundaries, store base ID, set object kind 4, normalize layer ID when layout ID is zero, call SetLayoutId, resolve treasure data, and notify EventFramework of object creation.",
            "StaticObjectManager::CreateTreasure is the unique caller in both builds and forwards the same base/layer/layout arguments.",
        ],
    },
    {
        "role": "Treasure post-creation state",
        "ps3Address": "0x00987770",
        "ps3Name": "Client::Game::Object::Treasure::OnCreated",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00987770",
        "windowsAddress": "0x1409EC260",
        "windowsName": "Client__Game__Object__Treasure__OnCreated",
        "confidence": "high",
        "evidence": [
            "The confirmed CreateTreasure handlers call these unique methods after all object, item, position, entity, layout, and base fields are populated.",
            "Both conditionally transition an already-open supported treasure to hidden graphical state through the corresponding virtual visibility boundary.",
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
    {
        "windowsAddress": "0x1406604E0",
        "windowsName": "Win335_EventFramework__InitializeQuestHandlersIfReady",
        "roles": ["quest-state initialization notifications"],
        "confidence": "high",
        "mappingKind": "windows-supporting",
        "evidence": [
            "The distinct OnQuestsInitialized, OnQuestCompleteFlagsInitialized, OnDailyQuestsInitialized, and OnQuestRepeatFlagsInitialized thunks share this implementation in Windows.",
            "It checks the 3.x quest-state readiness conditions and then initializes event handlers of type 1; compiler folding prevents assigning it one of the four source notification identities.",
        ],
    },
    {
        "windowsAddress": "0x1409EC2B0",
        "windowsName": "Win335_Treasure__ApplyLootItems",
        "roles": ["LootItems treasure-state application"],
        "confidence": "high",
        "mappingKind": "windows-supporting",
        "evidence": [
            "The confirmed OnLootItems handler resolves a Treasure by packet entity ID and passes the unchanged payload to this sole downstream method.",
            "The method copies catalogue IDs by item count, stores the three timers, marks loot/open state, and enters graphical opening state 1; this is the Windows-inlined counterpart of the PS3 TreasureManager::OnLootItemList behavior rather than a defensible one-to-one source function.",
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
