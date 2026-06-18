from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import threading
from fastapi.responses import StreamingResponse
import cv2
from src.app import FallDetectionApp

app = FastAPI()

# THÊM ĐOẠN NÀY NGAY ĐÂY
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fall_app = FallDetectionApp()


@app.on_event("startup")
def start_detection_loop():
    """
    BUG GỐC nằm ở đây: trước đây fall_app được tạo ra nhưng KHÔNG có gì gọi
    fall_app.run() hay bất kỳ loop xử lý nào cả. Vì vậy latest_result đứng yên
    ở giá trị default {is_fall: False, confidence: 0.0, timestamp: None} khai
    báo trong FallDetectionApp.__init__ -> in ra y chang mỗi 0.2s, không bao
    giờ đổi.

    WHY threading.Thread, không phải asyncio.create_task:
    process_one_frame() gọi cv2.VideoCapture.read(), mediapipe Pose.process(),
    đều là code đồng bộ (blocking, CPU-bound), không phải async. Nếu chạy thẳng
    trong event loop của FastAPI (await trong route, hoặc asyncio task), mỗi
    lần xử lý 1 frame sẽ chiếm dụng toàn bộ event loop, khiến server không thể
    handle request nào khác (kể cả /video, /ws) trong lúc đó -> server bị đứng/lag.
    Chạy trong thread riêng để loop xử lý camera chạy độc lập, không block event loop.

    WHY daemon=True:
    Nếu main process (uvicorn) bị dừng, thread này tự kết thúc theo, không để lại
    process con treo (zombie thread giữ camera không nhả).
    """
    thread = threading.Thread(target=fall_app.run_headless, daemon=True)
    thread.start()


def generate_frames():
    while True:
        frame = fall_app.get_latest_frame()

        if frame is None:
            continue

        _, buffer = cv2.imencode(".jpg", frame)
        frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame_bytes
            + b"\r\n"
        )


@app.get("/video")
def video_feed():
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connected")

    try:
        while True:
            result = fall_app.get_latest_result()
            print(result)

            await websocket.send_json({
                "is_fall": result["is_fall"],
                "confidence": result["confidence"],
                "timestamp": result["timestamp"]
            })

            await asyncio.sleep(0.2)

    except Exception as e:
        print("WS error:", e)