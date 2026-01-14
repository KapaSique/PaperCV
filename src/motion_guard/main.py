import time, cv2, numpy as np
from dataclasses import dataclass

@dataclass
class Params:
    cam_index: int = 0
    width: int | None = 1280
    height: int | None = 720

    blur_ksize: int = 21
    bg_alpha: float = 0.02
    thresh: int = 25
    dilate_iters: int = 2
    motion_px: int = 15_000

def main() -> None:
    p = Params()

    cap = cv2.VideoCapture(p.cam_index)

    bg: np.ndarray | None = None

    last_t = time.time()
    fps = 0.0

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("Frame grab failed")
                break

                #FPS
            now = time.time()
            dt = now - last_t
            if dt > 0:
                fps = 1.0 / dt
            last_t = now

                #Preprocess
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            k = p.blur_ksize if p.blur_ksize % 2 == 1 else p.blur_ksize + 1
            gray = cv2.GaussianBlur(gray, (k, k), 0)

                #Background model
            if bg is None:
                bg = gray.astype(np.float32)
                cv2.putText(frame, "Warming up background...", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.imshow("frame", frame)
                if (cv2.waitKey(1) & 0xFF) == ord("q"):
                    break
                continue
            cv2.accumulateWeighted(gray, bg, p.bg_alpha)

            bg_u8 = cv2.convertScaleAbs(bg)
            delta = cv2.absdiff(gray, bg_u8)

            _, thresh = cv2.threshold(delta, p.thresh, 255, cv2.THRESH_BINARY)
            thresh = cv2.dilate(thresh, None, iterations=p.dilate_iters)

            white_px = int(np.count_nonzero(thresh))
            status = "MOTION" if white_px >= p.motion_px else "IDLE"
            cv2.putText(
                frame,
                f"FPS: {fps:.1f} | {status} | px = {white_px} | press 'q' to quit",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            cv2.imshow("frame", frame)
            cv2.imshow("delta", delta)
            cv2.imshow("thresh", thresh)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()