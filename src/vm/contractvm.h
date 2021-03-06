// Copyright (c) 2016-2019 The MagnaChain Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.
#ifndef SMARTCONTRACT_H
#define SMARTCONTRACT_H

#include "coding/base58.h"
#include "thread/sync.h"
#include "univalue.h"
#include "vm/contract.h"

extern "C"
{
#include "lua/lstate.h"
}

#include <boost/threadpool.hpp>

const int MAX_CONTRACT_FILE_LEN = 65536;
const int MAX_CONTRACT_CALL = 15000;
const int MAX_DATA_LEN = 1024 * 1024;

class MCTxOut;
class MCBlockIndex;

struct VMIn
{
    int txIndex;
    MCAmount payment;
    MagnaChainAddress vmCaller;
    const MCBlockIndex* prevBlockIndex;

    void Copy(const VMIn& vmIn)
    {
        this->txIndex = vmIn.txIndex;
        this->payment = vmIn.payment;
        this->vmCaller = vmIn.vmCaller;
        this->prevBlockIndex = vmIn.prevBlockIndex;
    }
};

struct VMOut
{
    UniValue ret;
    int32_t runningTimes = 0;
    MapContractContext txPrevData;
    MapContractContext txFinalData;
    std::vector<MCTxOut> recipients;
    std::map<MCContractID, MCAmount> contractCoinsOut;
};

class ContractVM
{
    static const int MAX_INTERNAL_CALL_NUM = 30;
private:
    VMIn vmIn;
    VMOut* vmOut;
    bool isPublish;
    MapContractContext data;
    MapContractContext cache;
    std::vector<MagnaChainAddress> contractAddrs;   // call contract stack
    std::queue<lua_State*> luaStates;   // cache for recycle
    std::map<MagnaChainAddress, lua_State*> usingLuaStates;

public:
    ~ContractVM();

    void Initialize(const VMIn* vmin, VMOut* vmout);

    bool PublishContract(const MagnaChainAddress& contractAddr, const std::string& rawCode, bool decompress);
    bool CallContract(const MagnaChainAddress& contractAddr, const std::string& strFuncName, const UniValue& args);

    void SetContractContext(const MCContractID& contractId, ContractContext& context);
    bool GetContractContext(const MCContractID& contractId, ContractContext& context);

    void CommitData();
    void ClearData(bool onlyCache);
    const MapContractContext& GetAllData() const;

    bool ExecuteContract(const MCTransactionRef tx, int txIndex, const MCBlockIndex* prevBlockIndex, VMOut* vmOut);
    int ExecuteBlockContract(const MCBlock* pBlock, const MCBlockIndex* prevBlockIndex, int offset, int count, std::vector<VMOut>* vmOut);

private:
    bool IsPublish() { return isPublish; }
    const MCContractID GetCurrentContractID();
    void AddRecipient(MCAmount amount, const MCScript& scriptPubKey);
    bool CallContract(const MagnaChainAddress& contractAddr, const std::string& strFuncName, const UniValue& args, long& maxCallNum);

    lua_State* GetLuaState(const MagnaChainAddress& contractAddr, bool* exist);
    void ReleaseLuaState(lua_State* L);
    void SetMsgField(lua_State* L, bool rollBackLast);

    MCAmount GetContractCoins(const MCContractID& contractId);
    MCAmount GetContractCoinOut(const MCContractID& contractId);
    MCAmount IncContractCoinsOut(const MCContractID& contractId, MCAmount delta);

    void SetData(const MCContractID& contractId, const ContractContext& context);
    bool GetData(const MCContractID& contractId, ContractContext& context);

    static int InternalCallContract(lua_State* L);
    static int SendCoins(lua_State* L);
};

class MultiContractVM
{
private:
    mutable MCCriticalSection cs;

    bool interrupt;
    std::vector<VMOut>* vmOuts;
    const MCBlockIndex* prevBlockIndex;
    boost::threadpool::pool threadPool;
    std::map<boost::thread::id, ContractVM> threadIdToVM;

public:
    MultiContractVM();
    bool Execute(const MCBlock* pBlock, const MCBlockIndex* prevBlockIndex, std::vector<VMOut>* vmOut);
    bool CheckCross(const MCBlock* pBlock, MapContractContext& finalData);

private:
    void InitializeThread();
    void DoExecute(const MCBlock* pBlock, int offset, int count);
};

int GetDeltaDataLen(const VMOut* vmOut);
uint256 BlockMerkleLeavesWithPrevData(const MCBlock* pBlock, const std::vector<VMOut>& vmOuts, std::vector<uint256>& leaves, bool* mutated);
uint256 BlockMerkleLeavesWithFinalData(const MCBlock* pBlock, const std::vector<VMOut>& vmOuts, std::vector<uint256>& leaves, bool* mutated);

#endif
