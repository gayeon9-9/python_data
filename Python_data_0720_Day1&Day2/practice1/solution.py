# 데이터의 앞 5줄 확인
with open("data/web_logs.csv", encoding="utf-8") as file:
    for i, line in enumerate(file):
        print(line.strip())

        if i >= 4:
            break

import csv
from collections import Counter
from functools import reduce


def read_logs(path):
    # 파일을 한 줄씩 읽는 제너레이터
    with open(path, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            yield row


def fold(result, row):
    # 기존 결과에 로그 한 건을 누적
    result["total"] += 1
    result["status"][row["status"]] += 1
    result["path"][row["path"]] += 1
    result["hour"][row["timestamp"][11:13]] += 1
    result["ip"][row["ip"]] += 1

    return result


initial = {
    "total": 0,
    "status": Counter(),
    "path": Counter(),
    "hour": Counter(),
    "ip": Counter(),
}

# 제너레이터를 한 번만 순회하면서 모든 항목 누적
result = reduce(
    fold,
    read_logs("data/web_logs.csv"),
    initial,
)

error_5xx = sum(
    count
    for status, count in result["status"].items()
    if status.startswith("5")
)

error_ratio = error_5xx / result["total"] * 100

print("=" * 55)
print("대용량 웹 로그 스트리밍 집계 결과")
print("=" * 55)
print(f"총 요청 수 : {result['total']:,}건")
print(f"5xx 오류율 : {error_5xx:,}건 ({error_ratio:.3f}%)")

print("\n[상태코드별 요청 수]")
for status, count in sorted(result["status"].items()):
    print(f"{status}: {count:,}건")

print("\n[인기 경로 TOP 5]")
for path, count in result["path"].most_common(5):
    print(f"{path:<20} {count:>7,}건")

print("\n[시간대별 요청 수]")
hours = sorted(result["hour"].items())

for i in range(0, len(hours), 4):
    line = " | ".join(
        f"{hour}시 {count:,}건"
        for hour, count in hours[i : i + 4]
    )
    print(line)

print("\n[접속 상위 IP TOP 5]")
for ip, count in result["ip"].most_common(5):
    print(f"{ip:<18} {count:>3,}건")
    