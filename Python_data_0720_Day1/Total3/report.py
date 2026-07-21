"""
종합실습 3 - STEP 2~4. 데이터 분석 및 Jinja2 보고서 생성

STEP 2. 판매 데이터 로딩 및 정제
STEP 3. KPI와 카테고리별 매출 집계
STEP 4. Jinja2 템플릿으로 타임스탬프 HTML 보고서 생성
"""

from datetime import datetime

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import CONFIG


def clean_sales_data(df: pd.DataFrame) -> pd.DataFrame:
    """보고서 집계 전에 결측치와 이상치를 정제한다."""

    df = df.copy()

    # 날짜와 숫자형 열을 올바른 데이터 타입으로 변환한다.
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    for column in ["quantity", "unit_price", "discount"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    # 음수 가격은 정상 판매가격이 아니므로 결측치로 변경한다.
    df.loc[df["unit_price"] < 0, "unit_price"] = pd.NA

    # 단가 결측치는 같은 카테고리의 중앙값으로 대체해 왜곡을 줄인다.
    category_median = df.groupby("category")["unit_price"].transform("median")
    df["unit_price"] = df["unit_price"].fillna(category_median)
    df["unit_price"] = df["unit_price"].fillna(df["unit_price"].median())

    # 지역 결측치는 임의의 지역으로 배정하지 않고 '미상'으로 표시한다.
    df["region"] = df["region"].fillna("미상")

    # 비정상적으로 큰 수량은 IQR 상한으로 제한한다.
    q1, q3 = df["quantity"].quantile([0.25, 0.75])
    quantity_upper = q3 + 1.5 * (q3 - q1)
    df["quantity"] = df["quantity"].clip(lower=1, upper=quantity_upper).round().astype(int)

    # 실제 매출액 = 수량 × 단가 × (1 - 할인율)
    df["amount"] = df["quantity"] * df["unit_price"] * (1 - df["discount"])
    return df


def aggregate_sales(df: pd.DataFrame):
    """전체 KPI와 카테고리별 매출표를 만든다."""

    # 과제 체크포인트: 카테고리별 매출표를 groupby.agg로 생성한다.
    category_summary = (
        df.groupby("category")
        .agg(
            order_count=("order_id", "count"),
            total_quantity=("quantity", "sum"),
            average_price=("unit_price", "mean"),
            total_sales=("amount", "sum"),
        )
        .sort_values("total_sales", ascending=False)
        .reset_index()
    )

    total_sales = df["amount"].sum()
    category_summary["sales_share"] = category_summary["total_sales"] / total_sales * 100

    # 과제 체크포인트: 보고서 상단에 표시할 주요 KPI이다.
    kpis = {
        "order_count": len(df),
        "total_sales": total_sales,
        "average_order_sales": df["amount"].mean(),
        "top_category": category_summary.iloc[0]["category"],
    }

    return kpis, category_summary


def generate_report():
    """데이터를 분석하고 타임스탬프가 포함된 HTML 보고서를 생성한다."""

    if not CONFIG.data_path.exists():
        raise FileNotFoundError(f"데이터 파일을 찾을 수 없습니다: {CONFIG.data_path}")

    # STEP 2. 데이터 로딩 및 정제
    raw_df = pd.read_csv(CONFIG.data_path)
    clean_df = clean_sales_data(raw_df)

    # STEP 3. KPI와 카테고리별 매출 집계
    kpis, category_summary = aggregate_sales(clean_df)

    # STEP 4. Jinja2가 templates/report.html을 읽도록 설정한다.
    environment = Environment(
        loader=FileSystemLoader(CONFIG.template_dir),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # HTML에서 숫자와 비율을 보기 좋게 표시하기 위한 필터이다.
    environment.filters["number"] = lambda value: f"{value:,.0f}"
    environment.filters["percent"] = lambda value: f"{value:.1f}%"

    template = environment.get_template(CONFIG.template_name)
    generated_at = datetime.now()

    html = template.render(
        title=CONFIG.title,
        generated_at=generated_at.strftime("%Y-%m-%d %H:%M:%S"),
        kpis=kpis,
        category_rows=category_summary.to_dict("records"),
    )

    # 실행할 때마다 생성 시각이 파일명에 포함되어 기존 보고서를 보존한다.
    CONFIG.output_dir.mkdir(parents=True, exist_ok=True)
    output_name = generated_at.strftime("sales_report_%Y%m%d_%H%M%S.html")
    output_path = CONFIG.output_dir / output_name
    output_path.write_text(html, encoding="utf-8")

    return output_path, len(raw_df), len(clean_df)


if __name__ == "__main__":
    path, raw_count, clean_count = generate_report()
    print(f"원본 데이터: {raw_count:,}행")
    print(f"정제 데이터: {clean_count:,}행")
    print(f"보고서 저장: {path}")
    print("✅ 보고서 생성 완료")