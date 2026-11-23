"""Focus mode: checks whether you're looking at the screen, using Apple's Vision
framework (head yaw and pitch). Frames are processed in memory and never saved; the
camera is released whenever no session is actively running."""
import math
import statistics
import threading
import time
from collections import deque

# Starting values from testing, in degrees. Pitch is positive when the head tilts DOWN.
PITCH_DOWN = 5          # head this far below your baseline counts as looking down
YAW_SIDE = 30            # head turned this far sideways counts as looking away
CALIBRATE_READINGS = 4   # readings used to learn your "looking at the screen" pose
WINDOW = 4               # look at the last 4 readings...
MAJORITY = 2             # ...and call it "looking away" if 2 of them were away


class LookAwayWatcher:
    """Background thread: sets `away` once you've looked away for away_seconds."""

    def __init__(self, camera_index=0, interval=0.5):
        self.camera_index = camera_index
        self.interval = interval          # seconds between readings
        self.enabled = False              # user's focus-mode setting (from config)
        self.active = False               # True only while a session is running, not paused
        self.away_seconds = 15            # how long you can look away before it counts
        self.away = False                 # main.py reads this
        self.status = "off"               # off / idle / calibrating / watching / error: ...
        self._stop = threading.Event()    # doubles as an interruptible sleep timer

    def configure(self, enabled, away_seconds):
        # Called every loop from main.py so settings changes apply within seconds
        self.enabled, self.away_seconds = enabled, away_seconds

    def set_active(self, active):
        self.active = active

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()   # dies with the app

    def _set(self, away, status):
        self.away, self.status = away, status

    @staticmethod
    def _read(cap):
        """One reading: (yaw, pitch) in degrees, or None if no face is in view."""
        import cv2          # imported here so the app still runs without these
        import Foundation   # NSData (raw bytes) for Apple's APIs
        import Vision       # Apple's on-device face detection
        cap.read()                              # throw away a stale buffered frame
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError("camera returned no frame")
        _, jpg = cv2.imencode(".jpg", frame)    # Vision wants image bytes
        data = Foundation.NSData.dataWithBytes_length_(jpg.tobytes(), len(jpg))
        handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, {})
        request = Vision.VNDetectFaceRectanglesRequest.alloc().init()
        handler.performRequests_error_([request], None)
        faces = request.results() or []         # frame is dropped when this returns
        if not faces or faces[0].yaw() is None or faces[0].pitch() is None:
            return None
        return math.degrees(float(faces[0].yaw())), math.degrees(float(faces[0].pitch()))

    @staticmethod
    def _is_away(reading, baseline):
        if reading is None:                     # no face in view
            return True
        yaw, pitch = reading
        return (pitch - baseline[1] >= PITCH_DOWN) or (abs(yaw - baseline[0]) >= YAW_SIDE)

    def _run(self):
        cap = None
        baseline, calib = None, []              # baseline = (yaw, pitch) while on-screen
        recent = deque(maxlen=WINDOW)           # last few away/not-away results
        away_since = None                       # when the current look-away began
        while not self._stop.is_set():
            # --- Not supposed to be watching right now ---
            if not (self.enabled and self.active):
                if cap is not None:
                    cap.release()               # camera light goes off outside sessions
                    cap = None
                baseline, calib, away_since = None, [], None   # recalibrate next time
                recent.clear()
                self._set(False, "idle" if self.enabled else "off")
                self._stop.wait(1)
                continue
            # --- Watching ---
            try:
                if cap is None:
                    import cv2
                    cap = cv2.VideoCapture(self.camera_index)
                    if not cap.isOpened():
                        raise RuntimeError("can't open the camera (check Camera permission)")
                reading = self._read(cap)
                if baseline is None:
                    # Learning phase: look at your screen while this runs
                    if reading is not None:
                        calib.append(reading)
                    if len(calib) >= CALIBRATE_READINGS:
                        baseline = (statistics.median(r[0] for r in calib),
                                    statistics.median(r[1] for r in calib))
                    self._set(False, "calibrating")
                else:
                    recent.append(self._is_away(reading, baseline))
                    if sum(recent) >= MAJORITY:             # looking away right now
                        away_since = away_since or time.time()
                    else:
                        away_since = None                   # looked back, timer resets
                    too_long = (away_since is not None
                                and time.time() - away_since >= self.away_seconds)
                    self._set(too_long, "watching")
            except Exception as e:                # missing package, no permission, no camera
                print(f"   [look-away] {e}")
                if cap is not None:
                    cap.release()
                cap = None
                self.enabled = False              # stop retrying until re-enabled
                self._set(False, f"error: {e}")
            self._stop.wait(self.interval)


if __name__ == "__main__":   # .venv/bin/python -m webcam.look_away   (Ctrl+C to stop)
    w = LookAwayWatcher()
    w.configure(True, 2)       # enabled, 2 seconds is enough for a quick test
    w.set_active(True)
    w.start()
    while True:
        print(f"status={w.status}  away={w.away}")
        time.sleep(1)