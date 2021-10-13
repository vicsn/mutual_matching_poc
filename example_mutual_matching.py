from time import time, sleep

from algosdk import account, encoding
from algosdk.logic import get_application_address
from mutual_matching.operations import createMutualMatchingApp, commitMatch, closeMatching #setupMutualMatchingApp
from mutual_matching.util import (
    getBalances,
    getAppGlobalState,
    getLastBlockTimestamp,
)
from mutual_matching.testing.setup import getAlgodClient
from mutual_matching.testing.resources import (
    getTemporaryAccount,
    optInToAsset,
    createDummyAsset,
)


def simple_mutual_matching():
    client = getAlgodClient()

    print("Alice is generating temporary accounts...")
    sender = getTemporaryAccount(client)
    beneficiary = getTemporaryAccount(client)
    burnAccount = getTemporaryAccount(client)

    startTime = int(time()) + 10  # start time is 10 seconds in the future
    end_time = startTime + 10  # end time is 10 seconds later
    min_match = 100000
    match_growth = 2
    maxAmount = min_match*match_growth*10
    matchAmount = min_match*match_growth*2

    print(
        "Alice is creating mutual matching smart contract to collect funds for the beneficiary..."
    )
    appID = createMutualMatchingApp(
        client=client,
        sender=sender,
        beneficiary=beneficiary.getAddress(),
        burnAccount=burnAccount.getAddress(),
        startTime=startTime,
        end_time=end_time,
        minMatch=min_match,
        matchGrowth=match_growth,
    )

    beneficiaryAlgosBefore = getBalances(client, beneficiary.getAddress())[0]

    print("Alice's algo balance: ", beneficiaryAlgosBefore, " algos")

    matcher_1 = getTemporaryAccount(client)

    matcherAlgosBefore1 = getBalances(client, matcher_1.getAddress())[0]
    print("Carla wants to match, her algo balance: ", matcherAlgosBefore1, " algos")
    print("Carla is matching for max: ", maxAmount, " algos")

    commitMatch(client=client, appID=appID, matcher=matcher_1, matchAmount=maxAmount)

    matcher_2 = getTemporaryAccount(client)

    matcherAlgosBefore2 = getBalances(client, matcher_2.getAddress())[0]
    print("Dory wants to match, her algo balance: ", matcherAlgosBefore2, " algos")
    print("Dory is matching for: ", maxAmount, " algos")

    commitMatch(client=client, appID=appID, matcher=matcher_2, matchAmount=maxAmount)

    actualAppBalancesBefore = getBalances(client, get_application_address(appID))
    print("The smart contract now holds the following:", actualAppBalancesBefore)

    sleep(5) # To ensure a block is mined
    print("Commitments complete")
    _, lastRoundTime = getLastBlockTimestamp(client)
    if lastRoundTime < end_time:
        print("sleeping for: " + str(end_time - lastRoundTime + 5) + "seconds")
        sleep(end_time - lastRoundTime + 5)

    print("Alice is closing out the matching....")
    closeMatching(client, appID, beneficiary)

    actualAppBalances = getBalances(client, get_application_address(appID))
    expectedAppBalances = {0: 0}
    print("The smart contract now holds the following:", actualAppBalances)
    assert actualAppBalances == expectedAppBalances

    matcher1Balance = getBalances(client, matcher_1.getAddress())[0]
    print("Carla's balance:", matcher1Balance)

    matcher2Balance = getBalances(client, matcher_2.getAddress())[0]
    print("Dory's balance:", matcher2Balance)

    # The matchers should have the correct remaining balance
    assert matcher1Balance == matcherAlgosBefore1 - maxAmount - 2_000
    assert matcher2Balance == matcherAlgosBefore2 - maxAmount - 2_000

    actualBeneficiaryBalances = getBalances(client, beneficiary.getAddress())[0]
    print("Alice's balances after auction: ", actualBeneficiaryBalances, " Algos")
    # Beneficiary should receive the match amount, minus the txn fee
    assert actualBeneficiaryBalances >= beneficiaryAlgosBefore + matchAmount - 2_000


simple_mutual_matching()
