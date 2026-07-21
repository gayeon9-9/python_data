"""실습 5: Pandas·Polars·DuckDB 성능 비교"""

from pathlib import Path
from time import perf_counter

import duckdb
import pandas as pd
import polars as pl


DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "events_large.csv"


# 비교할 작업:
# amount가 0보다 큰 결제 이벤트만 선택하고 event_type별로
# 건수·매출합계·평균금액을 계산한 뒤 매출합계 내림차순으로 정렬한다.


# 1. Pandas: CSV 전체를 메모리에 읽은 뒤 순서대로 처리한다.
start = perf_counter()

pandas_df = pd.read_csv(DATA_PATH)
pandas_result = (
    pandas_df[pandas_df["amount"] > 0]
    .groupby("event_type")
    .agg(
        cnt=("event_id", "count"),
        revenue=("amount", "sum"),
        avg=("amount", "mean"),
    )
    .sort_values("revenue", ascending=False)
    .reset_index()
)

pandas_time = (perf_counter() - start) * 1000


# 2. Polars Lazy: scan_csv로 실행 계획을 먼저 만들고,
# collect를 호출할 때 필요한 행과 컬럼만 읽어 실제 연산을 수행한다.
start = perf_counter()

polars_result = (
    pl.scan_csv(DATA_PATH)
    .filter(pl.col("amount") > 0)
    .group_by("event_type")
    .agg(
        pl.col("event_id").count().alias("cnt"),
        pl.col("amount").sum().alias("revenue"),
        pl.col("amount").mean().alias("avg"),
    )
    .sort("revenue", descending=True)
    .collect()
)

polars_time = (perf_counter() - start) * 1000


# 3. DuckDB: CSV를 별도로 데이터베이스에 넣지 않고 SQL로 바로 조회한다.
start = perf_counter()

duckdb_result = duckdb.sql(
    f"""
    SELECT
        event_type,
        COUNT(event_id) AS cnt,
        SUM(amount) AS revenue,
        AVG(amount) AS avg
    FROM read_csv_auto('{DATA_PATH.as_posix()}')
    WHERE amount > 0
    GROUP BY event_type
    ORDER BY revenue DESC
    """
).df()

duckdb_time = (perf_counter() - start) * 1000


# 4. 결과 일치 검증
# 엔진마다 출력 순서와 자료형이 다를 수 있으므로 event_type으로 정렬한 뒤 비교한다.
pandas_compare = pandas_result.sort_values("event_type").reset_index(drop=True)
polars_compare = polars_result.to_pandas().sort_values("event_type").reset_index(drop=True)
duckdb_compare = duckdb_result.sort_values("event_type").reset_index(drop=True)

pd.testing.assert_frame_equal(
    pandas_compare,
    polars_compare,
    check_dtype=False,
    check_exact=False,
    rtol=1e-6,
    atol=1e-6,
)

pd.testing.assert_frame_equal(
    pandas_compare,
    duckdb_compare,
    check_dtype=False,
    check_exact=False,
    rtol=1e-6,
    atol=1e-6,
)


# 5. 집계 결과 출력
print("===== 엔진 성능 비교 =====")
print(f"입력 데이터: {len(pandas_df):,}행")
print("질의: amount > 0 → event_type별 건수·매출합계·평균금액")

print("\n[집계 결과]")
print(pandas_result.round({"avg": 0}))

print("\n세 엔진 결과 동일 검증 통과")


# 6. Pandas 시간을 기준으로 각 엔진의 배속을 계산한다.
times = [
    ("Pandas", pandas_time),
    ("Polars", polars_time),
    ("DuckDB", duckdb_time),
]

print("\n[엔진별 실행 시간]")
print(f"{'엔진':<10}{'시간(ms)':>12}{'Pandas 대비':>15}")

for name, elapsed in sorted(times, key=lambda item: item[1]):
    speed = pandas_time / elapsed
    print(f"{name:<10}{elapsed:>12,.0f}{speed:>14.1f}x")

print("\n실습 5 엔진 성능 비교 완료")