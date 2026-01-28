# 🤖 AI 기반 스마트 진단 및 자동 리포팅 시스템

본 프로젝트는 OCR 기술과 대형 언어 모델(LLM)을 결합하여 데이터 유효성 검증부터 지표화, 
<br>그리고 최종 리포트 생성까지 수행하는 통합 AI 솔루션입니다.

---

## 👥 프로젝트 팀 구성 (Contributors)

프로젝트를 이끄는 핵심 인력 및 역할 분담 현황입니다.

| 역할 | 이름 | GitHub Profile | 주요 담당 기능 |
| :--- | :--- | :--- | :--- |
| **PM / 조장** | **이종헌** | [![jjongjjongR's GitHub](https://img.shields.io/badge/jjongjjongR-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/jjongjjongR) | ESG |
| **AI 파트 리더** | **이수빈** | [![leesupin's GitHub](https://img.shields.io/badge/leesupin-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/leesupin) | 안전-보건 |
| **AI Developer** | **배수한** | [![uh004's GitHub](https://img.shields.io/badge/uh004-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/uh004) | 컴플라이언스 |

---
## 🛠 기술 스택 및 도구 (Tech Stack & Tools)
Language: Python 3.10
Framework: FastAPI

AI Pair-Programmer: Anthropic Claude 3.5 Sonnet (코드 구조 제안 및 유닛 테스트 생성 보조)

🤖 AI Collaboration Statement (AI 협업 선언)
이 프로젝트는 개발 생산성 향상을 위해 AI와 협업하여 제작되었습니다.
AI 기여 영역: 초기 API 스켈레톤 생성, 반복적인 데이터 파싱 로직 구현.
팀원의 기여 영역: 데이터베이스 스키마 설계, 보안 인증(JWT) 로직 구현, AI 생성 코드의 오류 수정 및 성능 튜닝.
검증 과정: 모든 AI 생성 코드는 직접 한 줄씩 검토(Line-by-line review)하였으며, 프로젝트의 컨벤션에 맞게 리팩토링되었습니다.

📈 학습 및 성장 포인트 (Key Learnings)
AI가 제안한 Async/Await 패턴의 원리를 분석하며 비동기 프로그래밍의 깊은 이해를 얻음.
AI의 할루시네이션(잘못된 라이브러리 추천)을 직접 해결하며 공식 문서(Documentation)를 교차 검증하는 습관을 형성함.


## 🛠 AI 시스템 아키텍처 및 파이프라인

전체 프로세스는 3개의 핵심 FastAPI 서버를 통해 유기적으로 동작합니다.

### 1️⃣ Data Acquisition & Preprocessing (OCR / Parsing)
* **OCR 연동**: Naver Clova OCR을 통한 이미지 텍스트 추출 (배수한)
* **데이터 파싱**: 자료 Parsing 및 추출된 데이터의 구조화 및 전처리 (이수빈, 이종헌)

### 2️⃣ Validation & Metric Calculation (FastAPI #1)
* **유효성 검증**:
  * **정형 데이터**: 통계적 수치 기반 검증 로직 (이종헌)
  * **비정형 데이터**: 논리성 검증 (배수한)
* **지표화 (AI)**: 검증된 데이터를 바탕으로 정량적 핵심 지표 산출 (이수빈)

### 3️⃣ Automated Reporting (FastAPI #2)
* **진단표 생성 (AI)**: 항목별 위험 점수 및 진단 결과 도출 (배수한)
* **보고서 생성 (AI)**: 고위험군 분석 및 대응 가이드라인 자동 기술 (이종헌)

### 4️⃣ Field Inspection Optimization (FastAPI #3)
* **현장 실사 체크리스트 (AI)**: 지능형 현장 실사 체크리스트 생성 및 사후 검토 (이수빈)

---

## 💻 Tech Stack
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white)
