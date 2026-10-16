import pandas as pd
from logic_b.storage import LocalParquetStore

def test_store_roundtrip_and_hash(tmp_path):
    store=LocalParquetStore(tmp_path/"data")
    df=pd.DataFrame({"a":[1,2],"b":["x","y"]})
    stored=store.write_frame("demo","20260928",df,metadata={"source":"test"})
    assert stored.rows==2
    assert store.verify("demo","20260928")
    out=store.read_frame("demo","20260928")
    assert out.equals(df)
