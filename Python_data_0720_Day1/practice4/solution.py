"""실습 4: Pandas 데이터 정제·집계"""

from pathlib import Path

import pandas as pd


# Pandas 2.x에서만 Copy-on-Write를 직접 활성화한다.
if int(pd.__version__.split(".")[0]) < 3:
    pd.options.mode.copy_on_write = True

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "sales_raw.csv"


# STEP 0. 정제 전에 데이터 크기·타입·결측치·이상치를 진단한다.
def diagnose(df: pd.DataFrame) -> None:
    print("=" * 60)
    print("STEP 0. 정제 전 데이터 진단")
    print("=" * 60)

    print("데이터 크기:", df.shape)

    print("\n[컬럼별 타입과 결측치]")
    df.info()

    print("\n[컬럼별 결측치 개수]")
    print(df.isna().sum())

    print("\n[수치형 기술통계]")
    print(df.describe())

    print("\n[데이터 앞 5행]")
    print(df.head())


# STEP 1. 숫자는 숫자, 날짜는 날짜, 범주값은 범주형으로 변환한다.
# errors="coerce"는 변환할 수 없는 값을 오류 대신 결측치로 바꾼다.
def normalize_types(df: pd.DataFrame) -> pd.DataFrame:
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["discount"] = pd.to_numeric(df["discount"], errors="coerce")
    df["region"] = df["region"].astype("string")
    df["category"] = df["category"].astype("category")

    return df


# STEP 2. 결측치와 잘못된 음수 가격을 처리한다.
def handle_missing(df: pd.DataFrame) -> pd.DataFrame:
    missing_price_before = df["unit_price"].isna().sum()
    negative_price_before = (df["unit_price"] < 0).sum()
    missing_region_before = df["region"].isna().sum()

    # 음수 가격은 정상적인 판매 가격이 아니므로 결측치로 변경한다.
    # 체인 인덱싱 대신 .loc를 사용하여 원본을 안전하게 수정한다.
    df.loc[df["unit_price"] < 0, "unit_price"] = pd.NA

    # 전체 평균이 아닌 카테고리별 중앙값으로 채운다.
    # 중앙값은 극단적인 가격의 영향을 평균보다 적게 받는다.
    category_median = df.groupby(
        "category", observed=True
    )["unit_price"].transform("median")

    df["unit_price"] = df["unit_price"].fillna(category_median)

    # 누락된 지역을 실제 지역으로 임의 지정하면 지역별 매출이 왜곡된다.
    # 따라서 별도 범주인 '미상'으로 표시한다.
    df["region"] = df["region"].fillna("미상")

    print("\n" + "=" * 60)
    print("STEP 2. 결측치 처리")
    print("=" * 60)
    print(
        f"unit_price 결측: {missing_price_before}건"
        f" → {df['unit_price'].isna().sum()}건"
    )
    print(
        f"unit_price 음수: {negative_price_before}건"
        f" → {(df['unit_price'] < 0).sum()}건"
    )
    print(
        f"region 결측: {missing_region_before}건"
        f" → {df['region'].isna().sum()}건"
    )

    return df


# STEP 3. IQR 범위를 벗어난 값을 삭제하지 않고 경계값으로 조정한다.
# 행을 삭제하지 않으므로 해당 행의 다른 정상 정보도 보존할 수 있다.
def winsorize(series: pd.Series, k: float = 1.5) -> pd.Series:
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1

    lower = q1 - k * iqr
    upper = q3 + k * iqr

    return series.clip(lower=lower, upper=upper)


def handle_outliers(df: pd.DataFrame) -> pd.DataFrame:
    quantity_max_before = df["quantity"].max()
    price_max_before = df["unit_price"].max()

    # 수량은 개수이므로 윈저라이징 후 다시 정수형으로 변환한다.
    df["quantity"] = winsorize(df["quantity"]).astype("int64")
    df["unit_price"] = winsorize(df["unit_price"])

    quantity_max_after = df["quantity"].max()
    price_max_after = df["unit_price"].max()

    print("\n" + "=" * 60)
    print("STEP 3. IQR 이상치 처리")
    print("=" * 60)
    print(f"quantity 최댓값: {quantity_max_before:.0f} → {quantity_max_after:.0f}")
    print(f"unit_price 최댓값: {price_max_before:.0f} → {price_max_after:.0f}")

    return df


# 원본에는 매출 컬럼이 없으므로 수량·단가·할인율로 실제 매출을 계산한다.
def add_amount(df: pd.DataFrame) -> pd.DataFrame:
    df["amount"] = (
        df["quantity"]
        * df["unit_price"]
        * (1 - df["discount"])
    ).round(2)

    return df


# STEP 4. groupby.agg로 카테고리별 건수·평균·중앙값·총매출을 계산한다.
def aggregate_by_category(df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df.groupby("category", observed=True)
        .agg(
            건수=("order_id", "count"),
            평균단가=("unit_price", "mean"),
            중앙단가=("unit_price", "median"),
            총매출=("amount", "sum"),
        )
        .round(1)
        .sort_values("총매출", ascending=False)
    )

    return summary


# STEP 5. 엑셀 피벗테이블처럼 카테고리와 지역을 교차하여 매출을 집계한다.
def make_pivot_table(df: pd.DataFrame) -> pd.DataFrame:
    pivot = df.pivot_table(
        index="category",
        columns="region",
        values="amount",
        aggfunc="sum",
        fill_value=0,
        observed=True,
    ).round(0)

    return pivot


# STEP 6. 지역 마스터 표를 지역명을 기준으로 left merge한다.
# left merge를 사용하면 기존 판매 데이터 5,000행을 모두 유지할 수 있다.
def merge_region_info(df: pd.DataFrame) -> pd.DataFrame:
    region_info = pd.DataFrame({
        "region": ["Seoul", "Incheon", "Busan", "Daegu", "Gwangju", "미상"],
        "권역": ["수도권", "수도권", "영남", "영남", "호남", "미상"],
    })

    before_rows = len(df)
    merged = df.merge(region_info, on="region", how="left")
    after_rows = len(merged)

    # merge 후 권역별 총매출을 추가로 집계한다.
    region_sales = (
        merged.groupby("권역")["amount"]
        .sum()
        .sort_values(ascending=False)
        .round(0)
    )

    print("\n" + "=" * 60)
    print("STEP 6. 지역 마스터 merge")
    print("=" * 60)
    print(f"merge 전후 행 수: {before_rows} → {after_rows}")
    print("행 수 일치:", before_rows == after_rows)

    print("\n[권역별 총매출]")
    print(region_sales)

    return merged


def main() -> None:
    # 데이터 불러오기
    df = pd.read_csv(DATA_PATH)

    # 진단 → 타입 → 결측 → 이상치 순서로 정제한다.
    diagnose(df)

    df = normalize_types(df)

    print("\n" + "=" * 60)
    print("STEP 1. 타입 정규화 후")
    print("=" * 60)
    print(df.dtypes)

    df = handle_missing(df)
    df = handle_outliers(df)
    df = add_amount(df)

    # groupby.agg 결과
    print("\n" + "=" * 60)
    print("STEP 4. 카테고리별 집계 groupby.agg")
    print("=" * 60)
    print(aggregate_by_category(df))

    # pivot_table 결과
    print("\n" + "=" * 60)
    print("STEP 5. 카테고리×지역 매출 pivot_table")
    print("=" * 60)
    print(make_pivot_table(df))

    # merge 결과
    merged = merge_region_info(df)

    print("\n[merge 결과 앞 5행]")
    print(merged[["order_id", "region", "권역", "amount"]].head())

    # 최종 검증: 결측치·음수 가격·행 수 변화가 없어야 한다.
    assert df.isna().sum().sum() == 0
    assert (df["unit_price"] > 0).all()
    assert len(df) == len(merged)

    print("\n" + "=" * 60)
    print("최종 확인")
    print("=" * 60)
    print("결측치 총합:", df.isna().sum().sum())
    print("최종 데이터 크기:", df.shape)
    print("최종 데이터 타입:")
    print(df.dtypes)
    print("\n실습 4 데이터 정제 및 집계 완료")


if __name__ == "__main__":
    main()