#!/usr/bin/env python3
# Copyright (c) 2017 The MagnaChain Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""
Smart Contract Testing - softfork test

测试合约相关的分叉情况

开4个节点,节点1,2为1组，3，4为1组
主要测试以下情况：
发布：
    1.同一个utxo，分叉引用发布合约
        a.utxo为普通交易输出
        b.utxo为合约输出
    2.同一个合约交易，在主链与分叉上发布
调用:
    1.链高度不同
        a.调用同一合约，不含send操作
        b.调用同一合约，含send操作
        c.切换主链后，前主链产出的块不计入新主链

"""
# Imports should be in PEP8 ordering (std library first, then third party
# libraries then local imports).
from decimal import Decimal

# Avoid wildcard * imports if possible
from test_framework.test_framework import MagnaChainTestFramework
from test_framework.mininode import COIN,MINER_REWARD
from test_framework.script import CScript
from test_framework.util import (
    assert_equal,
    assert_greater_than,
    assert_raises_rpc_error,
    assert_contains,
    generate_contract,
    sync_mempools,
    sync_blocks,
    bytes_to_hex_str,
    hex_str_to_bytes,
    connect_nodes_bi,
    wait_until,
)
from test_framework.contract import Contract

def get_contract_hex(contract):
    with open(contract) as fh:
        content = "".join(fh.readlines())
    return  bytes_to_hex_str(bytes(content, encoding='utf-8'))

class ContractForkTest(MagnaChainTestFramework):
    def set_test_params(self):
        """Override test parameters for your individual test.

        This method must be overridden and num_nodes must be exlicitly set."""
        self.setup_clean_chain = True
        self.num_nodes = 4

    def run_test(self):
        """Main test logic"""
        # prepare
        for i,node in enumerate(self.nodes):
            # for convenient
            setattr(self,'node' + str(i),node)

        for n in self.nodes:
            n.generate(2)  # make some coins
            self.sync_all()

        # main test
        self.contract_file = generate_contract(self.options.tmpdir)
        self.tips_num = 1
        # self.log.info("start test_publish_fork_with_utxo,normal utxo")
        # self.test_publish_fork_with_utxo()
        # self.log.info("start test_publish_fork_with_utxo,contract utxo")
        # self.test_publish_fork_with_utxo(is_contract_output=True)
        # self.log.info("start double publish on both chain")
        # self.test_double_publish()
        # self.log.info("start test_callcontract_fork,without send")
        # self.test_callcontract_fork()
        # self.log.info("start test_callcontract_fork,with send, crash point 1")
        self.test_callcontract_fork(with_send=True,crash_point=1)
        self.log.info("start test_callcontract_fork,with send,crash point 2")
        self.test_callcontract_fork(with_send=True, crash_point=2)
        self.log.info("start mix transaction reorg test,no generate")
        self.test_mix_contract_transaction_fork()
        self.log.info("start mix transaction reorg test,with generate")
        self.test_mix_contract_transaction_fork(gen_blocks=True)


    def test_publish_fork_with_utxo(self,is_contract_output = False):
        '''
             ab0[utxo1]
          /         \
        aa1 [ca1]   bb1 [cb1]
         |           |
        aa2         bb2
         |           |
        aa3         bb3
                     |
                    bb4
                     |
                    ...
        :param contract_output:
        :return:
        '''
        hex_content = get_contract_hex(self.contract_file)
        coster = self.node0.getnewaddress()
        if is_contract_output:
            ct = Contract(self.node0)
            tmp_tx1 = ct.call_payable(amount = 2000)['txid']
            tmp_tx2 = ct.call_sendCoinTest(coster,1000)['txid']
            print(ct.publish_txid,tmp_tx1,tmp_tx2)
        else:
            print(self.node0.sendtoaddress(coster, 1000))
        self.node0.generate(2)
        self.sync_all()
        blocks_num = self.node1.getblockcount()
        '''
        分割成2个网络，然后各自用同一个utxo发布合约
        '''
        self.split_network()
        sender_pub = self.node0.validateaddress(coster)['pubkey']
        sender_pri = self.node0.dumpprivkey(coster)
        amount = 0
        changeaddress = self.node0.getnewaddress()
        result = self.publish_contract(self.node0,hex_content,coster,sender_pub,sender_pri,amount,changeaddress)
        print(result)
        txid_a1 = result['txid']
        contract_a1 = result['contractaddress']
        # 第一组节点同步,这是该组链高度应该为12
        block_a1,block_a2 = self.node0.generate(2)
        self.sync_all([self.nodes[:2], self.nodes[2:]])
        assert_equal(self.node1.getblockcount(),blocks_num + 2)
        assert_equal(self.node1.getbestblockhash(), block_a2)
        last_block_hash =  block_a2

        # 第二组开始发布合约
        amount = 1
        changeaddress = self.node2.getnewaddress()
        result = self.publish_contract(self.node2,hex_content, coster, sender_pub, sender_pri,amount, changeaddress)
        print(result)
        txid_b1 = result['txid']
        contract_b1 = result['contractaddress']
        # 第二组节点同步,这是该组链高度应该为22
        block_b13 = self.node2.generate(12)[11]
        self.sync_all([self.nodes[:2], self.nodes[2:]])
        assert_equal(self.node2.getblockcount(),blocks_num + 12)
        assert_equal(self.node2.getbestblockhash(),block_b13)

        # 合并网络
        for i in range(4):
            print("before join:",i,self.nodes[i].getblockcount(),int(self.nodes[i].getchaintipwork(), 16) )
        self.join_network()
        for i in range(4):
            print(i,self.nodes[i].getblockcount(),int(self.nodes[i].getchaintipwork(), 16) )
        # 确认存在分叉存在，并且主链为22个区块的
        tips = self.nodes[0].getchaintips ()
        print(tips)
        assert_equal (len (tips), self.tips_num + 1)
        self.tips_num += 1
        assert_equal(self.node2.getblockcount(), blocks_num + 12)
        assert_equal(self.node2.getbestblockhash(), block_b13)
        print(self.node0.gettransaction(txid_a1))
        # 确认分叉上的合约在主链上不能被调用
        assert_raises_rpc_error(-1, "CallContractReal => GetContractInfo fail, contractid is " + contract_a1,self.node0.callcontract, True,
                                1, contract_a1, self.node0.getnewaddress(), "payable")
        # 主链合约是可以调用的
        print(self.node0.callcontract(True, 1, contract_b1, self.node0.getnewaddress(), "payable"))
        # 未完成的用例，下面的有问题，先屏蔽
        # '''
        # listsinceblock(lastblockhash) should now include txid_a1, as seen from nodes[0]
        # 这里只有node0节点才成功，换成其他节点时失败的，这不应该
        # '''
        lsbres = self.nodes[0].listsinceblock(last_block_hash)
        assert any(tx['txid'] == txid_a1 for tx in lsbres['removed']) # 这里只有node0节点才成功，换成其他节点时失败的，这不应该

        # but it should not include 'removed' if include_removed=false
        lsbres2 = self.nodes[0].listsinceblock(blockhash=last_block_hash, include_removed=False)
        assert 'removed' not in lsbres2
        # '''


    def test_double_publish(self):
        '''
        同一个合约交易，在主链与分叉上发布
        合并后，确认数为2(bb-bb4),而不是3(a1-a2-a3)
        txid同时存在于listsinceblock的transactions和removed
        只消耗一份utxo，合约余额也只有一份
              ab0
          /       \
        aa1 [ca1]   bb1
         |           |
        aa2         bb2
         |           |
        aa3         bb3 [ca1]
                     |
                    bb4
        :return:
        '''
        self.sync_all()
        self.node0.generate(2)
        self.sync_all()
        assert_equal(self.node0.getrawmempool(),[])

        hex_content = get_contract_hex(self.contract_file)
        coster = self.node0.getnewaddress()
        sendtx = self.node0.sendtoaddress(coster, 1000)
        self.node0.generate(1)
        self.sync_all()
        sender_pub = self.node0.validateaddress(coster)['pubkey']
        sender_pri = self.node0.dumpprivkey(coster)
        amount = 100
        changeaddress = self.node0.getnewaddress()

        balance = self.node0.getbalance()
        signed_tx = self.publish_contract(self.node0,hex_content,coster,sender_pub,sender_pri,amount,changeaddress,send_flag=False)
        blocks_num = self.node0.getblockcount()

        self.split_network()

        txid1 = self.node0.sendrawtransaction(signed_tx['hex'])
        # generate bb1-bb2 on right side
        self.node2.generate(2)
        txid2 = self.node2.sendrawtransaction(signed_tx['hex'])
        print(txid1,txid2)
        assert_equal(txid1, txid2)

        lastblockhash = self.node0.generate(3)[-1]
        block_hash = self.node2.generate(2)[-1]
        blocks = self.make_more_work_than(2,0)
        gen_blocks = len(blocks)

        # join network
        for i in range(4):
            print("before join:", i, self.nodes[i].getblockcount(), int(self.nodes[i].getchaintipwork(), 16))
            print("mempool:",self.nodes[i].getrawmempool())

        print("join network")
        connect_nodes_bi(self.nodes, 1, 2)
        sync_blocks(self.nodes)

        for i in range(4):
            print("mempool:", self.nodes[i].getrawmempool())
        # 确认存在分叉存在
        tips = self.nodes[1].getchaintips()
        print(tips)
        assert_equal(len(tips), self.tips_num + 1)
        self.tips_num += 1
        assert_equal(self.node1.getblockcount(), blocks_num + 4 + gen_blocks)
        assert_equal(self.node1.getbestblockhash(), blocks[-1] if gen_blocks > 0 else block_hash)

        # assert
        assert_equal(self.node0.getbalance() - MINER_REWARD + 100 - self.get_txfee(txid1['txid']) + self.get_txfee(sendtx),balance)
        assert_equal(self.node2.getbalanceof(txid1['contractaddress']),100)

        # listsinceblock(lastblockhash) should now include txid1 in transactions
        # as well as in removed
        lsbres = self.node0.listsinceblock(lastblockhash)
        assert any(tx['txid'] == txid1['txid'] for tx in lsbres['transactions'])
        assert any(tx['txid'] == txid1['txid'] for tx in lsbres['removed'])

        # find transaction and ensure confirmations is valid
        for tx in lsbres['transactions']:
            if tx['txid'] == txid1['txid']:
                assert_equal(tx['confirmations'], 2+gen_blocks)

        # the same check for the removed array; confirmations should STILL be 2
        for tx in lsbres['removed']:
            if tx['txid'] == txid1['txid']:
                assert_equal(tx['confirmations'], 2+gen_blocks)

    def test_callcontract_fork(self,with_send = False,crash_point = 1):
        '''
        调用同一合约，不含send操作与含send操作
        ab0[contract_ab]
          /         \
        aa1 [cca1]   bb1 [ccb1]
         |           |
        aa2         bb2
         |           |
        aa3         bb3
                     |
                    bb4
                     |
                    ...
        :param with_send:
        :return:
        '''
        self.sync_all()
        self.node0.generate(2)
        assert_equal(self.node0.getrawmempool(),[]) #make sure mempool empty
        assert_equal(self.node1.getrawmempool(), [])  # make sure mempool empty
        ct = Contract(self.node1,debug = False)
        ct2 = Contract(self.node1,debug = False)
        ct2.call_payable(amount = 1000)
        print(ct.publish_txid)
        self.sync_all()
        self.node0.generate(2)
        self.sync_all()
        blocks_num = self.node1.getblockcount()

        # split mgc network
        self.split_network()
        self.node1.generate(2)  #fork
        self.node3.generate(8)  # fork

        # in group 1
        balance = self.node1.getbalance()

        # tx_ai,tx_a11,tx_a12这3个交易，在合并网络后，应该都会被重新打回内存池中，毕竟是短链
        tx_a1 = ct.call_payable(amount = 2000)['txid']
        tx_a11 = ct.call_contractDataTest(amount = 0)['txid']
        tx_a12 = ct.call_contractDataTest(amount = 0)['txid']
        if with_send:
            tmp_ct = Contract(self.node1,debug = False)
            print(tmp_ct.publish_txid)
            tx_a13 = ct.call_callOtherContractTest(ct2.contract_id,'callOtherContractTest',tmp_ct.contract_id,"contractDataTest")
            print("ct balance:",ct.get_balance())
            print(tx_a13)
        print(tx_a1,tx_a11,tx_a12)
        self.sync_all([self.nodes[:2], self.nodes[2:]])
        last_block_hash = self.node1.generate(2)[-1]
        assert self.node1.getrawmempool() == []
        self.sync_all([self.nodes[:2], self.nodes[2:]])

        # in group 2
        tx_b1 = ct.call_payable(amount=2000,exec_node = self.node3,sender = self.node3.getnewaddress())['txid']
        print(tx_b1)
        self.sync_all([self.nodes[:2], self.nodes[2:]])
        self.node3.generate(2)
        self.sync_all([self.nodes[:2], self.nodes[2:]])
        assert tx_b1 not in self.node3.getrawmempool()
        tx_b11 = ct.call_contractDataTest(amount = 0,exec_node = self.node3)['txid']
        print("ct balance:", ct.get_balance(exec_node = self.node3))
        if with_send:
            # 这里有两个crash point,下面代码分别对应不同的CP
            if crash_point == 1:
                tx_b12 = ct.call_callOtherContractTest(ct2.contract_id, 'callOtherContractTest',
                                                   ct.contract_id, "contractDataTest",exec_node = self.node3)
                print("ct balance:", ct.get_balance(exec_node=self.node3))
            else:
                tx_b12 = ct.call_callOtherContractTest(ct2.contract_id, 'callOtherContractTest',
                                                   ct.contract_id, "contractDataTest")
                print("ct balance:", ct.get_balance(exec_node=self.node1))
            print("ct balance:", ct.get_balance(exec_node=self.node3))
            print("tx_b12:",tx_b12.txid)
        print(tx_b11)
        block_b16 = self.node3.generate(6)[-1]
        assert_equal(self.node3.getrawmempool(),[])
        if with_send and crash_point == 1:
            assert_equal(self.node1.getrawmempool(), [])
        elif with_send and crash_point == 2:
            assert_equal(self.node1.getrawmempool(), [tx_b12.txid])
        self.sync_all([self.nodes[:2], self.nodes[2:]])

        # join network
        more_work_blocks = self.make_more_work_than(3, 1)
        for i in range(4):
            print("before join:", i, self.nodes[i].getblockcount(), int(self.nodes[i].getchaintipwork(), 16))
            print("mempool:",self.nodes[i].getrawmempool())

        print("ct balance:", ct.get_balance(exec_node=self.node3))
        print("ct balance:", ct.get_balance(exec_node=self.node1))
        print("join network")
        connect_nodes_bi(self.nodes, 1, 2)
        sync_blocks(self.nodes)

        print("ct balance:", ct.get_balance(exec_node=self.node1))
        print("ct balance:", ct.get_balance(exec_node=self.node3))


        for i in range(4):
            print("mempool:", self.nodes[i].getrawmempool())
        if with_send:
            assert_equal(len(self.node1.getrawmempool()),5 if crash_point == 1 else 6) #短链的块内交易必须是打回内存池的，否则可能有bug了
        else:
            assert_equal(len(self.node1.getrawmempool()), 3)  # 短链的块内交易必须是打回内存池的，否则可能有bug了
        assert (balance - MINER_REWARD * 2 - 2000) - self.node1.getbalance() < 100
        print("node2 ct get_balance:",ct.get_balance(exec_node = self.node2))
        assert_equal(self.node1.getbalanceof(ct.contract_id), 2000 - 10 if with_send else 2000) #减去合约的send调用
        assert_equal(self.node0.getbalanceof(ct.contract_id), 2000 - 10 if with_send else 2000)    #减去合约的send调用
        assert_equal(ct.call_get('counter',broadcasting = False)['return'][0], 4)  #因为本节点mempool有合约交易，所以应该为4
        assert_equal(ct.call_get('counter',broadcasting = False,exec_node = self.node2)['return'][0], 2) #该节点内存池中没有交易哦，所以应该为2
        for i in range(4):
            print("node{} ct2 get_balance:{}".format(i,ct2.get_balance(exec_node=self.nodes[i])))
        assert_equal(self.node0.getbalanceof(ct2.contract_id), 1000 if with_send else 1000)  # 减去合约的send调用
        assert_equal(self.node1.getbalanceof(ct2.contract_id), 1000 if with_send else 1000)  # 减去合约的send调用
        assert_equal(self.node2.getbalanceof(ct2.contract_id), 1000 - 10 if with_send else 1000)  # 减去合约的send调用


        for i in range(4):
            print(i, self.nodes[i].getblockcount(), int(self.nodes[i].getchaintipwork(), 16))
        tips = self.nodes[0].getchaintips()
        print(tips)
        assert_equal(len(tips), self.tips_num + 1)
        self.tips_num += 1
        assert_equal(self.node2.getblockcount(), blocks_num + 16 + len(more_work_blocks))
        assert_equal(self.node2.getbestblockhash(), block_b16 if not more_work_blocks else more_work_blocks[-1])
        print(self.node1.gettransaction(tx_a1))
        print(self.node1.gettransaction(tx_a11))

        #clear node0's and node1's mempool and check balance
        self.node1.generate(4)
        sync_blocks(self.nodes)
        assert_equal(self.node0.getrawmempool(), [])
        assert_equal(self.node1.getrawmempool(), [])
        assert_equal(self.node1.getbalanceof(ct.contract_id), 4000 - 10 if with_send else 4000)
        assert (balance - MINER_REWARD * 2 - 2000) - self.node1.getbalance() < 100

        # In bestchain,ensure contract data is correct
        for i in range(4):
            assert_equal(ct.call_get('counter',exec_node = self.nodes[i],sender = self.nodes[i].getnewaddress())['return'][0],4)

        # 未完成的用例，下面的有问题，先屏蔽
        # '''
        # listsinceblock(lastblockhash) should now include txid_a1, as seen from nodes[0]
        # 这里只有node1节点才成功，换成其他节点时失败的，这不应该
        lsbres = self.nodes[1].listsinceblock(last_block_hash)
        assert any(tx['txid'] == tx_a1 for tx in lsbres['transactions'])# 这里只有node1节点才成功，换成其他节点时失败的，这不应该

        # but it should not include 'removed' if include_removed=false
        lsbres2 = self.nodes[1].listsinceblock(blockhash=last_block_hash, include_removed=False)
        assert 'removed' not in lsbres2
        # '''

    def test_mix_contract_transaction_fork(self,gen_blocks = False):
        '''
        在2条分叉链中，混合执行各种交易，然后：
        1.不产生块，合并网络
        2.产生块，合并网络

        :return:
        '''
        self.sync_all()
        self.node1.generate(2)
        assert_equal(self.node1.getrawmempool(),[]) #make sure mempool empty
        assert_equal(self.node0.getrawmempool(), [])  # make sure mempool empty
        ct = Contract(self.node0)
        ct2 = Contract(self.node0)
        ct2.call_payable(amount = 1000)
        print(ct.publish_txid)
        self.sync_all()
        self.node0.generate(2)
        self.sync_all()
        blocks_num = self.node0.getblockcount()

        # split mgc network
        self.split_network()
        self.node0.generate(2)  #fork
        self.node2.generate(8)  # fork
        balances = [n.getbalance() for n in self.nodes]

        # in group 1
        # normal transaction
        sendtxs_a = [self.node0.sendtoaddress(self.node3.getnewaddress(),1000) for i in range(10)]

        # publish contract transaction
        ccontracts_a = [Contract(self.node0) for i in range(10)]

        # call contract transaction
        call_contract_txs_a = [ct.call_payable(amount = 1000).txid for ct in  ccontracts_a]
        call_contract_txs_a1 = [ct.call_callOtherContractTest(ccontracts_a[0].contract_id, 'callOtherContractTest',ccontracts_a[-1].contract_id, "contractDataTest").txid for ct in ccontracts_a]

        # long mempool chain transaction
        call_contract_txs_a2 = []
        for i in range(30):
            result = ccontracts_a[1].call_reentrancyTest(throw_exception=False)
            if result.reason():
                print(result.reason())
                break
            else:
                call_contract_txs_a2.append(result.txid)

        ccontracts_a[2].call_maxContractCallTest(2).txid
        self.sync_all([self.nodes[:2], self.nodes[2:]])

        #in group 2
        sendtxs_b = [self.node2.sendtoaddress(self.node1.getnewaddress(),1000) for i in range(10)]

        # publish contract transaction
        ccontracts_b = [Contract(self.node2) for i in range(10)]

        # call contract transaction
        call_contract_txs_b = [ct.call_payable(amount = 1000).txid for ct in  ccontracts_b]
        call_contract_txs_b1 = [ct.call_callOtherContractTest(ccontracts_b[0].contract_id, 'callOtherContractTest',ccontracts_b[-1].contract_id, "contractDataTest").txid for ct in ccontracts_b]

        # long mempool chain transaction
        call_contract_txs_b2 = []
        for i in range(30):
            result = ccontracts_b[1].call_reentrancyTest(throw_exception=False)
            if result.reason():
                print(result.reason())
                break
            else:
                call_contract_txs_b2.append(result.txid)

        ccontracts_b[2].call_maxContractCallTest(2).txid
        self.sync_all([self.nodes[:2], self.nodes[2:]])

        # join network
        if gen_blocks:
            blocks_a = self.node0.generate(2)
            blocks_b = self.node2.generate(6)
            more_work_blocks = self.make_more_work_than(2, 0)

            for i in range(4):
                print("before join:", i, self.nodes[i].getblockcount(), int(self.nodes[i].getchaintipwork(), 16))
                print("mempool:", self.nodes[i].getrawmempool())

        print("join network")
        connect_nodes_bi(self.nodes, 1, 2)
        try:
            print("sync_mempools.......")
            sync_mempools(self.nodes,timeout = 30)
            print("sync_mempools done")
        except Exception as e:
            print("sync mempool failed,ignore!")

        sync_blocks(self.nodes)

        if gen_blocks:
            for i in range(4):
                print("mempool:", self.nodes[i].getrawmempool())
        for i in range(4):
            print(i, self.nodes[i].getblockcount(), int(self.nodes[i].getchaintipwork(), 16))
        tips = self.nodes[0].getchaintips()
        print("tips:",tips)
        assert_equal(len(tips), self.tips_num + 1)
        self.tips_num += 1

        # 合并后，节点再次调用合约,该交易应该回被不同组的节点抛弃，因为合约不存在
        tx1 = ccontracts_a[2].call_reentrancyTest().txid
        tx2 = ccontracts_b[2].call_reentrancyTest().txid
        try:
            sync_mempools(self.nodes, timeout=30)
        except Exception as e:
            print("sync_mempools(self.nodes,timeout = 30) not done")
        wait_until(lambda: tx1 not in self.node2.getrawmempool(), timeout=10)
        wait_until(lambda: tx1 in self.node1.getrawmempool(), timeout=10)
        wait_until(lambda: tx2 not in self.node1.getrawmempool(), timeout=10)
        wait_until(lambda: tx2 in self.node3.getrawmempool(), timeout=10)

        for i,n in enumerate(self.nodes):
            n.generate(2)
            print("node{} generate done".format(i))
            sync_blocks(self.nodes)
         # todo more assert



    def publish_contract(self,node,hex_content, coster, sender_pub, sender_pri,amount, changeaddress,send_flag = True):
        pre_transaction = node.prepublishcode(hex_content, coster, sender_pub, amount, changeaddress)
        print(pre_transaction)
        txhex = pre_transaction['txhex']
        spent_utxo = pre_transaction['coins']
        print(spent_utxo)
        prevtxs = []
        for ele in spent_utxo:
            info = {}
            info['txid'] = ele['txhash']
            info['vout'] = ele['outn']
            info['amount'] = ele['value']
            info['scriptPubKey'] = ele['script']
            prevtxs.append(info)
        signed_tx = node.signrawtransaction(txhex, prevtxs, [sender_pri, sender_pri])
        print(signed_tx)
        if send_flag:
            return node.sendrawtransaction(signed_tx['hex'])
        return signed_tx


    def get_txfee(self, txid, node_index=0):
        return Decimal(self.nodes[node_index].gettransaction(txid)['fee'])

if __name__ == '__main__':
    ContractForkTest().main()

