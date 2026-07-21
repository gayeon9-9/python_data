"""실습 4 확장: 데이터 품질 게이트"""

from pathlib import Path

import pandas as pd


DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "sales_raw.csv"


# IQR 범위를 벗어난 값은 삭제하지 않고 경계값으로 조정한다.
def winsorize(series: pd.Series) -> pd.Series:
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    return series.clip(lower=q1 - 1.5 * iqr, upper=q3 + 1.5 * iqr)


# 데이터가 정해진 품질 기준을 통과하는지 검사한다.
# 문제가 여러 개라면 하나만 멈추지 않고 모든 문제를 찾아서 반환한다.
def check_quality(df: pd.DataFrame) -> list[str]:
    problems = []

    required_columns = {
        "order_id", "order_date", "region", "category",
        "quantity", "unit_price", "discount",
    }

    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        problems.append(f"필수 컬럼 누락: {sorted(missing_columns)}")
        return problems

    missing_price = df["unit_price"].isna().sum()
    negative_price = (df["unit_price"] < 0).sum()
    missing_region = df["region"].isna().sum()

    q1, q3 = df["quantity"].quantile(0.25), df["quantity"].quantile(0.75)
    quantity_upper = q3 + 1.5 * (q3 - q1)
    quantity_outliers = (df["quantity"] > quantity_upper).sum()

    if missing_price:
        problems.append(f"unit_price 결측치: {missing_price}건")

    if negative_price:
        problems.append(f"unit_price 음수: {negative_price}건")

    if missing_region:
        problems.append(f"region 결측치: {missing_region}건")

    if quantity_outliers:
        problems.append(
            f"quantity IQR 상한 {quantity_upper:.1f} 초과: "
            f"{quantity_outliers}건"
        )

    return problems


# 실습 4에서 만든 정제 규칙을 하나의 함수로 묶어 재사용한다.
def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()

    # 타입을 먼저 변환해야 변환 실패로 새로 생긴 결측치까지 처리할 수 있다.
    cleaned["order_date"] = pd.to_datetime(cleaned["order_date"], errors="coerce")
    cleaned["quantity"] = pd.to_numeric(cleaned["quantity"], errors="coerce")
    cleaned["unit_price"] = pd.to_numeric(cleaned["unit_price"], errors="coerce")
    cleaned["discount"] = pd.to_numeric(cleaned["discount"], errors="coerce")
    cleaned["region"] = cleaned["region"].astype("string")
    cleaned["category"] = cleaned["category"].astype("category")

    # 음수 단가는 잘못된 값이므로 결측치로 변경한다.
    cleaned.loc[cleaned["unit_price"] < 0, "unit_price"] = pd.NA

    # 단가 결측치는 상품 특성이 비슷한 카테고리별 중앙값으로 대체한다.
    category_median = cleaned.groupby(
        "category", observed=True
    )["unit_price"].transform("median")

    cleaned["unit_price"] = cleaned["unit_price"].fillna(category_median)

    # 지역을 임의로 지정하면 지역별 매출이 왜곡되므로 '미상'으로 구분한다.
    cleaned["region"] = cleaned["region"].fillna("미상")

    # 수량과 단가의 이상치를 IQR 윈저라이징으로 조정한다.
    cleaned["quantity"] = winsorize(cleaned["quantity"]).astype("int64")
    cleaned["unit_price"] = winsorize(cleaned["unit_price"])

    # 정제된 값으로 할인 적용 매출을 계산한다.
    cleaned["amount"] = (
        cleaned["quantity"]
        * cleaned["unit_price"]
        * (1 - cleaned["discount"])
    ).round(2)

    return cleaned


# 검사 결과를 보기 쉽게 출력한다.
def print_result(title: str, problems: list[str]) -> None:
    print(f"\n[{title}]")

    if problems:
        print(f"통과 여부: False / 위반 {len(problems)}건")
        for problem in problems:
            print("-", problem)
    else:
        print("통과 여부: True / 위반 0건")


def main() -> None:
    raw = pd.read_csv(DATA_PATH)

    print("===== 실습 4 확장: 데이터 품질 게이트 =====")
    print(f"원본 데이터: {len(raw):,}행")

    # 정제하기 전에 품질 기준을 적용하면 원본의 문제점이 검출된다.
    raw_problems = check_quality(raw)
    print_result("원본 데이터 검사", raw_problems)

    # 같은 데이터를 자동 정제한 뒤 동일한 품질 기준으로 다시 검사한다.
    cleaned = clean_data(raw)
    cleaned_problems = check_quality(cleaned)
    print_result("정제 후 데이터 검사", cleaned_problems)

    print("\n[정제 결과]")
    print(f"행 수: {len(raw):,} → {len(cleaned):,}")
    print(f"결측치 총합: {cleaned.isna().sum().sum()}")
    print(f"음수 단가: {(cleaned['unit_price'] < 0).sum()}건")
    print(f"최대 수량: {cleaned['quantity'].max():.0f}")

    # 행이 사라지지 않았고 정제 후 모든 품질 기준을 통과했는지 검증한다.
    assert len(raw) == len(cleaned)
    assert not cleaned_problems

    print("\n실습 4 확장과제 완료")


if __name__ == "__main__":
    main()