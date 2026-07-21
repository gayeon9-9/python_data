"""
종합실습 3 - STEP 1. 설정 모듈

데이터 경로, 템플릿 경로, 출력 경로처럼 자주 바뀔 수 있는 설정을
분석 코드와 분리한다. frozen=True를 사용해 실행 중 설정이 실수로
변경되지 않도록 보호한다.
"""

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOTAL3_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ReportConfig:
    """보고서 생성에 필요한 공통 설정."""

    title: str = "판매 데이터 자동 분석 보고서"
    data_path: Path = PROJECT_ROOT / "data" / "sales_raw.csv"
    template_dir: Path = TOTAL3_DIR / "templates"
    template_name: str = "report.html"
    output_dir: Path = TOTAL3_DIR / "output"
    default_interval_seconds: int = 60


CONFIG = ReportConfig()