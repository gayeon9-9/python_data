"""
종합실습 3 확장과제: 실무형 자동 보고서

[확장 이유]
기본 과제에서는 정해진 시각에 HTML 보고서를 자동 생성했다.
하지만 실무에서는 보고서를 보기 쉽게 만들고, 생성 사실을 알리며,
일시적인 데이터 오류가 발생해도 작업이 중단되지 않도록 해야 한다.

[확장 내용]
1. Plotly 임베드
   - 카테고리별 매출을 인터랙티브 그래프로 생성한다.
   - fig.to_html(full_html=False)를 사용해 기존 HTML에 삽입한다.

2. Slack 알림
   - 보고서 생성 후 경로와 주요 내용을 알림 메시지로 만든다.
   - 웹훅이 없으면 미리보기 파일로 저장하고, 있을 때만 실제 발송한다.

3. 지수 백오프 재시도
   - 데이터가 아직 생성되지 않았거나 일시적인 파일 오류가 발생할 경우
     1초, 2초처럼 대기시간을 늘리며 최대 3회 재시도한다.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import pandas as pd
import plotly.express as px


# 기존 Total3 모듈을 복사하지 않고 재사용하기 위한 경로 설정이다.
ADVANCED_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ADVANCED_DIR.parent
TOTAL3_DIR = PROJECT_DIR / "Total3"
OUTPUT_DIR = ADVANCED_DIR / "output"

sys.path.insert(0, str(TOTAL3_DIR))

from config import CONFIG  # noqa: E402
from report import aggregate_sales, clean_sales_data, generate_report  # noqa: E402


def generate_with_retry(max_attempts=3, base_delay=1, demo_retry=False):
    """
    보고서 생성에 실패하면 지수 백오프 방식으로 재시도한다.

    대기시간 계산:
    1차 실패 후 1초, 2차 실패 후 2초 대기한다.
    --demo-retry는 실제 데이터 파일을 손상시키지 않고 재시도를 확인하는 옵션이다.
    """

    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[보고서 생성] {attempt}/{max_attempts}차 시도")

            # 재시도 기능 확인용으로 앞의 두 시도에만 가상 오류를 발생시킨다.
            if demo_retry and attempt < max_attempts:
                raise OSError("재시도 확인을 위한 가상 데이터 오류")

            result = generate_report()
            print(f"✅ {attempt}차 시도에서 보고서 생성 성공")
            return result

        except (FileNotFoundError, OSError, pd.errors.ParserError) as error:
            if attempt == max_attempts:
                print("❌ 최대 재시도 횟수를 초과했습니다.")
                raise

            wait_seconds = base_delay * (2 ** (attempt - 1))
            print(f"⚠️ 생성 실패: {error}")
            print(f"{wait_seconds}초 후 다시 시도합니다.\n")
            time.sleep(wait_seconds)


def embed_plotly_chart(base_report_path):
    """카테고리별 매출 그래프를 기존 Jinja2 보고서에 삽입한다."""

    # 기존 Total3의 정제·집계 함수를 재사용해 결과의 일관성을 유지한다.
    raw_df = pd.read_csv(CONFIG.data_path)
    clean_df = clean_sales_data(raw_df)
    _, category_summary = aggregate_sales(clean_df)

    fig = px.bar(
        category_summary,
        x="category",
        y="total_sales",
        color="category",
        text_auto=".3s",
        title="카테고리별 매출 비교",
        labels={"category": "카테고리", "total_sales": "총매출"},
    )

    fig.update_layout(showlegend=False, template="plotly_white")

    # 전체 HTML이 아니라 그래프 부분만 만들어 기존 보고서에 삽입한다.
    chart_html = fig.to_html(full_html=False, include_plotlyjs=True)

    chart_section = (
        "<section class='table-box'>"
        "<h2>인터랙티브 카테고리 매출 차트</h2>"
        "<p>막대 위에 마우스를 올리면 정확한 매출액을 확인할 수 있습니다.</p>"
        f"{chart_html}</section>"
    )

    base_html = base_report_path.read_text(encoding="utf-8")
    advanced_html = base_html.replace("</body>", chart_section + "</body>")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_name = datetime.now().strftime("advanced_sales_report_%Y%m%d_%H%M%S.html")
    output_path = OUTPUT_DIR / output_name
    output_path.write_text(advanced_html, encoding="utf-8")

    print(f"✅ Plotly 차트 임베드 완료: {output_path}")
    return output_path


def send_slack_or_save_preview(report_path, raw_count, clean_count):
    """
    Slack 웹훅이 있으면 알림을 발송한다.

    웹훅이 없는 과제 실행환경에서는 메시지를 TXT 파일로 저장해
    어떤 알림이 발송되는지 안전하게 확인할 수 있도록 한다.
    """

    base_url = os.getenv("REPORT_BASE_URL")
    report_link = f"{base_url.rstrip('/')}/{report_path.name}" if base_url else str(report_path)

    message = (
        "📊 판매 데이터 자동 보고서가 생성되었습니다.\n"
        f"- 원본 데이터: {raw_count:,}행\n"
        f"- 정제 데이터: {clean_count:,}행\n"
        f"- 생성 시각: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
        f"- 보고서: {report_link}"
    )

    # 실제 발송 여부와 관계없이 채점자가 확인할 수 있도록 미리보기를 저장한다.
    preview_path = OUTPUT_DIR / "slack_notification_preview.txt"
    preview_path.write_text(message, encoding="utf-8")
    print(f"✅ Slack 알림 미리보기 저장: {preview_path}")

    webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    if not webhook_url:
        print("ℹ️ SLACK_WEBHOOK_URL이 없어 실제 발송은 생략했습니다.")
        print("\n[알림 미리보기]")
        print(message)
        return

    request = Request(
        webhook_url,
        data=json.dumps({"text": message}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            print(f"✅ Slack 알림 발송 완료: HTTP {response.status}")
    except URLError as error:
        # 알림 실패 때문에 이미 생성된 보고서까지 실패 처리하지 않는다.
        print(f"⚠️ Slack 발송 실패: {error}")


def main():
    parser = argparse.ArgumentParser(description="종합실습 3 확장 보고서")
    parser.add_argument(
        "--demo-retry",
        action="store_true",
        help="첫 두 번의 가상 오류로 지수 백오프 재시도를 확인",
    )
    args = parser.parse_args()

    print("===== 종합실습 3 확장: 실무형 자동 보고서 =====")

    # ① 실패 시 지수 백오프로 보고서 생성을 재시도한다.
    base_path, raw_count, clean_count = generate_with_retry(
        demo_retry=args.demo_retry
    )

    # ② 생성된 HTML에 Plotly 차트를 삽입한다.
    advanced_path = embed_plotly_chart(base_path)

    # ③ 보고서 생성 알림을 발송하거나 미리보기로 저장한다.
    send_slack_or_save_preview(advanced_path, raw_count, clean_count)

    print("\n✅ 종합실습 3 확장과제 완료")


if __name__ == "__main__":
    main()