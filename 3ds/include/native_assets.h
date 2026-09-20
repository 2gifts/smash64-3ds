#pragma once
#include <memory>
#include <string>
#include <vector>
#include <cstdint>
#include "resource/RelocFile.h"
std::shared_ptr<RelocFile> nativeLoadReloc(uint32_t id);
struct NativeRelocInfo {uint32_t size,count;const uint16_t* deps;};
NativeRelocInfo nativeRelocInfo(uint32_t id);
std::shared_ptr<std::vector<uint8_t>> nativeLoadBlob(const std::string& name);
