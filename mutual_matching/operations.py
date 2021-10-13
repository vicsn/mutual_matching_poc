from typing import Tuple, List

from algosdk.v2client.algod import AlgodClient
from algosdk.future import transaction
from algosdk.logic import get_application_address
from algosdk import account, encoding

from pyteal import compileTeal, Mode

from .account import Account
from .contracts import approval_program, clear_state_program
from .util import (
    waitForTransaction,
    fullyCompileContract,
    getAppGlobalState,
)

APPROVAL_PROGRAM = b""
CLEAR_STATE_PROGRAM = b""


def getContracts(client: AlgodClient) -> Tuple[bytes, bytes]:
    """Get the compiled TEAL contracts.

    Args:
        client: An algod client that has the ability to compile TEAL programs.

    Returns:
        A tuple of 2 byte strings. The first is the approval program, and the
        second is the clear state program.
    """
    global APPROVAL_PROGRAM
    global CLEAR_STATE_PROGRAM

    if len(APPROVAL_PROGRAM) == 0:
        APPROVAL_PROGRAM = fullyCompileContract(client, approval_program())
        CLEAR_STATE_PROGRAM = fullyCompileContract(client, clear_state_program())

    return APPROVAL_PROGRAM, CLEAR_STATE_PROGRAM


def createMutualMatchingApp(
    client: AlgodClient,
    sender: Account,
    beneficiary: str,
    burnAccount: str,
    startTime: int,
    end_time: int,
    minMatch: int,
    matchGrowth: int,
) -> int:
    """Create a new Mutual Matching round.

    Args:
        client: An algod client.
        sender: The account that will create the auction application.
        beneficiary: The address of the beneficiary receiving the matches
        burnAccount: Temporary burn account for remainder funds - they should
            be returned to the senders
        startTime: A UNIX timestamp representing the start time of the matching
            round.  This must be greater than the current UNIX timestamp.
        endTime: A UNIX timestamp representing the end time of the matching
            round. This must be greater than startTime.
        minMatch: The minimum match.
        matchGrowth: Factor by which commitments increase as more people participate

    Returns:
        The ID of the newly created app.
    """
    approval, clear = getContracts(client)

    globalSchema = transaction.StateSchema(num_uints=7, num_byte_slices=2)
    localSchema = transaction.StateSchema(num_uints=0, num_byte_slices=0)

    app_args = [
        encoding.decode_address(beneficiary),
        startTime.to_bytes(8, "big"),
        end_time.to_bytes(8, "big"),
        minMatch.to_bytes(8, "big"),
        matchGrowth.to_bytes(8, "big"),
        encoding.decode_address(burnAccount),
    ]

    txn = transaction.ApplicationCreateTxn(
        sender=sender.getAddress(),
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval,
        clear_program=clear,
        global_schema=globalSchema,
        local_schema=localSchema,
        app_args=app_args,
        sp=client.suggested_params(),
    )

    signedTxn = txn.sign(sender.getPrivateKey())

    client.send_transaction(signedTxn)

    response = waitForTransaction(client, signedTxn.get_txid())
    assert response.applicationIndex is not None and response.applicationIndex > 0
    return response.applicationIndex

def commitMatch(client: AlgodClient, appID: int, matcher: Account, matchAmount: int) -> None:
    """Commit a match

    Args:
        client: An Algod client.
        appID: The app ID of the auction.
        matcher: The account providing the match.
        matchAmount: The amount of the match.
    """
    appAddr = get_application_address(appID)
    appGlobalState = getAppGlobalState(client, appID)

    suggestedParams = client.suggested_params()

    payTxn = transaction.PaymentTxn(
        sender=matcher.getAddress(),
        receiver=appAddr,
        amt=matchAmount,
        sp=suggestedParams,
    )

    appCallTxn = transaction.ApplicationCallTxn(
        sender=matcher.getAddress(),
        index=appID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[b"match"],
        sp=suggestedParams,
    )

    transaction.assign_group_id([payTxn, appCallTxn])

    signedPayTxn = payTxn.sign(matcher.getPrivateKey())
    signedAppCallTxn = appCallTxn.sign(matcher.getPrivateKey())

    client.send_transactions([signedPayTxn, signedAppCallTxn])

    waitForTransaction(client, appCallTxn.get_txid())

# This should be used to return funds
def closeMatching(client: AlgodClient, appID: int, closer: Account):
    """Close a matching round.

    This action can only happen before a matching round has begun, in which
    case it is cancelled, or after a matching round has ended.

    If called after the round has ended and the round was successful, the
    committed matches are transferred to the beneficiary. If the round was not
    successful, all money is burned.

    Args:
        client: An Algod client.
        appID: The app ID of the auction.
        closer: The account initiating the close transaction.
    """
    appGlobalState = getAppGlobalState(client, appID)

    accounts: List[str] = [
        encoding.encode_address(appGlobalState[b"beneficiary"]),
        encoding.encode_address(appGlobalState[b"burn_account"])
    ]

    deleteTxn = transaction.ApplicationDeleteTxn(
        sender=closer.getAddress(),
        index=appID,
        accounts=accounts,
        sp=client.suggested_params(),
    )
    signedDeleteTxn = deleteTxn.sign(closer.getPrivateKey())

    client.send_transaction(signedDeleteTxn)

    waitForTransaction(client, signedDeleteTxn.get_txid())
