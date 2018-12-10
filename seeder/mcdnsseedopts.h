#ifndef MCDNSSEEDOPTS_H_
#define MCDNSSEEDOPTS_H_

#include <set>
#include <vector>
#include <string>

using namespace std;

class MCDnsSeedOpts {
public:
    MCDnsSeedOpts();

    int nThreads;//Number of crawlers to run in parallel (default 96)
    int nPort;// dns UDP port 
    int nDnsThreads;// dns
    int fUseTestNet;
    int fWipeBan;
    int fWipeIgnore;
    const char *mbox;
    const char *ns;
    const char *host;
    const char *tor;
    const char *ipv4_proxy;
    const char *ipv6_proxy;
    std::set<uint64_t> filter_whitelist;
    std::vector<string> seeds;

    string branchid;
    unsigned short defaultport;
    unsigned char pchMessageStart[4];

    void InitMessageStart();
    void PrintWhitelistFilter();
};

#endif