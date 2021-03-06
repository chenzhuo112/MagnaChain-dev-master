// Copyright (c) 2016 The Bitcoin Core developers
// Copyright (c) 2016-2019 The MagnaChain Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef MAGNACHAIN_WALLET_RPCWALLET_H
#define MAGNACHAIN_WALLET_RPCWALLET_H

class CRPCTable;
class JSONRPCRequest;
class MCWalletTx;

void RegisterWalletRPCCommands(CRPCTable &t);

/**
 * Figures out what wallet, if any, to use for a JSONRPCRequest.
 *
 * @param[in] request JSONRPCRequest that wishes to access a wallet
 * @return nullptr if no wallet should be used, or a pointer to the MCWallet
 */
MCWallet *GetWalletForJSONRPCRequest(const JSONRPCRequest& request);

std::string HelpRequiringPassphrase(MCWallet *);
void EnsureWalletIsUnlocked(MCWallet *);
bool EnsureWalletIsAvailable(MCWallet *, bool avoidException);

#endif //MAGNACHAIN_WALLET_RPCWALLET_H
