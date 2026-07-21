import asyncio
import time

import httpx


# 실제 인터넷 요청을 사용할지 정하는 값
# 과제에서는 인터넷 없이 실행하기 위해 False로 설정
USE_REAL_HTTP = False

TOTAL_ITEMS = 60 # 총 60건의 데이터를 수집
MAX_CONCURRENT = 10 # 한 번에 실행할 수 있는 요청은 최대 10건
MAX_RETRIES = 3 # 요청이 실패하면 최대 3번까지 시도
MOCK_DELAY = 0.28 # 실제 네트워크 응답을 기다리는 상황을 0.28초로 모의 실행
TIMEOUT_SECONDS = 3.0 # 요청 하나가 3초를 넘으면 타임아웃 처리


# 데이터 한 건을 가져오는 함수
async def do_request(item_id, client):
    # True일 때만 실제 인터넷에 요청
    if USE_REAL_HTTP:
        url = f"https://jsonplaceholder.typicode.com/todos/{item_id + 1}"

        
        response = await client.get(url) # httpx의 비동기 클라이언트로 요청
        response.raise_for_status() # 400, 500번대 오류가 발생하면 예외 발생
        data = response.json() # 받은 JSON 데이터를 파이썬 데이터로 변환

    else:
        # False이면 실제 인터넷 요청 대신
        # 0.28초 동안 기다리면서 네트워크 상황을 모의 실행
        await asyncio.sleep(MOCK_DELAY)

        data = {
            "message": "mock response",
        }

    return {
        "id": item_id,
        "ok": True,
        "data": data,
    }


# 요청이 실패할 경우 다시 시도하는 함수
async def fetch_retry(item_id, semaphore, client):
    # 최대 3번까지 반복해서 요청
    for attempt in range(MAX_RETRIES):
        try:
            # Semaphore를 이용해 동시에 최대 10건만 실행
            async with semaphore:
                # 요청 하나당 최대 3초까지만 기다림
                async with asyncio.timeout(TIMEOUT_SECONDS):
                    return await do_request(item_id, client)

        # 타임아웃 또는 HTTP 오류가 발생한 경우
        except (TimeoutError, httpx.HTTPError):
            if attempt == MAX_RETRIES - 1: # 마지막 시도까지 실패했다면 더 이상 재시도하지 않음
                raise

            # 실패할 때마다 대기시간을 2배씩 증가
            # 첫 번째 실패는 1초, 두 번째 실패는 2초 대기
            wait = 2**attempt

            print(f"ID {item_id} 실패 → {wait}초 후 재시도")

            # time.sleep이 아니라 asyncio.sleep을 사용해야
            # 다른 비동기 작업이 멈추지 않음
            await asyncio.sleep(wait)


# 전체 비동기 작업을 실행하는 함수
async def main():
    # 동시에 실행할 수 있는 요청을 10건으로 제한
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    # requests가 아닌 비동기용 httpx.AsyncClient 사용
    async with httpx.AsyncClient() as client:
        # 0번부터 59번까지 총 60개의 작업 생성
        tasks = [
            fetch_retry(item_id, semaphore, client)
            for item_id in range(TOTAL_ITEMS)
        ]

        # 생성한 60개의 작업을 동시에 실행하고 결과 수집
        # 한 건이 실패해도 전체 작업이 중단되지 않도록 return_exceptions=True로 설정
        results = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

    return results


# 실행시간을 계산하기 위해 시작시간 저장
start = time.perf_counter()

# 비동기 main 함수 실행
results = asyncio.run(main())

# 전체 처리시간 계산
elapsed = time.perf_counter() - start


# 예외가 아닌 결과는 성공 목록에 저장
success = [
    result
    for result in results
    if not isinstance(result, Exception)
]

# 예외가 발생한 결과는 실패 목록에 저장
failure = [
    result
    for result in results
    if isinstance(result, Exception)
]


# 최종 결과 출력
print("=" * 45)
print("asyncio 비동기 수집 결과")
print("=" * 45)

# 현재 실제 HTTP가 아니라 모의 실행 중인지 표시
print(f"실행 방식     : {'실제 HTTP' if USE_REAL_HTTP else '모의 실행'}")

print(f"전체 처리     : {len(results)}건")
print(f"성공          : {len(success)}건")
print(f"실패          : {len(failure)}건")
print(f"최대 동시 실행: {MAX_CONCURRENT}건")
print(f"최대 재시도   : {MAX_RETRIES}회")
print(f"처리 시간     : {elapsed:.2f}초")