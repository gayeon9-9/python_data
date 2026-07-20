# Extract / Transform / Load / run()
from pydantic import ValidationError
from models import Product
import asyncio

from pathlib import Path
import pandas as pd

## 실습 3의 코드 함수로 옮겨오기
# 모의 API 응답 대기시간
MOCK_DELAY = 0.05

# 요청이 실패할 경우 최대 3번까지 시도
MAX_RETRIES = 3


# 외부 API에서 상품 한 건을 가져오는 상황을 모의 실행
async def fetch_product(product_id):
    await asyncio.sleep(MOCK_DELAY)

    return {
        "id": product_id,
        "name": f"Product {product_id}",
        "category": " FOOD " if product_id % 2 else " ELECTRONICS ",
        "price": 1000 + product_id * 100,
    }


# 여러 상품을 동시에 수집하는 Extract 함수
async def extract(product_ids, max_concurrent=10):
    # 동시에 최대 10건만 실행
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_one(product_id):
        # 실패할 경우 최대 3번까지 재시도
        for attempt in range(MAX_RETRIES):
            try:
                async with semaphore:
                    async with asyncio.timeout(3.0):
                        return await fetch_product(product_id)

            except TimeoutError:
                # 마지막 시도까지 실패하면 예외 전달
                if attempt == MAX_RETRIES - 1:
                    raise

                # 1초 → 2초 간격으로 다시 시도
                wait = 2**attempt
                await asyncio.sleep(wait)

    tasks = [fetch_one(product_id) for product_id in product_ids]

    # 한 건이 실패해도 나머지 수집 작업은 계속 실행
    results = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    # 성공한 결과만 반환
    return [result for result in results if not isinstance(result, Exception)]


# 원본 데이터를 유효 데이터와 오염 데이터로 분리
def transform(raw_data: list[dict]) -> tuple[list[Product], list[dict]]:
    valid = []
    invalid = []

    # 데이터를 한 건씩 Pydantic으로 검증
    for row in raw_data:
        try:
            valid.append(Product.model_validate(row))

        # 검증에 실패해도 중단하지 않고 오류 내용을 따로 저장
        except ValidationError as error:
            invalid.append(
                {
                    "data": row,
                    "errors": error.errors(),
                }
            )

    return valid, invalid


# 기본 결과 저장 위치
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


# 검증을 통과한 데이터를 CSV와 Parquet로 저장
def load(valid_data, output_dir=OUTPUT_DIR):
    output_dir = Path(output_dir)

    # output 폴더가 없으면 자동으로 생성
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Pydantic 모델을 딕셔너리로 바꿔 DataFrame 생성
    dataframe = pd.DataFrame([product.model_dump() for product in valid_data])

    # CSV와 Parquet 파일 경로
    csv_path = output_dir / "products.csv"
    parquet_path = output_dir / "products.parquet"

    # 두 가지 형식으로 저장
    dataframe.to_csv(
        csv_path,
        index=False,
    )

    dataframe.to_parquet(
        parquet_path,
        index=False,
    )

    return dataframe


# Extract → Transform → Load 순서로 전체 과정 실행
async def run(product_ids):
    # 1. 비동기로 원본 데이터 수집
    raw_data = await extract(product_ids)

    # 2. 유효 데이터와 오염 데이터 분리
    valid_data, invalid_data = transform(raw_data)

    # 3. 유효 데이터를 CSV와 Parquet로 저장
    dataframe = load(valid_data)

    # 전체 실행 결과를 요약해서 반환
    return {
        "total": len(raw_data),
        "valid": len(valid_data),
        "invalid": len(invalid_data),
        "rows_saved": len(dataframe),
    }


# pipeline.py를 직접 실행했을 때만 동작
if __name__ == "__main__":
    # 1번부터 60번까지 총 60건 수집
    product_ids = list(range(1, 61))

    summary = asyncio.run(run(product_ids))

    print("=" * 45)
    print("비동기 ETL 파이프라인 실행 결과")
    print("=" * 45)
    print(f"전체 수집 : {summary['total']}건")
    print(f"유효 데이터: {summary['valid']}건")
    print(f"오염 데이터: {summary['invalid']}건")
    print(f"저장 데이터: {summary['rows_saved']}건")
