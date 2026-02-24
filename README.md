# AI 기반 협력사 리스크 관리 플랫폼 — AI 서비스

> **KT AIVLE School 8기 빅프로젝트** | 수도권 5반 10조
>
> **"Beyond Blue, Forward to Green"** — HD현대중공업 협력사의 안전/컴플라이언스/ESG 문서(PDF, XLSX, 이미지)를 자동으로 분류·검증하고, 규칙 기반 검증 + LLM 분석을 결합해 verdict(판정) 및 risk level(위험도)을 산출하는 Stateless FastAPI 시스템입니다.

---

## 과제 선정 배경

| # | 배경 | 내용 |
|---|------|------|
| 1 | **중대재해처벌법 전면 확대** | 2024년 전 사업장 적용, 2025년 위험성평가 인정기준 70점→90점 상향 |
| 2 | **하도급법 개정 및 공정위 단속** | 2025년 3월 개정안 통과, 부당특약 무효화 근거 마련 |
| 3 | **EU CSDDD 글로벌 공급망 실사** | 원청기업 공급망 인권·환경 리스크 관리가 법적 의무로 전환 |

단순 체크리스트 자가진단을 넘어, **실질적 증빙 데이터 기반의 객관적 실사 체계**가 필수적인 환경에서 본 플랫폼을 개발했습니다.

---

## 전체 서비스 레포지토리

| 파트 | 레포지토리 | 기술 스택 |
|------|-----------|----------|
| **AI (본 레포)** | SmartChain-HD/smartchainAI | Python, FastAPI, OpenAI, YOLO |
| **Backend** | [SmartChain-HD/Backend](https://github.com/SmartChain-HD/Backend) | Java 17, Spring Boot 3.2, PostgreSQL |
| **Frontend** | [SmartChain-HD/Frontend](https://github.com/SmartChain-HD/Frontend) | React 18, TypeScript, Tailwind CSS v4 |

---

## 팀 구성 (Contributors)

| 역할 | 이름 | GitHub | 주요 담당 |
|------|------|--------|----------|
| **PM / 조장** | **이종헌** | [![jjongjjongR](https://img.shields.io/badge/jjongjjongR-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/jjongjjongR) | AI(ESG), Infra |
| **인프라 리더** | **이수오** | — | Infra, Azure |
| **풀스택 리더** | **진지현** | — | FE, BE |
| **FE/BE** | **김건우** | — | FE, BE, Infra |
| **FE/BE** | **박세용** | — | FE, BE |
| **AI 파트 리더** | **이수빈** | [![leesupin](https://img.shields.io/badge/leesupin-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/leesupin) | AI(안전보건) |
| **AI Developer** | **배수한** | [![uh004](https://img.shields.io/badge/uh004-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/uh004) | AI(컴플라이언스) |

---

## 서비스 권한 구조

```
게스트 → 기안자(협력사 작성) → 결재자(협력사 팀장) → 수신자(원청 HD현대)
```

| 권한 | 역할 | 핵심 기능 |
|------|------|----------|
| **게스트** | 접근 권한 신청 | 회사명/역할 입력 → 대기/승인/반려 상태 확인 |
| **기안자** | 협력사 작성 직원 | 문서 업로드 → AI Preview(분류/누락 탐지) → Submit(6단계 파이프라인) |
| **결재자** | 협력사 팀장 | 검증 결과 요약 확인 → 승인/반려 결재 |
| **수신자** | 원청(HD현대) 담당자 | 심사 대시보드 조회 → 보완요청 자동 생성 → 최종 판정 |

---

## Tech Stack (AI 서비스)

![Python](https://img.shields.io/badge/Python-3.10-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)
![YOLO](https://img.shields.io/badge/YOLO26n-00FFFF?style=for-the-badge&logoColor=black)
![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6F00?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Azure](https://img.shields.io/badge/Azure-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white)

| 구분 | 기술 |
|------|------|
| Framework | FastAPI + Uvicorn |
| LLM (Light) | OpenAI GPT-4o-mini — PDF/XLSX 텍스트 보강, Clarification 생성 |
| LLM (Heavy) | OpenAI GPT-5.1 — Vision 이미지 분석, 슬롯별 verdict 종합, 최종 판정 |
| Object Detection | YOLO26n (CrowdHuman Few-shot, 현장 인원수 감지) |
| OCR | Naver Clova OCR V2 (한국어 최적화, 96.4% 정확도) |
| Vector DB | ChromaDB (RAG 기반 검색) |
| 파싱 | PyMuPDF (PDF), pandas + openpyxl (XLSX/CSV) |
| HTTP | httpx (비동기 다운로드/OCR 호출) |
| 검증 | Pydantic v2 스키마 |
| 외부 검색 | GDELT API, Google News RSS |
| 인프라 | Azure Container Apps, Docker |

---

## 전체 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                   Azure Container Apps                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │sc-frontend│  │sc-backend│  │sc-ai-run │  │sc-chatbot│ │
│  │  (React) │  │(SpringBoot│  │  -api    │  │  -api   │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│                              ┌──────────────────────────┐ │
│                              │    sc-ai-out-risk-api    │ │
│                              └──────────────────────────┘ │
│                 Azure Load Balancer / Application Gateway  │
│                 Azure PostgreSQL / Key Vault / ACR        │
└─────────────────────────────────────────────────────────┘
```

### AI 서비스 내부 구조

```
apps/
├── ai_run_api/      [메인] 협력사 문서 자동 검증 엔진    (포트 8000)
├── chatbot_api/     [서브] 컴플라이언스 규정 Q&A 챗봇   (포트 8001)
└── out_risk_api/    [서브] 외부 뉴스 기반 ESG 리스크 분석 (포트 8002)
```

---

## [메인] ai_run_api — 협력사 문서 자동 검증

### 검증 도메인

| 도메인 | 증빙 문서 | 정형 데이터 |
|--------|----------|------------|
| **컴플라이언스** | 근로계약서, 교육출석부, 컴플라이언스 교육, 부정부패 관련 문서 | 개인정보 교육 이수 현황, 공정거래 점검표 |
| **안전보건** | 안전보건관리체계 구축매뉴얼, 소방시설 점검결과표, 현장사진, 교육출석부 | 안전교육 이수 현황, 위험성평가서 |
| **ESG** | ISO45001, 이사회 관련 사항, 윤리강령, 도시가스/수도/전기 고지서 | 윤리강령 배포 로그, 유해물질 목록, 에너지 사용량 |

### 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/health` | 서버 상태 확인 |
| `POST` | `/run/preview` | 파일 분류 + 슬롯 추정 (제출 전 누락 탐지) |
| `POST` | `/run/submit` | 6단계 파이프라인 실행 → verdict + risk_level 반환 |

### Submit 파이프라인 (6단계)

```
(1) TRIAGE        파일 분류 — 확장자/MIME 판별, 열 수 있는지 체크
        ↓
(2) SLOT APPLY    slot_hint 적용 — 파일을 도메인 슬롯에 매핑
        ↓
(3) EXTRACT       파싱/OCR — PDF→텍스트, XLSX→DataFrame, 이미지→OCR+Vision+YOLO
        ↓
(4) VALIDATE      룰 검증 — validators.py 규칙 + LLM 이상탐지 → reasons 도출
        ↓
(4.5) CROSS       교차 검증 — 슬롯 간 1:1 비교 (예: 출석부 인원 vs 현장사진 인원)
        ↓
(5) CLARIFY       보완요청 생성 — PASS가 아닌 슬롯에 대해 한국어 안내문 자동 작성
        ↓
(6) JUDGE FINAL   최종 집계 — 전체 verdict + risk_level + why 산출
```

### Verdict & Risk Level 기준

**Verdict (슬롯 단위)**

| Verdict | 의미 | 조건 |
|---------|------|------|
| **NEED_FIX** | 파일 자체 문제 (분석 불가) | MISSING_SLOT, PARSE_FAILED, HEADER_MISMATCH 등 |
| **NEED_CLARIFY** | 내용 문제 (분석 완료, 이슈 발견) | VIOLATION_DETECTED, LOW_EDUCATION_RATE 등 |
| **PASS** | 이상 없음 | reason 없음 |

**Risk Level (업체 단위 집계)**

| Risk Level | 조건 |
|------------|------|
| **HIGH** | 하나라도 NEED_FIX가 있음 |
| **MEDIUM** | NEED_FIX 없음, Safety/Compliance에 NEED_CLARIFY 있음 |
| **LOW** | 모두 PASS 또는 ESG 도메인에만 NEED_CLARIFY |

### 디렉토리 구조

```
apps/ai_run_api/app/
├── main.py                 # FastAPI 진입점 + /health
├── api/run.py              # POST /run/preview, /run/submit
├── schemas/run.py          # Pydantic 스키마
├── pipeline/               # Preview, Triage, Submit 파이프라인
├── engines/                # 도메인별 검증 로직 (safety/compliance/esg)
├── extractors/             # PDF, XLSX, OCR, YOLO 추출기
├── llm/                    # LLM 클라이언트 + 프롬프트
├── storage/                # 다운로더, 임시 저장소
└── core/                   # 설정, 에러 처리
```

---

## [서브] chatbot_api — 컴플라이언스 Q&A 챗봇

사내 컴플라이언스 규정 문서를 벡터DB(ChromaDB)에 저장하고, RAG 기반으로 질문에 답변합니다.

### 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/health` | 서버 상태 확인 |
| `POST` | `/chat` | 사용자 질문 → RAG 기반 답변 |
| `POST` | `/admin/upload` | 규정 문서 업로드 (관리자용, API Key 필요) |

### 디렉토리 구조

```
apps/chatbot_api/app/
├── main.py                 # FastAPI 진입점
├── api/chat.py             # 채팅 엔드포인트
├── api/admin.py            # 관리자 문서 업로드
├── rag/                    # ChromaDB + RAG 로직
├── core/config.py          # pydantic-settings 기반 설정
└── vectordb/               # ChromaDB 저장 경로 (gitignore)
```

---

## [서브] out_risk_api — 외부 리스크 분석

협력사명으로 GDELT/RSS 뉴스를 검색하고, ESG 키워드 기반 감정 분석으로 외부 리스크 점수를 산출합니다.

### 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/health` | 서버 상태 확인 |
| `POST` | `/risk/external/detect` | 협력사 리스트 → 외부 리스크 분석 |
| `POST` | `/risk/external/search/preview` | 검색 결과 미리보기 |

### 리스크 산출 방식

1. 협력사명으로 GDELT API / Google RSS 검색
2. ESG 키워드 필터링 (사고, 환경오염, 법적 분쟁 등)
3. 감정 분석으로 부정 문서 분류
4. 문서 발행일 기준 가중치 적용 (최근 30일: 1.5x, 90일: 1.0x, 180일: 0.7x)
5. 총점 기반 리스크 레벨 산출 (HIGH ≥10, MEDIUM ≥5, LOW <5)

### 디렉토리 구조

```
apps/out_risk_api/app/
├── main.py                 # FastAPI 진입점
├── api/risk.py             # 리스크 분석 엔드포인트
├── pipeline/detect.py      # 검색 → 분석 → 점수화 파이프라인
├── search/                 # GDELT, RSS 검색 프로바이더
├── analyze/sentiment.py    # 감정 분석 (키워드 기반)
├── rag/                    # ChromaDB 연동 (선택적 RAG)
└── core/config.py          # 환경변수 설정
```

---

## AI 모델 전략

| 모델 | 용도 | 최종 성능 |
|------|------|----------|
| **GPT-4o-mini** (Light) | PDF/XLSX 텍스트 보강, Clarification 생성 | JSON 파싱 성공률 기준 운영 요구 수준 충족 |
| **GPT-5.1** (Heavy) | Vision 이미지 분석, 슬롯별 verdict 종합, 최종 risk level 산출 | Accuracy 0.75, Recall 0.71 (GPT-4o 0.60 대비 우위) |
| **Naver Clova OCR V2** | 이미지 → 텍스트 변환 (한국어 최적화) | 정확도 96.4%, 처리속도 장당 1.2초 |
| **YOLO26n** (CrowdHuman Few-shot) | 현장 사진 인원수 감지 | Count Accuracy 80.2%, MAE 4.42 (파인튜닝 후 50.6% 개선) |
| **text-embedding-3-small** | RAG 임베딩 (chatbot_api) | — |

---

## 기대 효과 (KPI)

| 지표 | As-Is | To-Be |
|------|-------|-------|
| 1개사 검증 리드타임 | 0.5~2일 | **10~30분** 내 1차 판정 |
| 재제출 왕복 횟수 | 2~4회 | **1~2회** |
| 형식 오류 자동 검출률 | 사람 의존 | **95%+** 목표 |
| 담당자 집중 검토 범위 | 전체 파일 | **이슈 슬롯만 (20~40%)** |

---

## 실행 방법

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
# .env 파일 편집하여 API 키 등 설정
```

### 3. 서버 실행

```bash
# ai_run_api (메인) - 포트 8000
uvicorn app.main:app --reload --port 8000 --app-dir apps/ai_run_api

# chatbot_api (서브) - 포트 8001
uvicorn app.main:app --reload --port 8001 --app-dir apps/chatbot_api

# out_risk_api (서브) - 포트 8002
uvicorn app.main:app --reload --port 8002 --app-dir apps/out_risk_api
```

### 4. Streamlit 테스트 UI (선택)

```bash
# ai_run_api UI
streamlit run apps/ai_run_api/app/ui/streamlit_app.py

# chatbot_api UI
streamlit run apps/chatbot_api/app/ui/streamlit_app.py

# out_risk_api UI
streamlit run apps/out_risk_api/app/ui/streamlit_app.py
```

---

## 환경변수 (.env)

```env
# === 공통 ===
OPENAI_API_KEY="사용자지정"

# === ai_run_api ===
CLOVA_INVOKE_URL="사용자지정"
CLOVA_OCR_SECRET="사용자지정"
OPENAI_MODEL_LIGHT="gpt-4o-mini"
OPENAI_MODEL_HEAVY="gpt-5.1"

# === chatbot_api ===
OPENAI_EMBEDDING_MODEL="text-embedding-3-small"
CHATBOT_CHROMA_PATH="apps/chatbot_api/app/vectordb"
CHATBOT_CHROMA_COLLECTION="hd_hhi_compliance_kb"
ADMIN_API_KEY="사용자지정"

# === out_risk_api ===
OUT_RISK_CHROMA_PATH="apps/out_risk_api/app/vectordb"
OUT_RISK_CHROMA_COLLECTION="hd_hhi_out_risk_kb"
```

---

## 개발 참고

본 프로젝트는 초기 기획 단계에서 생성형 AI(Claude)를 활용해 개념적 구조와 로직 정리의 초안을 참고했으며, 실제 판단 기준의 구체화, 알고리즘 설계, FastAPI 구현 및 운영 로직은 모두 팀 내부에서 직접 설계·개발했습니다.
