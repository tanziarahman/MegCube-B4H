# main.py
from fastapi import FastAPI, Request
import json
from datetime import datetime

app = FastAPI()

@app.post("/webhook/alarm")
async def receive_alarm(request: Request):
    headers = dict(request.headers)
    content_type = headers.get("content-type", "")

    print(f"\n=== Incoming push @ {datetime.now()} ===")
    print(f"Content-Type: {content_type}")
    print(f"Headers: {headers}")

    if "multipart/form-data" in content_type:
        form = await request.form()
        print(f"Multipart form fields: {list(form.keys())}")
        for key, value in form.items():
            if hasattr(value, "filename"):  # it's a file part
                data = await value.read()
                print(f"  [{key}] FILE '{value.filename}', content_type={value.content_type}, size={len(data)} bytes")
            else:
                print(f"  [{key}] TEXT VALUE: {value}")
    else:
        body = await request.body()
        try:
            data = json.loads(body)
            print(f"JSON body:\n{json.dumps(data, indent=2, ensure_ascii=False)}")
        except json.JSONDecodeError:
            print(f"Raw body (not JSON), length={len(body)} bytes")
            print(body[:500])

    return {"status": "ok"}