import os
import re
import json
import cv2
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone

from ultralytics import YOLO
from rapidocr_onnxruntime import RapidOCR


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_PATH = r"best.pt"

VIDEO_DIR = r"test_videos"

VIDEO_EXTENSIONS = (
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".wmv"
)

OUTPUT_DIR = r"runs\final_anpr"

JSON_PATH = os.path.join(
    OUTPUT_DIR,
    "final_results.json"
)

CONF_THRESHOLD = 0.20
IMG_SIZE = 1280

# Padding around detected plate
PAD_X = 0.18
PAD_Y = 0.30

# Number of best crops used for OCR per track
BEST_CROPS = 4

# Minimum OCR confidence accepted
MIN_OCR_CONF = 0.30

# ------------------------------------------------------------
# Video timestamp base
#
# Change this to the actual CCTV recording start time when
# that information is available.
# ------------------------------------------------------------

VIDEO_START_TIME = datetime(
    2026,
    9,
    9,
    10,
    0,
    0,
    tzinfo=timezone.utc
)


# ============================================================
# INDIAN STATE / UT CODES
# ============================================================

STATE_CODES = {
    "AN",
    "AP",
    "AR",
    "AS",
    "BR",
    "CH",
    "CG",
    "DD",
    "DL",
    "DN",
    "GA",
    "GJ",
    "HR",
    "HP",
    "JH",
    "JK",
    "KA",
    "KL",
    "LA",
    "LD",
    "MH",
    "ML",
    "MN",
    "MP",
    "MZ",
    "NL",
    "OD",
    "PB",
    "PY",
    "RJ",
    "SK",
    "TN",
    "TR",
    "TS",
    "UK",
    "UP",
    "WB"
}


# ============================================================
# FIND ALL VIDEOS
# ============================================================

def find_videos():

    if not os.path.isdir(VIDEO_DIR):

        print()
        print(
            "ERROR: Video directory not found:"
        )

        print(
            VIDEO_DIR
        )

        return []

    videos = []

    for filename in os.listdir(VIDEO_DIR):

        file_path = os.path.join(
            VIDEO_DIR,
            filename
        )

        if not os.path.isfile(file_path):
            continue

        extension = os.path.splitext(
            filename
        )[1].lower()

        if extension in VIDEO_EXTENSIONS:

            videos.append(
                file_path
            )

    videos.sort(
        key=lambda path:
            os.path.basename(path).lower()
    )

    return videos


# ============================================================
# CLEAN OCR TEXT
# ============================================================

def clean_text(text):

    text = str(text).upper()

    return re.sub(
        r"[^A-Z0-9]",
        "",
        text
    )


# ============================================================
# VALIDATE INDIAN PLATE FORMAT
#
# LL DD LL DDDD
#
# Example:
# MH12TH0838
# ============================================================

def valid_plate(text):

    text = clean_text(text)

    if len(text) != 10:
        return False

    # State code
    if not text[:2].isalpha():
        return False

    if text[:2] not in STATE_CODES:
        return False

    # RTO digits
    if not text[2:4].isdigit():
        return False

    # Series letters
    if not text[4:6].isalpha():
        return False

    # Registration digits
    if not text[6:10].isdigit():
        return False

    return True


# ============================================================
# CROP DETECTED PLATE WITH PADDING
# ============================================================

def crop_with_padding(frame, box):

    h, w = frame.shape[:2]

    x1, y1, x2, y2 = box

    box_width = x2 - x1
    box_height = y2 - y1

    x1 = int(
        max(
            0,
            x1 - box_width * PAD_X
        )
    )

    y1 = int(
        max(
            0,
            y1 - box_height * PAD_Y
        )
    )

    x2 = int(
        min(
            w,
            x2 + box_width * PAD_X
        )
    )

    y2 = int(
        min(
            h,
            y2 + box_height * PAD_Y
        )
    )

    crop = frame[
        y1:y2,
        x1:x2
    ]

    return crop


# ============================================================
# CROP QUALITY SCORE
# ============================================================

def quality_score(crop):

    if crop is None:
        return 0.0

    if crop.size == 0:
        return 0.0

    gray = cv2.cvtColor(
        crop,
        cv2.COLOR_BGR2GRAY
    )

    # Sharpness
    sharpness = cv2.Laplacian(
        gray,
        cv2.CV_64F
    ).var()

    # Area
    height, width = gray.shape

    area = width * height

    # Aspect ratio
    aspect_ratio = width / max(
        height,
        1
    )

    if 2.5 <= aspect_ratio <= 6.5:
        aspect_score = 1.0
    else:
        aspect_score = 0.5

    score = (
        0.50 * min(
            sharpness / 1000.0,
            1.0
        )
        +
        0.30 * min(
            area / 30000.0,
            1.0
        )
        +
        0.20 * aspect_score
    )

    return float(score)


# ============================================================
# RAPIDOCR
# ============================================================

def run_ocr(ocr, crop):

    if crop is None:
        return []

    if crop.size == 0:
        return []

    try:

        result, _ = ocr(crop)

    except Exception:

        return []

    if not result:
        return []

    outputs = []

    for item in result:

        try:

            _, text, confidence = item

            text = clean_text(text)

            confidence = float(
                confidence
            )

            if not text:
                continue

            outputs.append(
                {
                    "text": text,
                    "confidence": confidence
                }
            )

        except Exception:

            continue

    return outputs


# ============================================================
# CREATE EVENT TIMESTAMP
# ============================================================

def create_timestamp(
    frame_number,
    fps
):

    seconds = frame_number / fps

    timestamp = (
        VIDEO_START_TIME
        +
        timedelta(
            seconds=seconds
        )
    )

    return timestamp.isoformat(
        timespec="seconds"
    ).replace(
        "+00:00",
        "Z"
    )


# ============================================================
# PROCESS CAMERA
# ============================================================

def process_camera(
    camera_id,
    video_path,
    model,
    ocr
):

    print()
    print("=" * 70)
    print(camera_id)
    print("=" * 70)

    print(
        "Video:",
        os.path.basename(
            video_path
        )
    )

    cap = cv2.VideoCapture(
        video_path
    )

    if not cap.isOpened():

        print(
            "ERROR: Could not open video:"
        )

        print(
            video_path
        )

        return []

    fps = cap.get(
        cv2.CAP_PROP_FPS
    )

    if fps <= 0:
        fps = 30.0

    total_frames = int(
        cap.get(
            cv2.CAP_PROP_FRAME_COUNT
        )
    )

    print(
        "Frames:",
        total_frames
    )

    print(
        "FPS:",
        fps
    )

    # ========================================================
    # TRACK DATA
    #
    # Every detected plate track is retained internally.
    # OCR failure does NOT delete the track.
    # ========================================================

    track_data = defaultdict(
        lambda: {
            "detections": 0,
            "best_crops": []
        }
    )

    frame_number = 0

    total_detections = 0

    # ========================================================
    # TRACK 1
    # NUMBER PLATE DETECTION + BYTETRACK
    # ========================================================

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        results = model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            conf=CONF_THRESHOLD,
            imgsz=IMG_SIZE,
            device=0,
            verbose=False
        )

        if not results:

            frame_number += 1

            continue

        result = results[0]

        if result.boxes is None:

            frame_number += 1

            continue

        boxes = result.boxes

        if boxes.xyxy is None:

            frame_number += 1

            continue

        xyxy = (
            boxes.xyxy
            .cpu()
            .numpy()
        )

        confidences = (
            boxes.conf
            .cpu()
            .numpy()
        )

        if boxes.id is not None:

            track_ids = (
                boxes.id
                .cpu()
                .numpy()
                .astype(int)
            )

        else:

            track_ids = (
                [-1]
                * len(xyxy)
            )

        # ====================================================
        # STORE EVERY DETECTION
        # ====================================================

        for (
            box,
            detector_confidence,
            track_id
        ) in zip(
            xyxy,
            confidences,
            track_ids
        ):

            if track_id == -1:
                continue

            track_id = int(
                track_id
            )

            total_detections += 1

            track_data[
                track_id
            ]["detections"] += 1

            crop = crop_with_padding(
                frame,
                box
            )

            if crop is None:
                continue

            if crop.size == 0:
                continue

            quality = quality_score(
                crop
            )

            track_data[
                track_id
            ]["best_crops"].append(
                {
                    "frame": frame_number,
                    "detector_confidence":
                        float(
                            detector_confidence
                        ),
                    "quality": quality,
                    "crop": crop
                }
            )

        frame_number += 1

    cap.release()

    print()
    print(
        "Total plate detections:",
        total_detections
    )

    print(
        "Detected plate tracks:",
        len(track_data)
    )

    # ========================================================
    # TRACK 2
    # OCR ON EACH TRACK
    # ========================================================

    camera_results = []

    for track_id in sorted(
        track_data.keys()
    ):

        data = track_data[
            track_id
        ]

        detections = data[
            "detections"
        ]

        crops = data[
            "best_crops"
        ]

        # ----------------------------------------------------
        # SORT CROPS BY QUALITY
        # ----------------------------------------------------

        crops = sorted(
            crops,
            key=lambda x:
                x["quality"],
            reverse=True
        )

        crops = crops[
            :BEST_CROPS
        ]

        print()
        print("-" * 60)

        print(
            f"Track {track_id:04d} "
            f"| detections={detections} "
            f"| OCR crops={len(crops)}"
        )

        # ----------------------------------------------------
        # OCR RESULTS
        # ----------------------------------------------------

        ocr_results = []

        for item in crops:

            results = run_ocr(
                ocr,
                item["crop"]
            )

            for result in results:

                text = result[
                    "text"
                ]

                confidence = result[
                    "confidence"
                ]

                print(
                    f"  frame={item['frame']:06d} "
                    f"| OCR={text} "
                    f"| conf={confidence:.3f}"
                )

                ocr_results.append(
                    {
                        "text": text,
                        "confidence":
                            confidence,
                        "frame":
                            item["frame"]
                    }
                )

        # ----------------------------------------------------
        # ONLY VALID OCR RESULTS
        # ----------------------------------------------------

        valid_ocr = [
            item
            for item in ocr_results
            if (
                item["confidence"]
                >= MIN_OCR_CONF
                and
                valid_plate(
                    item["text"]
                )
            )
        ]

        # ----------------------------------------------------
        # OCR SUCCESS
        # ----------------------------------------------------

        if valid_ocr:

            plate_counter = Counter(
                item["text"]
                for item in valid_ocr
            )

            best_plate, support = (
                plate_counter
                .most_common(1)[0]
            )

            matching_confidences = [
                item["confidence"]
                for item in valid_ocr
                if item["text"]
                == best_plate
            ]

            best_confidence = max(
                matching_confidences
            )

            # ------------------------------------------------
            # Select the frame that produced the best
            # recognition of this plate.
            # ------------------------------------------------

            best_match = max(
                (
                    item
                    for item in valid_ocr
                    if item["text"]
                    == best_plate
                ),
                key=lambda x:
                    x["confidence"]
            )

            best_frame = best_match[
                "frame"
            ]

            timestamp = create_timestamp(
                best_frame,
                fps
            )

            print()

            print(
                f"  OCR RESULT: "
                f"{best_plate} "
                f"| support={support} "
                f"| confidence="
                f"{best_confidence:.3f}"
            )

            camera_results.append(
                {
                    "camera_id":
                        camera_id,

                    "track_id":
                        track_id,

                    "plate_number":
                        best_plate,

                    "timestamp":
                        timestamp,

                    "confidence":
                        round(
                            best_confidence,
                            4
                        )
                }
            )

        # ----------------------------------------------------
        # OCR FAILURE
        #
        # Nothing is saved to the final JSON.
        # ----------------------------------------------------

        else:

            print()

            print(
                "  OCR RESULT: "
                "NOT RECOGNIZED"
            )

    return camera_results


# ============================================================
# MAIN
# ============================================================

def main():

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    print()
    print("=" * 70)
    print(
        "FINAL TRACK 1 + TRACK 2 ANPR PIPELINE"
    )
    print("=" * 70)

    # ========================================================
    # FIND ALL VIDEOS
    # ========================================================

    video_paths = find_videos()

    if not video_paths:

        print()
        print(
            "No supported videos found in:"
        )

        print(
            VIDEO_DIR
        )

        print()
        print(
            "Supported formats:",
            ", ".join(
                VIDEO_EXTENSIONS
            )
        )

        return

    print()
    print(
        "Videos found:",
        len(video_paths)
    )

    for index, video_path in enumerate(
        video_paths,
        start=1
    ):

        print(
            f"  CAM_{index:02d}: "
            f"{os.path.basename(video_path)}"
        )

    # ========================================================
    # LOAD MODELS
    # ========================================================

    print()
    print(
        "Loading YOLO model..."
    )

    model = YOLO(
        MODEL_PATH
    )

    print(
        "Loading RapidOCR..."
    )

    ocr = RapidOCR()

    # ========================================================
    # PROCESS ALL CAMERAS
    # ========================================================

    all_camera_results = []

    for index, video_path in enumerate(
        video_paths,
        start=1
    ):

        camera_id = (
            f"CAM_{index:02d}"
        )

        results = process_camera(
            camera_id,
            video_path,
            model,
            ocr
        )

        all_camera_results.extend(
            results
        )

    # ========================================================
    # CREATE FINAL EVENTS
    #
    # EXACT FINAL JSON SCHEMA:
    #
    # event_id
    # camera_id
    # vehicle_id
    # plate_number
    # timestamp
    # confidence
    #
    # ONLY RECOGNIZED PLATES ARE SAVED.
    # ========================================================

    events = []

    event_index = 1

    for item in all_camera_results:

        events.append(
            {
                "event_id":
                    f"EVT_{event_index:06d}",

                "camera_id":
                    item["camera_id"],

                "vehicle_id":
                    f"track_{item['track_id']:04d}",

                "plate_number":
                    item["plate_number"],

                "timestamp":
                    item["timestamp"],

                "confidence":
                    item["confidence"]
            }
        )

        event_index += 1

    # ========================================================
    # FINAL JSON
    #
    # No project metadata.
    # No UNKNOWN records.
    # No OCR status.
    # No support count.
    # No detection count.
    # ========================================================

    with open(
        JSON_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            events,
            file,
            indent=2
        )

    # ========================================================
    # FINAL RESULTS
    # ========================================================

    print()
    print("=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)

    for event in events:

        print(
            f"{event['event_id']} | "
            f"{event['camera_id']} | "
            f"{event['vehicle_id']} | "
            f"{event['plate_number']} | "
            f"{event['timestamp']} | "
            f"confidence="
            f"{event['confidence']:.3f}"
        )

    print()
    print(
        "Videos processed:",
        len(video_paths)
    )

    print(
        "Recognized plate events saved:",
        len(events)
    )

    print()
    print(
        "JSON saved:",
        JSON_PATH
    )

    print("=" * 70)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()