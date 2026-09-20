#pragma once
#include <cstdint>
#include <vector>
// Same fields consumed by BattleShip's relocation bridge, without its desktop
// resource-manager inheritance. Asset bytes stay in their original BE format.
struct RelocFile {
    uint32_t FileId;
    uint16_t RelocInternOffset, RelocExternOffset;
    std::vector<uint16_t> ExternFileIds;
    std::vector<uint8_t> Data;
};
