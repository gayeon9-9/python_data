# Pydantic 모델 (실습 2 재사용)
from pydantic import BaseModel, Field, field_validator


# 수집한 상품 데이터를 검증할 모델
class Product(BaseModel):
    id: int
    name: str
    category: str
    price: float = Field(gt=0)

    # 카테고리의 공백을 제거하고 소문자로 통일
    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        value = value.strip().lower()

        # 카테고리가 비어 있으면 검증 실패
        if not value:
            raise ValueError("category는 비어 있을 수 없습니다")

        # 정리한 값을 반드시 반환
        return value
