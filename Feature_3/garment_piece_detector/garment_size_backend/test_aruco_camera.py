import argparse

import cv2
import numpy as np


def read_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--camera",
        type=int,
        default=1,
        help="External camera index",
    )

    parser.add_argument(
        "--marker-size-cm",
        type=float,
        default=10.0,
    )

    return parser.parse_args()


def detect_marker(
    frame,
    marker_size_cm,
):
    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2GRAY,
    )

    dictionary = (
        cv2.aruco.getPredefinedDictionary(
            cv2.aruco.DICT_4X4_50
        )
    )

    if hasattr(
        cv2.aruco,
        "ArucoDetector",
    ):
        parameters = (
            cv2.aruco.DetectorParameters()
        )

        detector = (
            cv2.aruco.ArucoDetector(
                dictionary,
                parameters,
            )
        )

        corners, ids, _ = (
            detector.detectMarkers(gray)
        )
    else:
        parameters = (
            cv2.aruco.DetectorParameters_create()
        )

        corners, ids, _ = (
            cv2.aruco.detectMarkers(
                gray,
                dictionary,
                parameters=parameters,
            )
        )

    if ids is None:
        return None, None, None

    marker_ids = ids.flatten()

    if 0 in marker_ids:
        marker_index = int(
            np.where(
                marker_ids == 0
            )[0][0]
        )
    else:
        marker_index = 0

    marker_corners = (
        corners[marker_index][0]
        .astype(np.float32)
    )

    side_lengths = []

    for index in range(4):
        point_1 = marker_corners[index]
        point_2 = marker_corners[
            (index + 1) % 4
        ]

        side_length = np.linalg.norm(
            point_1 - point_2
        )

        side_lengths.append(
            float(side_length)
        )

    average_side_pixels = float(
        np.mean(side_lengths)
    )

    pixels_per_cm = (
        average_side_pixels
        / marker_size_cm
    )

    return (
        marker_corners,
        pixels_per_cm,
        ids,
    )


def main():
    arguments = read_arguments()

    camera = cv2.VideoCapture(
        arguments.camera,
        cv2.CAP_DSHOW,
    )

    camera.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        1920,
    )

    camera.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        1080,
    )

    if not camera.isOpened():
        raise RuntimeError(
            "External camera could not be opened. "
            "Try --camera 0, 1 or 2."
        )

    print("=" * 60)
    print("ArUco camera calibration test")
    print("=" * 60)
    print(
        f"Camera index: {arguments.camera}"
    )
    print("Press Q to close.")

    while True:
        success, frame = camera.read()

        if not success:
            break

        (
            marker_corners,
            pixels_per_cm,
            ids,
        ) = detect_marker(
            frame,
            arguments.marker_size_cm,
        )

        if marker_corners is None:
            status = (
                "CALIBRATION MARKER NOT DETECTED"
            )

            colour = (0, 0, 255)
        else:
            status = (
                f"MARKER DETECTED | "
                f"{pixels_per_cm:.3f} pixels/cm"
            )

            colour = (0, 255, 0)

            cv2.polylines(
                frame,
                [
                    marker_corners.astype(
                        np.int32
                    )
                ],
                True,
                colour,
                3,
            )

        cv2.putText(
            frame,
            status,
            (30, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            colour,
            2,
            cv2.LINE_AA,
        )

        cv2.imshow(
            "ArUco Calibration Test",
            frame,
        )

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()