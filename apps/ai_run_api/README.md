# 함수 이름은 각 도메인 명으로 시작할 것. 
# preview / submit으로 나뉨

AI/apps/ai_run_api/
├─ app/
│  ├─ main.py
│  ├─ api.py 
│  ├─ schemas.py
│  ├─ core/
│  │  ├─ config.py
│  │  └─ errors.py 
│  ├─ services/
│  │  ├─ file_fetcher.py
│  │  ├─ slot_suggester.py
│  │  ├─ required_slots.py
│  │  ├─ preview_service.py
│  │  └─ submit_service.py
│  ├─ domains/
│  │  ├─ safety.py
│  │  ├─ compliance.py
│  │  └─ esg.py
│  ├─ integrations/
│  │  ├─ clova_ocr.py
│  │  ├─ llm_client.py
│  │  └─ rag_chroma.py
│  └─ store/
│     ├─ package_store.py
│     └─ memory_store.py 
├─ ui/
│  └─ streamlit_app.py
├─ scripts/
│  └─ demo_run.sh
├─ docs/
│  └─ output_schema.md
├─ requirements.txt
└─ README.md