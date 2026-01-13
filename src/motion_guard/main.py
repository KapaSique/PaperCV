import time

import cv2


def main() -> None:
    cap = cv2.VideoCapture(0)

    last_t = time.time()
    fps = 0.0

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("Frame grab failed")
                break

            now = time.time()
            dt = now - last_t
            if dt > 0:
                fps = 1.0 / dt
            last_t = now

            cv2.putText(
                frame,
                f"FPS: {fps:.1f} | press 'q' to quit",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            cv2.imshow("motion-guard", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()