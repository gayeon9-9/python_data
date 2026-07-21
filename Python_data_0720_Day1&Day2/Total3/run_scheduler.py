"""
종합실습 3 - STEP 5~7. 보고서 자동 실행

STEP 5. --once: 보고서를 한 번 생성
STEP 6. --interval: 지정한 초마다 반복 생성
STEP 7. --daily: schedule 라이브러리로 매일 지정 시각 실행
추가로 --show-cron을 사용하면 운영환경용 cron 명령을 확인할 수 있다.
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from config import CONFIG
from report import generate_report


def run_job():
    """스케줄러가 공통으로 호출하는 보고서 생성 작업."""

    print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] 보고서 생성을 시작합니다.")
    output_path, raw_count, clean_count = generate_report()

    print(f"원본 데이터: {raw_count:,}행")
    print(f"정제 데이터: {clean_count:,}행")
    print(f"보고서 저장: {output_path}")
    print("✅ 보고서 생성 작업 완료")

    return output_path


def run_interval(seconds):
    """외부 라이브러리 없이 지정한 초마다 반복 실행한다."""

    if seconds <= 0:
        raise ValueError("반복 주기는 1초 이상이어야 합니다.")

    print(f"경량 루프 실행: {seconds}초마다 보고서를 생성합니다.")
    print("종료하려면 Control + C를 누르세요.")

    while True:
        run_job()
        time.sleep(seconds)


def run_daily(run_time):
    """schedule 라이브러리를 이용해 매일 지정 시각에 실행한다."""

    try:
        import schedule
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError(
            "schedule 설치가 필요합니다: pip install schedule"
        ) from error

    schedule.every().day.at(run_time).do(run_job)

    print(f"schedule 실행: 매일 {run_time}에 보고서를 생성합니다.")
    print("종료하려면 Control + C를 누르세요.")

    while True:
        schedule.run_pending()
        time.sleep(1)


def show_cron_example():
    """현재 가상환경과 파일 경로를 반영한 cron 등록 예시를 보여준다."""

    CONFIG.output_dir.mkdir(parents=True, exist_ok=True)
    script_path = Path(__file__).resolve()
    log_path = CONFIG.output_dir / "cron.log"

    print("매일 오전 9시에 실행하는 cron 등록 예시입니다.")
    print(f"0 9 * * * {sys.executable} {script_path} --once >> {log_path} 2>&1")


def main():
    parser = argparse.ArgumentParser(description="판매 분석 보고서 자동 생성기")
    group = parser.add_mutually_exclusive_group()

    group.add_argument("--once", action="store_true", help="보고서를 한 번 생성")
    group.add_argument("--interval", type=int, metavar="초", help="지정한 초마다 반복 생성")
    group.add_argument("--daily", metavar="HH:MM", help="매일 지정 시각에 생성")
    group.add_argument("--show-cron", action="store_true", help="cron 등록 예시 출력")

    args = parser.parse_args()

    if args.interval is not None:
        run_interval(args.interval)
    elif args.daily:
        run_daily(args.daily)
    elif args.show_cron:
        show_cron_example()
    else:
        # 옵션이 없거나 --once를 입력하면 한 번만 실행한다.
        run_job()


if __name__ == "__main__":
    main()
    