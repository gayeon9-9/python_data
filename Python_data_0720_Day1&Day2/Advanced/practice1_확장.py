import tracemalloc


DATA_PATH = "data/web_logs.csv"


# 1. readlines 방식의 최대 메모리 측정
tracemalloc.start()

with open(DATA_PATH, encoding="utf-8") as file:
    lines = file.readlines()
    list_count = len(lines) - 1  # 헤더 제외

_, list_peak = tracemalloc.get_traced_memory()
tracemalloc.stop()

del lines


# 2. 제너레이터 방식의 최대 메모리 측정
tracemalloc.start()

with open(DATA_PATH, encoding="utf-8") as file:
    next(file)  # 헤더 제외
    generator_count = sum(1 for _ in file)

_, generator_peak = tracemalloc.get_traced_memory()
tracemalloc.stop()


# 3. 결과 출력
print("=" * 50)
print("readlines와 제너레이터 메모리 비교")
print("=" * 50)

print(f"readlines 방식 : {list_count:,}건")
print(f"최대 메모리    : {list_peak / 1024 / 1024:.2f} MB")

print(f"\n제너레이터 방식: {generator_count:,}건")
print(f"최대 메모리    : {generator_peak / 1024 / 1024:.2f} MB")

print(f"\n메모리 차이    : 약 {list_peak / generator_peak:.1f}배")
