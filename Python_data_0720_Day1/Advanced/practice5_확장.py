"""실습 5 확장: 반복 벤치마크와 성능 안정성 검증"""

from pathlib import Path
from time import perf_counter

import duckdb
import pandas as pd
import polars as pl


DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "events_large.csv"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# Pandas로 파일 읽기부터 집계 완료까지 전체 시간을 측정한다.
def run_pandas():
    start = perf_counter()

    df = pd.read_csv(DATA_PATH)
    result = (
        df[df["amount"] > 0]
        .groupby("event_type")
        .agg(
            cnt=("event_id", "count"),
            revenue=("amount", "sum"),
            avg=("amount", "mean"),
        )
        .reset_index()
    )

    elapsed = (perf_counter() - start) * 1000
    return result, elapsed


# Polars는 scan_csv로 실행 계획을 만든 뒤 collect에서 실제 실행한다.
def run_polars():
    start = perf_counter()

    result = (
        pl.scan_csv(DATA_PATH)
        .filter(pl.col("amount") > 0)
        .group_by("event_type")
        .agg(
            pl.col("event_id").count().alias("cnt"),
            pl.col("amount").sum().alias("revenue"),
            pl.col("amount").mean().alias("avg"),
        )
        .collect()
    )

    elapsed = (perf_counter() - start) * 1000
    return result, elapsed


# DuckDB는 CSV 파일을 데이터베이스에 저장하지 않고 SQL로 직접 조회한다.
def run_duckdb():
    start = perf_counter()

    result = duckdb.sql(
        f"""
        SELECT
            event_type,
            COUNT(event_id) AS cnt,
            SUM(amount) AS revenue,
            AVG(amount) AS avg
        FROM read_csv_auto('{DATA_PATH.as_posix()}')
        WHERE amount > 0
        GROUP BY event_type
        """
    ).df()

    elapsed = (perf_counter() - start) * 1000
    return result, elapsed


# 엔진별 출력 형식과 순서를 통일해야 결과를 정확하게 비교할 수 있다.
def normalize_result(result):
    if isinstance(result, pl.DataFrame):
        result = result.to_pandas()

    return result.sort_values("event_type").reset_index(drop=True)


def main():
    print("===== 실습 5 확장: 반복 벤치마크 =====")
    print("각 엔진 3회 실행 · 실행 순서 교차 · 결과 일치 검증\n")

    # 같은 엔진이 항상 먼저 실행되면 파일 캐시의 영향을 받을 수 있다.
    # 따라서 회차마다 실행 순서를 바꿔 조금 더 공정하게 비교한다.
    engine_orders = [
        [("Pandas", run_pandas), ("Polars", run_polars), ("DuckDB", run_duckdb)],
        [("DuckDB", run_duckdb), ("Pandas", run_pandas), ("Polars", run_polars)],
        [("Polars", run_polars), ("DuckDB", run_duckdb), ("Pandas", run_pandas)],
    ]

    records = []
    reference = None

    for round_number, engines in enumerate(engine_orders, start=1):
        print(f"[{round_number}회차]")

        for engine_name, engine_function in engines:
            result, elapsed = engine_function()
            normalized = normalize_result(result)

            # 첫 번째 결과를 기준으로 이후 8번의 집계 결과가 같은지 검증한다.
            if reference is None:
                reference = normalized
            else:
                pd.testing.assert_frame_equal(
                    reference,
                    normalized,
                    check_dtype=False,
                    check_exact=False,
                    rtol=1e-6,
                    atol=1e-6,
                )

            records.append({
                "engine": engine_name,
                "round": round_number,
                "time_ms": elapsed,
            })

            print(f"{engine_name}: {elapsed:,.0f}ms")

        print()

    # 평균뿐 아니라 중앙값과 표준편차를 함께 계산해 속도와 안정성을 확인한다.
    records_df = pd.DataFrame(records)

    summary = (
        records_df.groupby("engine")["time_ms"]
        .agg(["min", "mean", "median", "std"])
        .sort_values("median")
    )

    pandas_median = summary.loc["Pandas", "median"]
    summary["pandas_speedup"] = pandas_median / summary["median"]
    summary = summary.round(2)

    output_path = OUTPUT_DIR / "practice5_benchmark.csv"
    summary.reset_index().to_csv(output_path, index=False)

    print("[3회 반복 측정 결과]")
    print(summary)

    print("\n총 9회 집계 결과 동일 검증 통과")
    print(f"결과 저장: {output_path}")
    print("\n실습 5 확장과제 완료")


if __name__ == "__main__":
    main()