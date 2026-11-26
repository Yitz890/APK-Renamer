import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


APKTOOL_API = "https://api.github.com/repos/iBotPeaches/Apktool/releases/latest"
APKTOOL_FALLBACK_URL = "https://github.com/iBotPeaches/Apktool/releases/download/v3.0.3/apktool_3.0.3.jar"

SIGNER_API = "https://api.github.com/repos/patrickfav/uber-apk-signer/releases/latest"
SIGNER_FALLBACK_URL = (
    "https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar"
)


class ApkRenamerModernGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("APK Package Renamer & Auto-Signer")
        self.root.geometry("680x475")
        self.root.minsize(640, 450)

        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.tools_dir = os.path.join(self.script_dir, "tools")
        os.makedirs(self.tools_dir, exist_ok=True)

        self.apktool_jar = os.path.join(self.tools_dir, "apktool.jar")
        self.signer_jar = os.path.join(self.tools_dir, "uber-apk-signer.jar")

        self.apk_path: str = ""
        self.current_package: str = ""
        self.busy: bool = False

        self._configure_styles()
        self._build_ui()
        self.root.after(150, lambda: self.ensure_dependencies_async(prompt_on_error=False))

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        for theme in ("vista", "clam", "default"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break

        self.bg_color = "#f4f6f9"
        self.root.configure(bg=self.bg_color)

        style.configure("TFrame", background=self.bg_color)
        style.configure("TLabelframe", background="#ffffff", borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background="#ffffff", foreground="#1f2937", font=("Segoe UI", 9, "bold"))
        style.configure("TLabel", background="#ffffff", foreground="#1f2937", font=("Segoe UI", 9))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#6b7280", font=("Segoe UI", 8))
        style.configure("Status.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI", 9))
        style.configure("Pct.TLabel", background="#ffffff", foreground="#2563eb", font=("Segoe UI", 10, "bold"))
        style.configure("TCheckbutton", background="#ffffff", foreground="#1f2937", font=("Segoe UI", 9))
        style.configure("TButton", font=("Segoe UI", 9), padding=(10, 5))
        style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"), padding=(12, 5))
        style.configure("Horizontal.TProgressbar", thickness=14)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill=tk.BOTH, expand=True)

        # Header
        header = ttk.Frame(outer)
        header.pack(fill=tk.X, pady=(0, 10))
        title_lbl = tk.Label(
            header,
            text="APK Package Renamer & Auto-Signer",
            bg=self.bg_color,
            fg="#0f172a",
            font=("Segoe UI", 14, "bold"),
        )
        title_lbl.pack(anchor="w")
        sub_lbl = tk.Label(
            header,
            text="Decode manifest, change package name, rebuild, and sign with a debug key.",
            bg=self.bg_color,
            fg="#475569",
            font=("Segoe UI", 9),
        )
        sub_lbl.pack(anchor="w")

        # Card 1: APK & Package Settings
        pkg_card = ttk.Labelframe(outer, text="1. APK & Package Configuration", padding=12)
        pkg_card.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(pkg_card, text="Source APK:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=5)
        self.path_var = tk.StringVar()
        ttk.Entry(pkg_card, textvariable=self.path_var, font=("Consolas", 9), state="readonly").grid(
            row=0, column=1, sticky="ew", pady=5
        )
        self.upload_btn = ttk.Button(pkg_card, text="Upload APK", command=self.upload_apk)
        self.upload_btn.grid(row=0, column=2, padx=(8, 0), pady=5)

        ttk.Label(pkg_card, text="Current Package:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=5)
        self.current_pkg_var = tk.StringVar(value="(No APK loaded)")
        ttk.Entry(
            pkg_card, textvariable=self.current_pkg_var, font=("Consolas", 9), state="readonly"
        ).grid(row=1, column=1, columnspan=2, sticky="ew", pady=5)

        ttk.Label(pkg_card, text="New Package:").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=5)
        self.new_pkg_var = tk.StringVar()
        self.new_pkg_entry = ttk.Entry(pkg_card, textvariable=self.new_pkg_var, font=("Consolas", 9))
        self.new_pkg_entry.grid(row=2, column=1, columnspan=2, sticky="ew", pady=5)

        self.update_refs_var = tk.BooleanVar(value=True)
        self.refs_chk = ttk.Checkbutton(
            pkg_card,
            text="Expand relative component names & update provider authorities (recommended for side-by-side install)",
            variable=self.update_refs_var,
        )
        self.refs_chk.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 2))

        pkg_card.columnconfigure(1, weight=1)

        # Card 2: Dependencies & Live Conversion Progress
        prog_card = ttk.Labelframe(outer, text="2. Tools & Conversion Progress", padding=12)
        prog_card.pack(fill=tk.X, pady=(0, 12))

        deps_row = ttk.Frame(prog_card)
        deps_row.pack(fill=tk.X, pady=(0, 8))
        self.deps_var = tk.StringVar(value="Checking Java, apktool.jar, and uber-apk-signer.jar...")
        ttk.Label(deps_row, textvariable=self.deps_var, style="Muted.TLabel").pack(side=tk.LEFT)
        self.dl_btn = ttk.Button(
            deps_row,
            text="Sync / Update Tools",
            command=lambda: self.ensure_dependencies_async(prompt_on_error=True, force=True),
        )
        self.dl_btn.pack(side=tk.RIGHT)

        bar_row = ttk.Frame(prog_card)
        bar_row.pack(fill=tk.X, pady=(0, 6))
        self.pct_var = tk.StringVar(value="0%")
        self.progress = ttk.Progressbar(bar_row, orient="horizontal", mode="determinate", maximum=100, value=0)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        ttk.Label(bar_row, textvariable=self.pct_var, style="Pct.TLabel", width=5, anchor="e").pack(side=tk.RIGHT)

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(prog_card, textvariable=self.status_var, style="Status.TLabel", wraplength=610).pack(anchor="w")

        # Action Bar
        btn_bar = ttk.Frame(outer)
        btn_bar.pack(fill=tk.X, pady=(2, 0))

        self.save_btn = ttk.Button(
            btn_bar, text="Convert & Save As...", command=self.save_apk, state="disabled"
        )
        self.save_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self.save_close_btn = ttk.Button(
            btn_bar, text="Convert, Save & Close", style="Accent.TButton", command=self.save_and_close, state="disabled"
        )
        self.save_close_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self.close_btn = ttk.Button(btn_bar, text="Close", command=self.close_app)
        self.close_btn.pack(side=tk.RIGHT)

    def _set_progress(self, percent: int, message: str | None = None) -> None:
        clamped = max(0, min(100, int(percent)))

        def apply() -> None:
            self.progress["value"] = clamped
            self.pct_var.set(f"{clamped}%")
            if message is not None:
                self.status_var.set(message)
            self.root.update_idletasks()

        self.root.after(0, apply)

    def _set_busy(self, is_busy: bool) -> None:
        self.busy = is_busy
        state = "disabled" if is_busy else "normal"
        has_apk = bool(self.apk_path and self.current_package)
        save_state = "disabled" if (is_busy or not has_apk) else "normal"

        def apply() -> None:
            self.upload_btn.config(state=state)
            self.dl_btn.config(state=state)
            self.new_pkg_entry.config(state=state)
            self.refs_chk.config(state=state)
            self.close_btn.config(state=state)
            self.save_btn.config(state=save_state)
            self.save_close_btn.config(state=save_state)

        self.root.after(0, apply)

    def _refresh_deps_label(self) -> None:
        has_java = shutil.which("java") is not None
        has_apktool = os.path.isfile(self.apktool_jar)
        has_signer = os.path.isfile(self.signer_jar)
        text = (
            f"Java: {'Ready' if has_java else 'Missing'}   •   "
            f"apktool.jar: {'Ready' if has_apktool else 'Missing'}   •   "
            f"uber-apk-signer.jar: {'Ready' if has_signer else 'Missing'}"
        )
        self.root.after(0, lambda: self.deps_var.set(text))

    def _resolve_latest_jar_url(self, api_url: str, pattern: str, fallback_url: str) -> str:
        req = urllib.request.Request(
            api_url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github+json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for asset in data.get("assets", []):
                    name = asset.get("name", "")
                    dl_url = asset.get("browser_download_url", "")
                    if re.search(pattern, name, re.IGNORECASE) and dl_url:
                        return dl_url
        except Exception:
            pass
        return fallback_url

    def _download_file(self, url: str, dest_path: str, start_pct: int, end_pct: int, label: str) -> None:
        tmp_path = dest_path + ".part"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(tmp_path, "wb") as out:
            total_hdr = resp.headers.get("Content-Length")
            total = int(total_hdr) if total_hdr and total_hdr.isdigit() else 0
            downloaded = 0
            chunk_size = 65536
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    frac = min(1.0, downloaded / total)
                    pct = start_pct + int(frac * (end_pct - start_pct))
                    self._set_progress(pct, f"{label} ({downloaded // 1024} KB / {total // 1024} KB)")
        os.replace(tmp_path, dest_path)
        self._set_progress(end_pct, f"{label} complete.")

    def ensure_dependencies_async(self, prompt_on_error: bool = True, force: bool = False) -> None:
        if self.busy:
            return

        def worker() -> None:
            self._set_busy(True)
            errors: list[str] = []
            self._set_progress(5, "Checking required dependencies...")

            if shutil.which("java") is None:
                errors.append("Java runtime ('java') was not found in PATH.")

            need_apktool = force or not os.path.isfile(self.apktool_jar)
            need_signer = force or not os.path.isfile(self.signer_jar)

            if need_apktool:
                self._set_progress(15, "Resolving latest apktool release...")
                try:
                    url = self._resolve_latest_jar_url(
                        APKTOOL_API, r"^apktool.*\.jar$", APKTOOL_FALLBACK_URL
                    )
                    self._download_file(url, self.apktool_jar, 15, 55, "Downloading apktool.jar")
                except (urllib.error.URLError, OSError) as exc:
                    errors.append(f"Failed to download apktool.jar: {exc}")
            else:
                self._set_progress(55, "apktool.jar found locally.")

            if need_signer:
                self._set_progress(60, "Resolving latest uber-apk-signer release...")
                try:
                    url = self._resolve_latest_jar_url(
                        SIGNER_API, r"^uber-apk-signer.*\.jar$", SIGNER_FALLBACK_URL
                    )
                    self._download_file(url, self.signer_jar, 60, 95, "Downloading uber-apk-signer.jar")
                except (urllib.error.URLError, OSError) as exc:
                    errors.append(f"Failed to download uber-apk-signer.jar: {exc}")
            else:
                self._set_progress(95, "uber-apk-signer.jar found locally.")

            self._refresh_deps_label()
            self._set_busy(False)

            if errors:
                self._set_progress(0, "Dependency check failed: " + " | ".join(errors))
                if prompt_on_error:
                    self.root.after(0, lambda: messagebox.showerror("Dependencies", "\n".join(errors)))
            else:
                self._set_progress(100, "All tools ready. Upload an APK to convert.")

        threading.Thread(target=worker, daemon=True).start()

    def _run_java_jar(self, jar_path: str, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(["java", "-jar", jar_path] + args, capture_output=True, text=True, check=False)

    def upload_apk(self) -> None:
        if self.busy:
            return
        selected = filedialog.askopenfilename(
            title="Select an APK file",
            filetypes=[("Android Package", "*.apk"), ("All Files", "*.*")],
        )
        if not selected:
            return

        self.apk_path = selected
        self.path_var.set(selected)
        self._set_progress(10, "Reading package name from APK...")

        pkg = self._read_package_name(selected)
        if pkg:
            self.current_package = pkg
            self.current_pkg_var.set(pkg)
            self.new_pkg_var.set(pkg)
            self.save_btn.config(state="normal")
            self.save_close_btn.config(state="normal")
            self._set_progress(0, f"Loaded {os.path.basename(selected)} — Current package: {pkg}")
        else:
            self.current_package = ""
            self.current_pkg_var.set("(Could not read package name)")
            self.new_pkg_var.set("")
            self.save_btn.config(state="disabled")
            self.save_close_btn.config(state="disabled")
            self._set_progress(0, "Could not read package name. Check Java and apktool.jar.")
            messagebox.showwarning("Read Failed", "Could not read package name from the selected APK.")

    def _read_package_name(self, apk_file: str) -> str:
        for tool in ("aapt2", "aapt"):
            tool_path = shutil.which(tool)
            if not tool_path:
                continue
            cmd = (
                [tool_path, "dump", "badging", apk_file]
                if tool == "aapt"
                else [tool_path, "dump", "xmltree", "--file", "AndroidManifest.xml", apk_file]
            )
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            for line in (proc.stdout or "").splitlines():
                if tool == "aapt" and line.startswith("package:"):
                    m = re.search(r"name=['\"]([^'\"]+)['\"]", line)
                    if m:
                        return m.group(1)
                elif tool == "aapt2" and "A: package=" in line:
                    m = re.search(r'package="([^"]+)"', line)
                    if m:
                        return m.group(1)

        if os.path.isfile(self.apktool_jar) and shutil.which("java"):
            with tempfile.TemporaryDirectory() as tmpdir:
                out_dir = os.path.join(tmpdir, "dec")
                proc = self._run_java_jar(self.apktool_jar, ["d", "-f", "-s", apk_file, "-o", out_dir])
                manifest = os.path.join(out_dir, "AndroidManifest.xml")
                if proc.returncode == 0 and os.path.isfile(manifest):
                    tree = ET.parse(manifest)
                    pkg = tree.getroot().attrib.get("package", "")
                    if pkg:
                        return pkg
        return ""

    @staticmethod
    def _is_valid_package_name(pkg: str) -> bool:
        if not pkg or "." not in pkg:
            return False
        for part in pkg.split("."):
            if not part or not part[0].isalpha():
                return False
            if not all(ch.isalnum() or ch == "_" for ch in part):
                return False
        return True

    def _patch_manifest(self, manifest_path: str, old_pkg: str, new_pkg: str, update_refs: bool) -> None:
        ET.register_namespace("android", "http://schemas.android.com/apk/res/android")
        android_ns = "{http://schemas.android.com/apk/res/android}"

        tree = ET.parse(manifest_path)
        root = tree.getroot()
        root.set("package", new_pkg)

        if update_refs:
            component_tags = ("activity", "activity-alias", "service", "receiver", "provider")
            for elem in root.iter():
                tag_name = elem.tag.split("}")[-1]
                if tag_name in component_tags:
                    name_attr = elem.get(f"{android_ns}name")
                    if name_attr and name_attr.startswith("."):
                        elem.set(f"{android_ns}name", old_pkg + name_attr)
                    elif name_attr and "." not in name_attr:
                        elem.set(f"{android_ns}name", f"{old_pkg}.{name_attr}")

                if tag_name == "provider":
                    auth = elem.get(f"{android_ns}authorities")
                    if auth and old_pkg in auth:
                        elem.set(f"{android_ns}authorities", auth.replace(old_pkg, new_pkg))

        tree.write(manifest_path, encoding="utf-8", xml_declaration=True)

    def _convert_worker(self, src_apk: str, dst_apk: str, old_pkg: str, new_pkg: str, close_after: bool) -> None:
        self._set_busy(True)
        try:
            self._set_progress(5, "Verifying Java runtime and tool JARs...")
            if shutil.which("java") is None:
                self._set_progress(0, "Java ('java') not found in PATH.")
                self.root.after(0, lambda: messagebox.showerror("Missing Java", "Java ('java') is required in PATH."))
                return

            if not os.path.isfile(self.apktool_jar):
                url = self._resolve_latest_jar_url(APKTOOL_API, r"^apktool.*\.jar$", APKTOOL_FALLBACK_URL)
                self._download_file(url, self.apktool_jar, 5, 15, "Downloading apktool.jar")

            if not os.path.isfile(self.signer_jar):
                url = self._resolve_latest_jar_url(SIGNER_API, r"^uber-apk-signer.*\.jar$", SIGNER_FALLBACK_URL)
                self._download_file(url, self.signer_jar, 15, 25, "Downloading uber-apk-signer.jar")

            self._refresh_deps_label()

            with tempfile.TemporaryDirectory() as tmpdir:
                decoded_dir = os.path.join(tmpdir, "decoded")
                rebuilt_apk = os.path.join(tmpdir, "rebuilt_unsigned.apk")
                signed_dir = os.path.join(tmpdir, "signed_out")
                os.makedirs(signed_dir, exist_ok=True)

                # 25% -> 50%: Decode APK
                self._set_progress(28, "Decoding APK resources and manifest...")
                dec_proc = self._run_java_jar(self.apktool_jar, ["d", "-f", "-s", src_apk, "-o", decoded_dir])
                if dec_proc.returncode != 0:
                    err = dec_proc.stderr or dec_proc.stdout
                    self._set_progress(0, "Decode failed.")
                    self.root.after(0, lambda: messagebox.showerror("Decode Failed", f"apktool failed:\n{err}"))
                    return
                self._set_progress(50, "Decoded APK manifest and resources.")

                # 50% -> 62%: Patch AndroidManifest.xml
                self._set_progress(55, f"Updating package name to '{new_pkg}'...")
                manifest_path = os.path.join(decoded_dir, "AndroidManifest.xml")
                try:
                    self._patch_manifest(manifest_path, old_pkg, new_pkg, self.update_refs_var.get())
                except Exception as exc:
                    self._set_progress(0, "Manifest update failed.")
                    self.root.after(0, lambda: messagebox.showerror("Manifest Error", str(exc)))
                    return
                self._set_progress(62, "AndroidManifest.xml updated.")

                # 62% -> 85%: Rebuild APK
                self._set_progress(66, "Rebuilding APK archive...")
                bld_proc = self._run_java_jar(self.apktool_jar, ["b", decoded_dir, "-o", rebuilt_apk])
                if bld_proc.returncode != 0 or not os.path.isfile(rebuilt_apk):
                    err = bld_proc.stderr or bld_proc.stdout
                    self._set_progress(0, "Rebuild failed.")
                    self.root.after(0, lambda: messagebox.showerror("Build Failed", f"apktool build failed:\n{err}"))
                    return
                self._set_progress(85, "Rebuilt APK archive.")

                # 85% -> 98%: Align & Sign APK
                self._set_progress(88, "Aligning and signing APK with debug certificate...")
                sign_proc = self._run_java_jar(self.signer_jar, ["-a", rebuilt_apk, "-o", signed_dir])
                signed_files = [f for f in os.listdir(signed_dir) if f.endswith(".apk")]
                if sign_proc.returncode != 0 or not signed_files:
                    err = sign_proc.stderr or sign_proc.stdout
                    self._set_progress(0, "Signing failed.")
                    self.root.after(0, lambda: messagebox.showerror("Signing Failed", f"uber-apk-signer failed:\n{err}"))
                    return

                preferred = next((f for f in signed_files if "aligned-debugSigned" in f), signed_files[0])
                shutil.copy2(os.path.join(signed_dir, preferred), dst_apk)

            # 100%: Complete
            self._set_progress(100, f"Completed (100%) — Saved to {dst_apk}")

            def finish_ui() -> None:
                messagebox.showinfo("Conversion Complete", f"Renamed and signed APK saved to:\n{dst_apk}")
                if close_after:
                    self.root.destroy()

            self.root.after(0, finish_ui)
        finally:
            self._set_busy(False)

    def _start_conversion(self, close_after: bool) -> None:
        if self.busy:
            return
        new_pkg = self.new_pkg_var.get().strip()
        if not self._is_valid_package_name(new_pkg):
            messagebox.showerror(
                "Invalid Package Name",
                "Enter a valid Android package name (e.g., com.example.myapp) with at least two dot-separated segments.",
            )
            return

        base_name = os.path.splitext(os.path.basename(self.apk_path))[0]
        default_name = f"{base_name}_{new_pkg}_signed.apk"
        dst_path = filedialog.asksaveasfilename(
            title="Save Converted APK As",
            initialfile=default_name,
            defaultextension=".apk",
            filetypes=[("Android Package", "*.apk")],
        )
        if not dst_path:
            return

        threading.Thread(
            target=self._convert_worker,
            args=(self.apk_path, dst_path, self.current_package, new_pkg, close_after),
            daemon=True,
        ).start()

    def save_apk(self) -> None:
        self._start_conversion(close_after=False)

    def save_and_close(self) -> None:
        self._start_conversion(close_after=True)

    def close_app(self) -> None:
        if not self.busy:
            self.root.destroy()


if __name__ == "__main__":
    app_root = tk.Tk()
    ApkRenamerModernGUI(app_root)
    app_root.mainloop()
