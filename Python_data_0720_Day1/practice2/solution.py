import json
from datetime import date

from pydantic import BaseModel, Field, ValidationError, field_validator


# STEP 1~4: 사용자 데이터 검증 모델
class Profile(BaseModel):
    country: str
    tier: str
    score: float = Field(ge=0, le=100)


class User(BaseModel):
    id: int
    username: str
    email: str
    age: int = Field(ge=0, le=120)
    is_active: bool
    signup_date: date
    profile: Profile
    tags: list[str] = []

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        # 이메일의 앞뒤 공백 제거 및 소문자화
        value = value.strip().lower()

        # 이메일 형식 검사
        if "@" not in value:
            raise ValueError("올바른 이메일 형식이 아닙니다")

        return value


# STEP 0: JSON 구조 확인 결과에 맞게 데이터 불러오기
with open("data/api_response.json", encoding="utf-8") as file:
    payload = json.load(file)

# 실제 사용자 40건은 results 안에 있음
data = payload["results"]


# STEP 5: 유효 데이터와 오염 데이터 분리
valid = []
invalid = []

for i, row in enumerate(data):
    try:
        valid.append(User.model_validate(row))

    except ValidationError as error:
        invalid.append(
            {
                "index": i,
                "id": row.get("id"),
                "data": row,
                "errors": error.errors(),
            }
        )


# 검증 결과 출력
print("=" * 65)
print("Pydantic 사용자 데이터 검증 결과")
print("=" * 65)
print(f"전체 {len(data)}건 → 유효 {len(valid)}건 / 오염 {len(invalid)}건")


# STEP 6: 오염 데이터의 실패 사유 출력
print("\n[오염 데이터 실패 사유]")
print(f"{'행':<4}{'ID':<6}{'필드':<18}사유")
print("-" * 65)

for item in invalid:
    for error in item["errors"]:
        field = ".".join(str(value) for value in error["loc"])

        print(
            f"{item['index'] + 1:<4}"
            f"{item['id']:<6}"
            f"{field:<18}"
            f"{error['msg']}"
        )