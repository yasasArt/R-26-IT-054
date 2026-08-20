from pathlib import Path

import cv2
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


PROJECT_DIRECTORY = (
    Path(__file__).resolve().parent
)

MARKER_PNG_PATH = (
    PROJECT_DIRECTORY
    / "aruco_marker_id_0.png"
)

MARKER_PDF_PATH = (
    PROJECT_DIRECTORY
    / "aruco_marker_10cm.pdf"
)

MARKER_SIZE_CM = 10.0
MARKER_IMAGE_PIXELS = 1200


def create_marker_image():
    dictionary = (
        cv2.aruco.getPredefinedDictionary(
            cv2.aruco.DICT_4X4_50
        )
    )

    if hasattr(
        cv2.aruco,
        "generateImageMarker",
    ):
        marker_image = (
            cv2.aruco.generateImageMarker(
                dictionary,
                0,
                MARKER_IMAGE_PIXELS,
            )
        )
    else:
        marker_image = (
            cv2.aruco.drawMarker(
                dictionary,
                0,
                MARKER_IMAGE_PIXELS,
            )
        )

    success = cv2.imwrite(
        str(MARKER_PNG_PATH),
        marker_image,
    )

    if not success:
        raise RuntimeError(
            "Marker PNG could not be saved."
        )


def create_printable_pdf():
    page_width, page_height = A4

    marker_size = (
        MARKER_SIZE_CM * cm
    )

    marker_x = (
        page_width - marker_size
    ) / 2

    marker_y = (
        page_height - marker_size
    ) / 2

    pdf = canvas.Canvas(
        str(MARKER_PDF_PATH),
        pagesize=A4,
    )

    pdf.setTitle(
        "10 cm ArUco Calibration Marker"
    )

    pdf.setFont(
        "Helvetica-Bold",
        16,
    )

    pdf.drawCentredString(
        page_width / 2,
        page_height - 2 * cm,
        "Garment Measurement Calibration Marker",
    )

    pdf.setFont(
        "Helvetica",
        11,
    )

    pdf.drawCentredString(
        page_width / 2,
        page_height - 2.7 * cm,
        (
            "Print at Actual Size / 100%. "
            "Do not use Fit to Page."
        ),
    )

    pdf.drawImage(
        str(MARKER_PNG_PATH),
        marker_x,
        marker_y,
        width=marker_size,
        height=marker_size,
        preserveAspectRatio=True,
        mask="auto",
    )

    pdf.setFont(
        "Helvetica-Bold",
        12,
    )

    pdf.drawCentredString(
        page_width / 2,
        marker_y - 0.8 * cm,
        (
            "The black marker square "
            "must measure exactly 10.0 cm"
        ),
    )

    pdf.setFont(
        "Helvetica",
        10,
    )

    pdf.drawCentredString(
        page_width / 2,
        marker_y - 1.4 * cm,
        "Dictionary: DICT_4X4_50 | Marker ID: 0",
    )

    pdf.save()


def main():
    create_marker_image()
    create_printable_pdf()

    print("=" * 60)
    print("Calibration marker generated")
    print("=" * 60)
    print(f"PNG: {MARKER_PNG_PATH}")
    print(f"PDF: {MARKER_PDF_PATH}")
    print(
        "Print PDF using Actual Size / 100%."
    )


if __name__ == "__main__":
    main()