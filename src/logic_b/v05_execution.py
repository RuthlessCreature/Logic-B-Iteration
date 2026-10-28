"""Conservative *per-event* fill feasibility for historical v0.5 bar proxy.

This deliberately reuses Logic-B's existing minute-bar execution simulator.
It is NOT a portfolio replay and cannot assert full-fund execution, historical
ST status, auction order-book priority or broker execution. Unfilled exits
remain OPEN/LOCKED and must never become a fake realized return.
"""
from __future__ import annotations
from datetime import datetime,time
from math import floor
import pandas as pd
from .costs import TradingCosts
from .execution import simulate_buy_fill,simulate_sell_fill
from .models import FillModel
from .providers.xuangubao_market import XuangubaoMarketProvider
from .universe import board_of

DEFAULT_COSTS=TradingCosts(commission_rate=.00025,minimum_commission=5.0,
                           transfer_fee_rate=.00001,stamp_rate=.0005)
EPS=1e-9

def _price_limits(code,preclose,has_risk_status,has_ipo_limit_exception):
    if not preclose or preclose<=0:
        return None,"PRE_CLOSE_UNKNOWN"
    if has_risk_status is None or has_ipo_limit_exception is None:
        return None,"HISTORICAL_ST_OR_IPO_STATUS_UNKNOWN"
    if has_risk_status:
        return None,"HISTORICAL_ST_EXCLUDED"
    if has_ipo_limit_exception:
        return None,"IPO_NO_LIMIT_EXCLUDED"
    board=board_of(code)
    rate={"main":.10,"chinext":.20,"star":.20}.get(board)
    if rate is None:return None,"UNSUPPORTED_BOARD"
    rounding=XuangubaoMarketProvider._round_price
    return (rounding(preclose*(1+rate)),rounding(preclose*(1-rate))),None

def _lot_for_cash(price,cash,costs):
    if price<=0 or cash<=0:return 0
    shares=100*floor(cash/(price*100))
    while shares and shares*price+costs.buy_cost(shares*price)>cash+EPS:
        shares-=100
    return shares

def audit_event_fills(*,code,signal_time,entry_day_bars,exit_day_bars,
                      entry_day_preclose,exit_day_preclose,
                      risk_warning=None,ipo_no_limit=None,
                      cash=10000.0,costs=DEFAULT_COSTS,
                      model=FillModel.CONSERVATIVE):
    """One D entry and next D+1 E0 at 09:35; original minute times respected."""
    base={"source":"estimated_nonST_price_limits","model":str(model),
          "entry_filled":False,"exit_filled":False,
          "shares":0,"net_return":None,"profit":None,
          "fill_certified":False,"portfolio_replay":False}
    limits,reason=_price_limits(code,entry_day_preclose,risk_warning,ipo_no_limit)
    if reason:return {**base,"state":"UNVERIFIED","reason":reason}
    if entry_day_bars is None or entry_day_bars.empty:
        return {**base,"state":"NO_ENTRY_DATA","reason":"ENTRY_MINUTES_MISSING"}
    stamp=pd.Timestamp(signal_time)
    buy=simulate_buy_fill(ts_code=code,signal_time=stamp.to_pydatetime(),
       minute_bars=entry_day_bars,limit_up_price=limits[0],model=model)
    if not buy.filled:
        return {**base,"state":"ENTRY_UNFILLED","reason":buy.reason}
    price=float(buy.fill_price)
    qty=_lot_for_cash(price,cash,costs)
    if qty<100:
        return {**base,"state":"CASH_INSUFFICIENT","reason":"NO_FULL_100_SHARE_LOT"}
    # The simulated fill can occur in a bar with volume insufficient for
    # the target order. Conservative capacity cap: <=10% of that minute.
    row=entry_day_bars[pd.to_datetime(entry_day_bars.trade_time)==pd.Timestamp(buy.fill_time)]
    minute_volume=float(row.iloc[0]["vol"]) if len(row) else 0.
    if minute_volume<=0 or qty>minute_volume*.10:
        return {**base,"state":"VOLUME_CAPACITY_UNVERIFIED",
                "reason":"ORDER_EXCEEDS_10_PERCENT_OF_MINUTE_VOLUME"}
    if exit_day_bars is None or exit_day_bars.empty:
        return {**base,"state":"POSITION_OPEN","reason":"NEXT_DAY_MINUTES_MISSING",
                "entry_filled":True,"shares":qty,
                "entry_at":str(buy.fill_time),"entry_price":price}
    next_limits,error=_price_limits(code,exit_day_preclose,risk_warning,ipo_no_limit)
    if error:
        return {**base,"state":"POSITION_OPEN","reason":"NEXT_DAY_"+error,
                "entry_filled":True,"shares":qty}
    dt=pd.to_datetime(exit_day_bars.trade_time)
    if dt.empty:return {**base,"state":"POSITION_OPEN","reason":"NEXT_DAY_TIMES_MISSING","entry_filled":True}
    exit_checkpoint=datetime.combine(dt.iloc[0].date(),time(9,35))
    sell=simulate_sell_fill(ts_code=code,signal_time=exit_checkpoint,
       minute_bars=exit_day_bars,limit_down_price=next_limits[1],model=model)
    result={**base,"entry_filled":True,"shares":qty,"entry_at":str(buy.fill_time),
      "entry_price":price}
    if not sell.filled:
        return {**result,"state":"POSITION_OPEN","reason":sell.reason,
                "exit_filled":False}
    sold=float(sell.fill_price)
    cost_in=costs.buy_cost(price*qty)
    cost_out=costs.sell_cost(sold*qty)
    invested=price*qty+cost_in
    net=(sold*qty-cost_out-invested)/invested
    return {**result,"state":"CLOSED_PROXY","reason":None,"exit_filled":True,
      "exit_at":str(sell.fill_time),"exit_price":sold,
      "net_return":round(net,8),
      "profit":round((sold-price)*qty-cost_in-cost_out,4),
      "fees":round(cost_in+cost_out,4)}
