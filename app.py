from fastapi import FastAPI, File, UploadFile, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import cv2
import numpy as np
from tensorflow.keras.models import load_model
import shutil
import os
import sqlite3

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

model = load_model('Slang_CNN_model.h5')

temp_dir = 'temp'
os.makedirs(temp_dir, exist_ok=True)


def get_db_connection():
    conn = sqlite3.connect("slang_database.db")
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analyze/")
async def analyze_video(request: Request, username: str = Form(...), file: UploadFile = File(...)):
    count_swear = 0
    temp_file_path = os.path.join(temp_dir, file.filename)
    with open(temp_file_path, "wb") as temp_file:
        shutil.copyfileobj(file.file, temp_file)

    cap = cv2.VideoCapture(temp_file_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = 0

    if not cap.isOpened():
        return {"error": "Error opening video file"}

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % (5 * fps) == 0:
                img_path = os.path.join(temp_dir, f"frame_at_{frame_count // fps}sec.jpg")
                cv2.imwrite(img_path, frame)
                img = cv2.resize(frame, (28, 28))
                img = img / 255.0
                img = np.expand_dims(img, axis=0)
                prediction = model.predict(img)
                if prediction[0][0] < 0.5:
                    count_swear += 1

            frame_count += 1

        cap.release()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if cap.isOpened():
            cap.release()

    os.remove(temp_file_path)

    if count_swear >= 5:
        message = "욕 하지 마라."
    elif 2 <= count_swear < 5:
        message = "욕 줄여보는 습관을 들여보자."
    else:
        message = "바른 행동의 사람입니다. 참 좋습니다."


    db_connect = get_db_connection()
    cur = db_connect.cursor()
    insert_query = """
    INSERT INTO user_swear_count (username, swear_count, detected_at)
    VALUES (?, ?, datetime('now'));
    """

    cur.execute(insert_query, (username, count_swear))
    db_connect.commit()
    cur.close()

    return templates.TemplateResponse("results.html", {"request": request, "username": username, "count_swear": count_swear, "message": message})
