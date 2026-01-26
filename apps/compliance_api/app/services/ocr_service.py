# app/services/ocr_service.py
import httpx
import json
import uuid
import time
from app.core.config import settings

async def extract_text_from_image(file_content: bytes, filename: str):
    """
    Clova OCR API를 호출하여 텍스트와 Bounding Box를 추출합니다.
    """
    request_json = {
        "images": [
            {
                "format": filename.split('.')[-1].lower(), # jpg, png 등
                "name": filename,
                "data": None # file upload 방식이 아니라 base64가 아닐 경우 제외
            }
        ],
        "requestId": str(uuid.uuid4()),
        "version": "V2",
        "timestamp": int(time.time() * 1000)
    }

    # 파일 업로드를 위한 multipart/form-data 구성
    files = {
        'file': (filename, file_content)
    }
    
    headers = {
        'X-OCR-SECRET': settings.CLOVA_OCR_SECRET
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.CLOVA_INVOKE_URL,
            headers=headers,
            data={'message': json.dumps(request_json)},
            files=files,
            timeout=30.0
        )

    if response.status_code != 200:
        raise Exception(f"OCR Error: {response.text}")

    result = response.json()
    
    # 결과 파싱 (텍스트와 좌표 추출)
    parsed_data = []
    full_text = ""
    
    for image in result.get('images', []):
        for field in image.get('fields', []):
            text = field.get('inferText', '')
            # Clova 좌표: vertices [{'x': 1, 'y': 1}, ...] -> [x, y, w, h]로 변환 필요
            vertices = field.get('boundingPoly', {}).get('vertices', [])
            x = int(vertices[0]['x'])
            y = int(vertices[0]['y'])
            w = int(vertices[2]['x'] - x)
            h = int(vertices[2]['y'] - y)
            
            parsed_data.append({
                "text": text,
                "bbox": [x, y, w, h]
            })
            full_text += text + " "

    return full_text, parsed_data