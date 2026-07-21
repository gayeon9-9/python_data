"""
종합실습 2: EDA + 통계 + 머신러닝 파이프라인

STEP 1. Polars를 이용한 EDA
STEP 2. Plotly HTML 시각화 보고서
STEP 3. 결측치 처리 및 범주형 인코딩
STEP 4. 월요금 t-검정
STEP 5. 계약 유형 카이제곱 검정
STEP 6. ColumnTransformer 전처리
STEP 7. RandomForest 이탈 예측 모델
STEP 8. ROC-AUC 평가 및 joblib 저장
"""

from pathlib import Path

import joblib
import pandas as pd
import plotly.express as px
import plotly.io as pio
import polars as pl
from scipy.stats import chi2_contingency, ttest_ind
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


# analysis.py는 Total2 폴더 안에 있으므로 parents[2]가 skala_python 폴더이다.
DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "telco_churn.csv"
OUTPUT_DIR = Path(__file__).parent / "output"
REPORT_PATH = OUTPUT_DIR / "churn_eda_report.html"
MODEL_PATH = OUTPUT_DIR / "churn_model.joblib"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"데이터 파일을 찾을 수 없습니다: {DATA_PATH}")

    # ================================================================
    # STEP 1. Polars EDA
    # 과제 기준: Polars로 데이터를 읽고 집계·요약한다.
    # ================================================================
    df_pl = pl.read_csv(DATA_PATH)

    print("=" * 65)
    print("STEP 1. Polars EDA")
    print("=" * 65)
    print(f"데이터 크기: {df_pl.height:,}행 × {df_pl.width}열")
    print("컬럼:", df_pl.columns)
    print("\n[결측치 개수]")
    print(df_pl.null_count())

    # 이탈 여부에 따라 고객 수와 주요 수치의 평균을 비교한다.
    churn_summary = (
        df_pl.group_by("churn")
        .agg(
            pl.len().alias("고객수"),
            pl.col("monthly_charges").mean().round(2).alias("평균월요금"),
            pl.col("total_charges").mean().round(2).alias("평균총요금"),
            pl.col("tenure_months").mean().round(2).alias("평균가입개월"),
        )
        .sort("churn")
    )

    # 계약 유형별 이탈률을 계산한다. churn은 0과 1이므로 평균이 이탈률이다.
    contract_summary = (
        df_pl.group_by("contract")
        .agg(
            pl.len().alias("고객수"),
            pl.col("churn").mean().round(3).alias("이탈률"),
        )
        .sort("이탈률", descending=True)
    )

    print("\n[이탈 여부별 요약]")
    print(churn_summary)
    print("\n[계약 유형별 이탈률]")
    print(contract_summary)

    # 통계 검정, Plotly, scikit-learn 사용을 위해 Pandas로 변환한다.
    df = df_pl.to_pandas()
    df["churn_label"] = df["churn"].map({0: "유지", 1: "이탈"})

    # ================================================================
    # STEP 2. Plotly HTML 시각화 보고서
    # 과제 기준: 분석 결과를 대화형 HTML 보고서로 저장한다.
    # ================================================================

    # 이탈 고객과 유지 고객의 월요금 분포를 비교한다.
    fig_charge = px.box(
        df,
        x="churn_label",
        y="monthly_charges",
        color="churn_label",
        title="이탈 여부에 따른 월요금 분포",
        labels={"churn_label": "고객 상태", "monthly_charges": "월요금"},
    )

    # 계약 유형별 이탈률을 계산해 막대그래프로 표현한다.
    contract_chart = df.groupby("contract", as_index=False)["churn"].mean()
    contract_chart["churn_rate"] = contract_chart["churn"] * 100

    fig_contract = px.bar(
        contract_chart,
        x="contract",
        y="churn_rate",
        color="contract",
        title="계약 유형별 고객 이탈률",
        labels={"contract": "계약 유형", "churn_rate": "이탈률(%)"},
    )

    # 두 개의 Plotly 그래프를 하나의 HTML 파일로 저장한다.
    report_html = (
        "<!DOCTYPE html><html lang='ko'><head><meta charset='UTF-8'>"
        "<title>고객 이탈 EDA 보고서</title></head><body>"
        "<h1>고객 이탈 EDA 보고서</h1>"
        f"<p>분석 데이터: {len(df):,}건</p>"
        + pio.to_html(fig_charge, full_html=False, include_plotlyjs=True)
        + pio.to_html(fig_contract, full_html=False, include_plotlyjs=False)
        + "</body></html>"
    )

    REPORT_PATH.write_text(report_html, encoding="utf-8")
    print(f"\nSTEP 2. HTML 보고서 저장: {REPORT_PATH}")

    # ================================================================
    # STEP 3. 결측치 처리 및 범주형 인코딩 준비
    # 과제 기준: 숫자형 결측치는 중앙값, 범주형은 최빈값으로 처리한다.
    # ================================================================
    numeric_features = ["senior", "tenure_months", "monthly_charges", "total_charges", "num_services"]
    categorical_features = ["gender", "contract", "payment_method"]

    # customer_id는 고객을 구분하는 값일 뿐 이탈 원인이 아니므로 제외한다.
    X = df[numeric_features + categorical_features]
    y = df["churn"]

    print("\n" + "=" * 65)
    print("STEP 3. 결측치 및 인코딩 준비")
    print("=" * 65)
    print(f"total_charges 결측치: {X['total_charges'].isna().sum()}건")
    print("숫자형 처리: 중앙값 대체 + 표준화")
    print("범주형 처리: 최빈값 대체 + One-Hot Encoding")

    # ================================================================
    # STEP 4. Welch t-검정
    # 과제 기준: 월요금과 고객 이탈의 관계를 통계적으로 확인한다.
    # 귀무가설: 이탈 고객과 유지 고객의 평균 월요금은 같다.
    # ================================================================
    churn_charge = df.loc[df["churn"] == 1, "monthly_charges"]
    stay_charge = df.loc[df["churn"] == 0, "monthly_charges"]
    t_stat, t_pvalue = ttest_ind(churn_charge, stay_charge, equal_var=False)

    print("\n" + "=" * 65)
    print("STEP 4. 월요금 t-검정")
    print("=" * 65)
    print(f"이탈 고객 평균 월요금: {churn_charge.mean():,.2f}")
    print(f"유지 고객 평균 월요금: {stay_charge.mean():,.2f}")
    print(f"t 통계량: {t_stat:.4f}")
    print(f"p-value: {t_pvalue:.4e}")
    print("검정 결과:", "월요금과 이탈 사이에 유의한 차이가 있음" if t_pvalue < 0.05 else "유의한 차이가 없음")

    # ================================================================
    # STEP 5. 카이제곱 검정
    # 과제 기준: 계약 유형과 고객 이탈의 연관성을 확인한다.
    # 귀무가설: 계약 유형과 고객 이탈은 서로 독립이다.
    # ================================================================
    contract_table = pd.crosstab(df["contract"], df["churn"])
    chi_stat, chi_pvalue, _, _ = chi2_contingency(contract_table)

    print("\n" + "=" * 65)
    print("STEP 5. 계약 유형 카이제곱 검정")
    print("=" * 65)
    print(contract_table)
    print(f"카이제곱 통계량: {chi_stat:.4f}")
    print(f"p-value: {chi_pvalue:.4e}")
    print("검정 결과:", "계약 유형과 고객 이탈은 연관이 있음" if chi_pvalue < 0.05 else "연관이 없음")

    # ================================================================
    # STEP 6. ColumnTransformer 전처리
    # 숫자형 열과 범주형 열에 서로 다른 전처리를 적용한다.
    # ================================================================
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])

    preprocessor = ColumnTransformer([
        ("numeric", numeric_pipeline, numeric_features),
        ("categorical", categorical_pipeline, categorical_features),
    ])

    print("\nSTEP 6. ColumnTransformer 전처리 구성 완료")

    # ================================================================
    # STEP 7. RandomForest 머신러닝 파이프라인
    # 전처리와 모델을 하나로 연결해 학습과 예측 규칙을 일치시킨다.
    # ================================================================
    model = Pipeline([
    ("preprocessor", preprocessor),
    ("classifier", RandomForestClassifier(
        n_estimators=300,
        max_depth=8,
        min_samples_leaf=10,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )),
    ])

    # stratify를 사용해 훈련·평가 데이터의 이탈 고객 비율을 유지한다.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model.fit(X_train, y_train)
    prediction = model.predict(X_test)
    probability = model.predict_proba(X_test)[:, 1]

    print("\n" + "=" * 65)
    print("STEP 7. RandomForest 모델 학습")
    print("=" * 65)
    print(f"훈련 데이터: {len(X_train):,}건")
    print(f"평가 데이터: {len(X_test):,}건")

    # ================================================================
    # STEP 8. ROC-AUC 평가 및 joblib 저장
    # ROC-AUC는 모델이 이탈 고객과 유지 고객을 구별하는 능력을 평가한다.
    # ================================================================
    auc = roc_auc_score(y_test, probability)

    print("\n" + "=" * 65)
    print("STEP 8. 모델 성능 평가 및 저장")
    print("=" * 65)
    print(f"ROC-AUC: {auc:.4f}")
    print("\n[분류 성능]")
    print(classification_report(y_test, prediction, digits=3, zero_division=0))

    # 전처리기와 RandomForest가 모두 포함된 전체 Pipeline을 저장한다.
    joblib.dump(model, MODEL_PATH)

    print(f"모델 저장: {MODEL_PATH}")
    print(f"보고서 저장: {REPORT_PATH}")
    print("\n✅ 종합실습 2 전체 단계 완료")


if __name__ == "__main__":
    main()