/*
 * This file is part of the VanitySearch distribution (https://github.com/JeanLucPons/VanitySearch).
 * Copyright (c) 2019 Jean Luc PONS.
 * GPLv3
 */

#ifndef GPUENGINEH
#define GPUENGINEH

#include <cstdint>    // uint8_t, uint32_t, uint64_t, int64_t
#include <cstddef>    // size_t
#include <string>     // std::string
#include <vector>
#include "../SECP256k1.h"

#define SEARCH_COMPRESSED   0
#define SEARCH_UNCOMPRESSED 1
#define SEARCH_BOTH         2

 // operating mode
#define SEARCH_MODE_MA 1   // multiple addresses
#define SEARCH_MODE_SA 2   // single address
#define SEARCH_MODE_MX 3   // multiple xpoints
#define SEARCH_MODE_SX 4   // single xpoint

#define COIN_BTC 1
#define COIN_ETH 2

// Number of key per thread (must be a multiple of GRP_SIZE) per kernel call
#define STEP_SIZE (1024*2)

// Output item sizes (host<->device contract)
#define ITEM_SIZE_A   28
#define ITEM_SIZE_A32 (ITEM_SIZE_A/4)

#define ITEM_SIZE_X   40
#define ITEM_SIZE_X32 (ITEM_SIZE_X/4)

typedef struct {
    uint32_t thId;
    int16_t  incr;
    uint8_t* hash;
    bool     mode;
} ITEM;

class GPUEngine {

public:
    GPUEngine(Secp256K1* secp,
        int nbThreadGroup,
        int nbThreadPerGroup,
        int gpuId,
        uint32_t maxFound,
        int searchMode,
        int compMode,
        int coinType,
        int64_t  BLOOM_SIZE,          // bytes (may exceed 2^31)
        uint64_t BLOOM_BITS,          // total bits (may exceed 2^31)
        uint8_t  BLOOM_HASHES,        // number of hash funcs
        const uint8_t* BLOOM_DATA,    // host bloom bytes
        uint8_t* DATA,                // sorted BIN records (20/32B)
        uint64_t TOTAL_COUNT,         // #records in DATA
        bool rKey);

    GPUEngine(Secp256K1* secp,
        int nbThreadGroup,
        int nbThreadPerGroup,
        int gpuId,
        uint32_t maxFound,
        int searchMode,
        int compMode,
        int coinType,
        const uint32_t* hashORxpoint,
        bool rKey);

    ~GPUEngine();

    bool SetKeys(Point* p);

    bool LaunchSEARCH_MODE_MA(std::vector<ITEM>& dataFound, bool spinWait = false);
    bool LaunchSEARCH_MODE_SA(std::vector<ITEM>& dataFound, bool spinWait = false);
    bool LaunchSEARCH_MODE_MX(std::vector<ITEM>& dataFound, bool spinWait = false);
    bool LaunchSEARCH_MODE_SX(std::vector<ITEM>& dataFound, bool spinWait = false);

    int  GetNbThread();
    int  GetGroupSize();

    std::string deviceName;

    static void PrintCudaInfo();
    static void GenerateCode(Secp256K1* secp, int size);

private:
    void InitGenratorTable(Secp256K1* secp);

    bool callKernelSEARCH_MODE_MA();
    bool callKernelSEARCH_MODE_SA();
    bool callKernelSEARCH_MODE_MX();
    bool callKernelSEARCH_MODE_SX();

    int  CheckBinary(const uint8_t* x, int K_LENGTH);

    int nbThread;
    int nbThreadPerGroup;

    uint32_t* inputHashORxpoint;
    uint32_t* inputHashORxpointPinned;

    // Bloom (host & device buffers)
    uint8_t* inputBloomLookUp;        // device
    uint8_t* inputBloomLookUpPinned;  // host pinned

    // Key buffers
    uint64_t* inputKey;        // device
    uint64_t* inputKeyPinned;  // host pinned

    // Output buffer
    uint32_t* outputBuffer;        // device
    uint32_t* outputBufferPinned;  // host pinned

    // Precomputed tables
    uint64_t* __2Gnx;
    uint64_t* __2Gny;
    uint64_t* _Gx;
    uint64_t* _Gy;

    bool     initialised;
    uint32_t compMode;
    uint32_t searchMode;
    uint32_t coinType;
    bool     littleEndian;

    bool     rKey;
    uint32_t maxFound;
    uint32_t outputSize;

    // IMPORTANT: 64-bit Bloom params (match .cu)
    int64_t  BLOOM_SIZE;    // bytes; when copying/allocating, cast to size_t
    uint64_t BLOOM_BITS;    // total bits; pass to kernels as unsigned long long
    uint8_t  BLOOM_HASHES;  // k

    uint8_t* DATA;          // sorted BIN data (20/32 bytes per record), read-only usage
    uint64_t TOTAL_COUNT;   // number of records
};

#endif // GPUENGINEH
