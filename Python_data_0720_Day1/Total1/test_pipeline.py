# pytest 테스트 6개
import pandas as pd
from pipeline import load, transform


# 카테고리의 공백이 제거되고 소문자로 바뀌는지 확인
def test_category_lowercase():
    raw_data = [
        {
            "id": 1,
            "name": "Apple",
            "category": " FOOD ",
            "price": 1000,
        }
    ]

    valid, invalid = transform(raw_data)

    assert valid[0].category == "food"
    assert len(invalid) == 0


# 음수 가격이 오염 데이터로 분리되는지 확인
def test_negative_price_rejected():
    raw_data = [
        {
            "id": 2,
            "name": "Laptop",
            "category": "electronics",
            "price": -5000,
        }
    ]

    valid, invalid = transform(raw_data)

    assert len(valid) == 0
    assert len(invalid) == 1


# 입력한 전체 건수와 검증 결과의 건수가 같은지 확인
def test_valid_invalid_count():
    raw_data = [
        {
            "id": 1,
            "name": "Apple",
            "category": "food",
            "price": 1000,
        },
        {
            "id": 2,
            "name": "Laptop",
            "category": "electronics",
            "price": 5000,
        },
        {
            "id": 3,
            "name": "Error",
            "category": "etc",
            "price": -100,
        },
    ]

    valid, invalid = transform(raw_data)

    assert len(valid) + len(invalid) == len(raw_data)
    assert len(valid) == 2
    assert len(invalid) == 1

    ## -----------
    # 필수 항목인 name이 없으면 오염 데이터로 분리되는지 확인


def test_missing_field_rejected():
    raw_data = [
        {
            "id": 1,
            "category": "food",
            "price": 1000,
        }
    ]

    valid, invalid = transform(raw_data)

    assert len(valid) == 0
    assert len(invalid) == 1


# CSV와 Parquet 파일이 모두 생성되는지 확인
def test_load_creates_files(tmp_path):
    raw_data = [
        {
            "id": 1,
            "name": "Apple",
            "category": "food",
            "price": 1000,
        }
    ]

    valid, _ = transform(raw_data)

    dataframe = load(valid, tmp_path)

    assert len(dataframe) == 1
    assert (tmp_path / "products.csv").exists()
    assert (tmp_path / "products.parquet").exists()


# Parquet 저장 후 다시 읽어도 데이터가 같은지 확인
def test_parquet_roundtrip(tmp_path):
    raw_data = [
        {
            "id": 1,
            "name": "Apple",
            "category": "food",
            "price": 1000,
        },
        {
            "id": 2,
            "name": "Laptop",
            "category": "electronics",
            "price": 5000,
        },
    ]

    valid, _ = transform(raw_data)

    original = load(valid, tmp_path)
    loaded = pd.read_parquet(tmp_path / "products.parquet")

    pd.testing.assert_frame_equal(
        original,
        loaded,
    )
