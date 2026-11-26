# APK Package Renamer & Auto-Signer

A lightweight, standalone Python desktop GUI tool that mimics the core package-cloning workflow of **APK Editor**—allowing you to inspect an Android `.apk` file, change its package name cleanly, rebuild the binary manifest, and sign the output APK so it is ready to install on an Android device or emulator.

---

## Features

- **Clean Desktop GUI:** Built with standard Python `tkinter` (`ttk`)—zero third-party Python dependencies required.
- **Automatic Package Inspection:** Automatically reads the current package name upon uploading an `.apk` file (via `aapt2`, `aapt`, or `apktool`).
- **Safe Manifest Rebuilding:** Uses `apktool` to decode and recompile binary `AndroidManifest.xml`, supporting new package names of **any character length** without corrupting binary XML string pools.
- **Side-by-Side Install Support:** Automatically expands relative component names (e.g., `.MainActivity` $\rightarrow$ `com.original.pkg.MainActivity`) and updates `ContentProvider` `android:authorities` so both the original and renamed apps can coexist on the same device without `INSTALL_FAILED_CONFLICTING_PROVIDER`.
- **Built-in Auto-Signing:** Uses `uber-apk-signer` to `zipalign` and sign the rebuilt APK with a debug certificate (v1, v2, and v3 signature schemes).
- **Auto-Dependency Management:** Automatically fetches and caches the latest `apktool.jar` and `uber-apk-signer.jar` into a local `./tools/` directory on first launch.
- **Live Conversion Progress (`0%`–`100%`):** Non-blocking background execution with stage-by-stage progress percentage and byte-level download tracking.

---

## Prerequisites

1. **Python 3.10+** (includes `tkinter` by default on Windows and macOS; on Debian/Ubuntu, install `python3-tk` if needed).
2. **Java Runtime Environment (JRE / JDK 11+)** available in your system `PATH` (`java -version`).
3. **Internet access on first run** so the script can automatically download `apktool.jar` and `uber-apk-signer.jar` into `./tools/`.

---

## Quick Start

1. **Clone or download the repository:**
   ```bash
   git clone https://github.com/your-username/apk-package-renamer.git
   cd apk-package-renamer
   ```

2. **Run the application:**
   ```bash
   python apk_editor_pro_renamer.py
   ```

3. **Convert an APK:**
   - Wait for the tool status bar to show `Java: Ready • apktool.jar: Ready • uber-apk-signer.jar: Ready`.
   - Click **Upload APK** and select your `.apk` file.
   - Review the detected **Current Package** and enter your desired **New Package** (e.g., `com.example.clonedapp`).
   - Keep **Expand relative component names & update provider authorities** checked if you plan to install alongside the original app.
   - Click **Convert & Save As...** (or **Convert, Save & Close**) and choose the destination path.

---

## Project Structure

```text
apk-package-renamer/
├── apk_editor_pro_renamer.py   # Main Tkinter GUI & APK build/sign pipeline
├── README.md                   # Project documentation
└── tools/                      # Auto-created on first run
    ├── apktool.jar             # Downloaded automatically from iBotPeaches/Apktool
    └── uber-apk-signer.jar     # Downloaded automatically from patrickfav/uber-apk-signer
```

---

## How It Works Under the Hood

| Stage | Progress | Action |
| :--- | :---: | :--- |
| **1. Tool Check / Download** | `0% – 25%` | Verifies `java` in `PATH` and downloads `apktool.jar` & `uber-apk-signer.jar` if missing. |
| **2. Decode** | `28% – 50%` | Runs `apktool d -f -s` to decode `AndroidManifest.xml` while leaving `classes.dex` intact for speed and stability. |
| **3. Manifest Patch** | `55% – 62%` | Updates the root `package` attribute, expands relative class names, and rewrites matching `provider` authorities. |
| **4. Rebuild** | `66% – 85%` | Recompiles resources and binary XML via `apktool b`. |
| **5. Align & Sign** | `88% – 100%` | Runs `uber-apk-signer` to `zipalign` and sign the APK with a debug key. |

---

## Troubleshooting

- **`Java runtime ('java') was not found in PATH`:** Install OpenJDK / Temurin (JDK 11 or newer) and ensure `java` is accessible from your terminal.
- **App crashes immediately after launch on Android:** Some apps hardcode their own package name inside compiled Java/Kotlin bytecode (`classes.dex`) or native libraries (`.so`), or enforce signature/tamper checks. This tool modifies `AndroidManifest.xml` without rewriting `classes.dex`.
- **Installing via ADB:** Once saved, you can install the output APK directly with:
  ```bash
  adb install path/to/your_app_com.new.package_signed.apk
  ```

---

## Disclaimer

This tool is intended for educational purposes, local testing, debugging, and modifying applications you own or have permission to modify.
