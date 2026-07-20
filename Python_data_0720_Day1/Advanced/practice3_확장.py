## 확장 과제 : dead-letter 격리
import asyncio
import json
import time
from pathlib import Path


# 총 60건 처리
TOTAL_ITEMS = 60

# 동시에 최대 10건만 실행
MAX_CONCURRENT = 10

# 실패하면 최대 3번까지 시도
MAX_RETRIES = 3

# 네트워크 대기시간 모의 실행
MOCK_DELAY = 0.28

# ID 13을 의도적으로 계속 실패시킴
FAIL_ITEM_ID = 13

# 실패한 데이터를 저장할 파일 위치
# 현재 Advanced 폴더 안에 자동으로 생성됨
OUTPUT_PATH = Path(__file__).resolve().parent / "dead_letter.json"


# 데이터 한 건을 수집하는 함수
async def do_request(item_id):
    # ID 13은 재시도해도 계속 실패하도록 설정
    if item_id == FAIL_ITEM_ID:
        raise RuntimeError("의도적으로 발생시킨 수집 오류")

    # 나머지 데이터는 정상적으로 모의 수집
    await asyncio.sleep(MOCK_DELAY)

    return {
        "id": item_id,
        "ok": True,
    }


# 실패한 요청을 다시 시도하는 함수
async def fetch_retry(item_id, semaphore):
    for attempt in range(MAX_RETRIES):
        try:
            # 동시에 최대 10건만 실행
            async with semaphore:
                # 한 요청은 최대 3초까지만 기다림
                async with asyncio.timeout(3.0):
                    return await do_request(item_id)

        except (TimeoutError, RuntimeError):
            # 세 번째 시도까지 실패하면 최종 실패 처리
            if attempt == MAX_RETRIES - 1:
                raise

            # 첫 실패는 1초, 두 번째 실패는 2초 대기
            wait = 2**attempt

            print(f"ID {item_id} 실패 → {wait}초 후 재시도")

            await asyncio.sleep(wait)


# 전체 60건을 비동기로 실행
async def main():
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    tasks = [
        fetch_retry(item_id, semaphore)
        for item_id in range(TOTAL_ITEMS)
    ]

    # 한 건이 최종 실패해도 나머지 작업은 계속 실행
    return await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )


# 처리시간 측정 시작
start = time.perf_counter()

results = asyncio.run(main())

elapsed = time.perf_counter() - start


# 최종 실패한 데이터를 저장할 목록
dead_letters = []

# 결과의 순서와 item_id의 순서가 같으므로 enumerate로 함께 확인
for item_id, result in enumerate(results):
    if isinstance(result, Exception):
        dead_letters.append(
            {
                "id": item_id,
                "attempts": MAX_RETRIES,
                "error_type": type(result).__name__,
                "error": str(result),
            }
        )


# 최종 실패 목록을 JSON 파일로 저장
OUTPUT_PATH.write_text(
    json.dumps(
        dead_letters,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


# 결과 출력
print("=" * 50)
print("dead-letter 격리 결과")
print("=" * 50)
print(f"전체 처리   : {len(results)}건")
print(f"성공        : {len(results) - len(dead_letters)}건")
print(f"최종 실패   : {len(dead_letters)}건")
print(f"처리 시간   : {elapsed:.2f}초")
print(f"저장 파일   : {OUTPUT_PATH}")