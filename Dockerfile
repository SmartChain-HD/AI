FROM python:3.9-slim
WORKDIR /app
COPY . .
# 에러가 났던 RUN pip install 줄을 삭제하거나 앞에 #을 붙여 주석 처리합니다.
# RUN pip install -r requirements.txt 
CMD ["python", "main.py"]
