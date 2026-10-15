import json
import pandas as pd
import pytest
from logic_b.h02_minute_audit import audit_h02_minute_execution
from logic_b.h02_certification import _validated_official_limit_codes, inspect_h02_executable_provenance


def minute_bars():
    return pd.DataFrame({
        'trade_time': [pd.Timestamp('2020-01-03 09:35:00'), pd.Timestamp('2020-01-03 09:36:00')],
        'open': [10.0, 10.1], 'high': [10.2, 10.3],
        'low': [9.9, 10.0], 'close': [10.1, 10.2], 'vol': [200, 300],
    })


def test_normal_minute_is_structurally_valid_not_fill_certified():
    r = audit_h02_minute_execution(minute_bars(), '20200103')
    assert r['status'] == 'STRUCTURALLY_VALID'
    assert r['fill_certified'] is False


@pytest.mark.parametrize('column', ['open', 'high', 'low', 'close'])
def test_infinite_ohlc_rejected(column):
    b = minute_bars()
    b.loc[1, column] = float('inf')
    assert audit_h02_minute_execution(b, '20200103')['reason'] == 'invalid_ohlc'


@pytest.mark.parametrize('delta', [pd.Timedelta(microseconds=1), pd.Timedelta(nanoseconds=1)])
def test_fractional_minute_timestamp_rejected(delta):
    b = minute_bars()
    b['trade_time'] = pd.Series([
        pd.Timestamp('2020-01-03 09:35:00'),
        pd.Timestamp('2020-01-03 09:36:00') + delta,
    ], dtype=object)
    assert audit_h02_minute_execution(b, '20200103')['reason'] == 'out_of_session_or_nonminute_timestamp'


def test_valid_limit_code():
    assert _validated_official_limit_codes(pd.DataFrame({'ts_code': ['000998.SZ'], 'up_limit': [11.0], 'down_limit': [9.0]})) == {'000998.SZ'}


@pytest.mark.parametrize('up,down', [(float('nan'),9), (0,9), (9,11), (float('inf'),9), (11,float('nan')), (11,11), (11,0)])
def test_invalid_official_price_bands_fail_closed(up, down):
    assert _validated_official_limit_codes(pd.DataFrame({'ts_code': ['000998.SZ'], 'up_limit': [up], 'down_limit': [down]})) == set()


def test_duplicate_limit_codes_reject_all_ambiguous_rows():
    frame = pd.DataFrame({'ts_code': ['000998.SZ', '000998.SZ'], 'up_limit': [11,11], 'down_limit': [9,9]})
    assert _validated_official_limit_codes(frame) == set()


def test_missing_price_column_fail_closed():
    assert _validated_official_limit_codes(pd.DataFrame({'ts_code': ['000998.SZ']})) == set()


class FakeStore:
    def __init__(self, tmp_path, bad_limits):
        self.root = tmp_path
        self.frames = {}
        self.manifests = {}
        self.frames['limit_up', '20200102'] = pd.DataFrame({'ts_code': ['000998.SZ']})
        for d in ['20200102', '20200103']:
            self.frames['limit_prices', d] = bad_limits.copy()
            self.frames['stock_st', d] = pd.DataFrame(columns=['ts_code'])
            self.frames['suspend', d] = pd.DataFrame(columns=['ts_code'])
            for k in ['limit_prices', 'stock_st', 'suspend']:
                f = tmp_path / f'{k}-{d}.json'
                f.write_text(json.dumps({'metadata': {'source': 'TushareProvider'}}))
                self.manifests[k, d] = f
        self.frames['minute_1m', '20200103/000998.SZ'] = minute_bars()
    def exists(self, dataset, day): return (dataset, day) in self.frames
    def verify(self, dataset, day): return self.exists(dataset, day)
    def read_frame(self, dataset, day): return self.frames[dataset, day]
    def manifest_path(self, dataset, day): return self.manifests[dataset, day]


def test_invalid_limit_blocks_full_h02_provenance_gate(tmp_path):
    bad = pd.DataFrame({'ts_code': ['000998.SZ'], 'up_limit': [float('nan')], 'down_limit': [9]})
    r = inspect_h02_executable_provenance(FakeStore(tmp_path, bad), ['20200102', '20200103'])
    assert r['status'] == 'BLOCKED_UNCERTIFIED_EXECUTION_INPUTS'
    assert r['candidate_official_limit_rows_missing'] == 1
    assert r['candidate_official_limit_rows_invalid'] == 1
    assert r['minute_execution_structurally_valid_symbol_days'] == 1
    assert r['net_equity_validated'] is False


def test_valid_limits_do_not_certify_fill_or_equity(tmp_path):
    good = pd.DataFrame({'ts_code': ['000998.SZ'], 'up_limit': [11], 'down_limit': [9]})
    r = inspect_h02_executable_provenance(FakeStore(tmp_path, good), ['20200102', '20200103'])
    assert r['status'] == 'READY_FOR_FURTHER_EXECUTION_AUDIT'
    assert r['net_equity_validated'] is False
    assert r['minute_publication_certified'] is False


def test_holdout_locked_before_store_reads(tmp_path):
    good = pd.DataFrame({'ts_code': ['000998.SZ'], 'up_limit': [11], 'down_limit': [9]})
    with pytest.raises(ValueError, match='holdout'):
        inspect_h02_executable_provenance(FakeStore(tmp_path, good), ['20260630', '20260701'])
