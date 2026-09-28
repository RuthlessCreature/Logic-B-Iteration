import pytest

from logic_b.providers.tushare import TushareProvider


def provider_without_network():
    p=object.__new__(TushareProvider)
    p.max_attempts=4
    p.retry_base_seconds=0.5
    p.sleeps=[]
    p.sleeper=p.sleeps.append
    return p


def test_transient_error_retries_with_backoff():
    p=provider_without_network()
    calls={"n":0}

    def flaky():
        calls["n"]+=1
        if calls["n"]<3:
            raise RuntimeError("抱歉，每分钟访问频率超限")
        return "ok"

    assert p._call(flaky)=="ok"
    assert calls["n"]==3
    assert p.sleeps==[0.5,1.0]


def test_non_transient_permission_error_fails_immediately():
    p=provider_without_network()
    calls={"n":0}

    def denied():
        calls["n"]+=1
        raise RuntimeError("没有接口权限")

    with pytest.raises(RuntimeError,match="权限"):
        p._call(denied)
    assert calls["n"]==1
    assert p.sleeps==[]
