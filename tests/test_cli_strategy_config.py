from logic_b.cli import _runner_from_config
from logic_b.models import FillModel
from logic_b.storage import LocalParquetStore


def test_runner_uses_strategy_thresholds_from_config(tmp_path):
    cfg={
        "strategy":{
            "min_confirmation":0.61,
            "min_tradability":0.42,
        },
        "portfolio":{
            "initial_cash":100000,
        },
        "execution":{
            "commission_rate":0.0003,
            "minimum_commission":5.0,
            "transfer_fee_rate":0.00001,
            "stamp_rate":0.0005,
            "decision_checkpoint":"09:35",
        },
        "universe":{
            "exclude_st":True,
            "include_boards":[
                "main",
                "chinext",
                "star",
            ],
            "exclude_no_limit_ipo_days":True,
        },
    }
    runner=_runner_from_config(
        cfg=cfg,
        store=LocalParquetStore(
            tmp_path/"data"
        ),
        model=FillModel.REALISTIC,
    )
    assert runner.strategy.min_confirmation==0.61
    assert runner.strategy.min_tradability==0.42
