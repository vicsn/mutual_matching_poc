from pyteal import *


def approval_program():
    beneficiary_key = Bytes("beneficiary")
    start_time_key = Bytes("start")
    end_time_key = Bytes("end_time")
    reserve_amount_key = Bytes("reserve_amount")
    min_match_key = Bytes("min_match")
    num_matches_key = Bytes("num_matches")
    match_growth_key = Bytes("match_growth_key")
    burn_key = Bytes("burn_account")
    total_match_amount_key = Bytes("match_amount")

    @Subroutine(TealType.none)
    def payTotalMatch() -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.amount: App.globalGet(total_match_amount_key) - Global.min_txn_fee(),
                    TxnField.receiver: App.globalGet(beneficiary_key),
                }
            ),
            InnerTxnBuilder.Submit(),
        )

    @Subroutine(TealType.none)
    def burnRemainder() -> Expr:
        return If(Balance(Global.current_application_address()) != Int(0)).Then(
            Seq(
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.Payment,
                        TxnField.close_remainder_to: App.globalGet(burn_key),
                    }
                ),
                InnerTxnBuilder.Submit(),
            )
        )

    on_create_start_time = Btoi(Txn.application_args[1])
    on_create_end_time = Btoi(Txn.application_args[2])
    on_create = Seq(
        App.globalPut(beneficiary_key, Txn.application_args[0]),
        App.globalPut(start_time_key, on_create_start_time),
        App.globalPut(end_time_key, on_create_end_time),
        App.globalPut(min_match_key, Btoi(Txn.application_args[3])),
        App.globalPut(match_growth_key, Btoi(Txn.application_args[4])),
        App.globalPut(burn_key, Txn.application_args[5]),
        Approve(),
    )

    on_match_txn_index = Txn.group_index() - Int(1)
    on_match = Seq(
        Assert(
            And(
                # the round has started
                App.globalGet(start_time_key) <= Global.latest_timestamp(),
                # the round  has not ended
                Global.latest_timestamp() < App.globalGet(end_time_key),
                # the actual payment is before the app call
                Gtxn[on_match_txn_index].type_enum() == TxnType.Payment,
                Gtxn[on_match_txn_index].sender() == Txn.sender(),
                Gtxn[on_match_txn_index].receiver()
                == Global.current_application_address(),
                Gtxn[on_match_txn_index].amount() >= Global.min_txn_fee(),
            )
        ),
        If(
            Gtxn[on_match_txn_index].amount()
            >= App.globalGet(min_match_key)
        ).Then(
            Seq(
                App.globalPut(num_matches_key, App.globalGet(num_matches_key) + Int(1)),
                App.globalPut(total_match_amount_key, App.globalGet(num_matches_key) * App.globalGet(min_match_key) * App.globalGet(match_growth_key) ),
                Approve(),
            )
        ),
        Reject(),
    )

    on_call_method = Txn.application_args[0]
    on_call = Cond(
        [on_call_method == Bytes("match"), on_match],
    )

    on_delete = Seq(
        If(Global.latest_timestamp() < App.globalGet(start_time_key)).Then(
            Seq(
                # the round has not yet started, it's ok to delete
                Assert(
                    Or(
                        # sender must either be the beneficiary or the creator
                        Txn.sender() == App.globalGet(beneficiary_key),
                        Txn.sender() == Global.creator_address(),
                    )
                ),
                burnRemainder(),  # As long as we don't store the matchers, we burn the rest
                Approve(),
            )
        ),
        If(App.globalGet(end_time_key) <= Global.latest_timestamp()).Then(
            Seq(
                # the round has ended, pay out assets
                If(App.globalGet(beneficiary_key) != Global.zero_address())
                .Then(
                    If(
                        App.globalGet(total_match_amount_key)
                        >= App.globalGet(min_match_key)
                    )
                    .Then(
                        payTotalMatch()
                    )
                    .Else(
                        Seq(
                            burnRemainder(),  # As long as we don't store the matchers, we burn the rest
                        )
                    )
                )
                .Else(
                    burnRemainder(),  # As long as we don't store the matchers, we burn the rest
                ),
                burnRemainder(),  # As long as we don't store the matchers, we burn the rest
                Approve(),
            )
        ),
        Reject(),
    )

    program = Cond(
        [Txn.application_id() == Int(0), on_create],
        [Txn.on_completion() == OnComplete.NoOp, on_call],
        [
            Txn.on_completion() == OnComplete.DeleteApplication,
            on_delete,
        ],
        [
            Or(
                Txn.on_completion() == OnComplete.OptIn,
                Txn.on_completion() == OnComplete.CloseOut,
                Txn.on_completion() == OnComplete.UpdateApplication,
            ),
            Reject(),
        ],
    )

    return program


def clear_state_program():
    return Approve()


if __name__ == "__main__":
    with open("mutual_matching_approval.teal", "w") as f:
        compiled = compileTeal(approval_program(), mode=Mode.Application, version=5)
        f.write(compiled)

    with open("mutual_matching_clear_state.teal", "w") as f:
        compiled = compileTeal(clear_state_program(), mode=Mode.Application, version=5)
        f.write(compiled)
