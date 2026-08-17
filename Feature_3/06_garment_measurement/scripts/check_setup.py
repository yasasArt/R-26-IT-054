import platform
import sys
from pathlib import Path


def check_import(package_name, import_name=None):
    module_name = import_name or package_name

    try:
        module = __import__(module_name)
        version = getattr(module, "__version__", "Unknown")

        print(
            f"[OK] {package_name}: {version}"
        )

        return True

    except ImportError as error:
        print(
            f"[ERROR] {package_name} is not installed"
        )
        print(f"        {error}")

        return False


def check_folders(project_root):
    required_folders = [
        "data/raw_best_frames",
        "data/annotations_labelme",
        "data/segmentation_dataset/images/train",
        "data/segmentation_dataset/images/val",
        "data/segmentation_dataset/images/test",
        "data/segmentation_dataset/labels/train",
        "data/segmentation_dataset/labels/val",
        "data/segmentation_dataset/labels/test",
        "data/calibration",
        "data/ground_truth",
        "config",
        "scripts",
        "models",
        "outputs/segmentation_training",
        "outputs/segmentation_predictions",
        "outputs/garment_masks",
        "outputs/measurement_results",
        "outputs/size_predictions"
    ]

    all_folders_exist = True

    print("\n----- Folder Check -----")

    for relative_folder in required_folders:
        folder_path = project_root / relative_folder

        if folder_path.exists():
            print(f"[OK] {relative_folder}")
        else:
            print(f"[MISSING] {relative_folder}")
            all_folders_exist = False

    return all_folders_exist


def check_gpu():
    print("\n----- PyTorch and GPU Check -----")

    try:
        import torch

        print(f"PyTorch version: {torch.__version__}")
        print(f"CUDA available: {torch.cuda.is_available()}")

        if torch.cuda.is_available():
            print(
                "GPU name: "
                f"{torch.cuda.get_device_name(0)}"
            )

            print(
                "CUDA version: "
                f"{torch.version.cuda}"
            )

            total_memory = (
                torch.cuda.get_device_properties(0)
                .total_memory
                / (1024 ** 3)
            )

            print(
                f"GPU memory: {total_memory:.2f} GB"
            )

            return True

        print(
            "[WARNING] CUDA GPU එක detect වී නැහැ."
        )

        return False

    except ImportError:
        print("[ERROR] PyTorch is not installed.")
        return False


def main():
    project_root = Path(__file__).resolve().parent.parent

    print("========================================")
    print(" Garment Measurement Setup Verification")
    print("========================================")

    print(f"Project root: {project_root}")
    print(f"Python version: {sys.version}")
    print(f"Operating system: {platform.platform()}")

    print("\n----- Package Check -----")

    package_results = [
        check_import("NumPy", "numpy"),
        check_import("Pandas", "pandas"),
        check_import("OpenCV", "cv2"),
        check_import("SciPy", "scipy"),
        check_import("Scikit-learn", "sklearn"),
        check_import("PyYAML", "yaml"),
        check_import("Pillow", "PIL"),
        check_import("Matplotlib", "matplotlib"),
        check_import("Ultralytics", "ultralytics")
    ]

    gpu_available = check_gpu()
    folders_exist = check_folders(project_root)

    packages_available = all(package_results)

    print("\n========================================")
    print(" Final Setup Result")
    print("========================================")

    print(
        f"Packages: "
        f"{'PASSED' if packages_available else 'FAILED'}"
    )

    print(
        f"Folders: "
        f"{'PASSED' if folders_exist else 'FAILED'}"
    )

    print(
        f"GPU: "
        f"{'PASSED' if gpu_available else 'NOT AVAILABLE'}"
    )

    if (
        packages_available
        and folders_exist
        and gpu_available
    ):
        print(
            "\nSETUP SUCCESSFUL — "
            "Ready for garment segmentation."
        )
    else:
        print(
            "\nSETUP INCOMPLETE — "
            "Fix the errors shown above."
        )


if __name__ == "__main__":
    main()