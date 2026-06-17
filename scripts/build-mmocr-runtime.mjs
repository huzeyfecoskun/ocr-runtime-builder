import { existsSync, mkdirSync, copyFileSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

// fileURLToPath (not URL.pathname) — .pathname yields a drive-relative "/D:/..."
// which path.resolve re-prefixes with the current drive, doubling it on
// Windows (D:\D:\...). fileURLToPath converts file:// URLs to native paths.
const root = resolve(join(dirname(fileURLToPath(import.meta.url)), ".."));
const python = process.env.PYTHON ?? join(root, ".venv-paddle", process.platform === "win32" ? "Scripts" : "bin", process.platform === "win32" ? "python.exe" : "python");
const worker = join(root, "resources", "ocr", "mmocr-svtr-worker.py");
const modelSource = process.env.SVTR_MODEL ?? join(process.env.HOME ?? "", ".cache", "torch", "hub", "checkpoints", "svtr-small_20e_st_mj-35d800d6.pth");
const modelTargetDir = join(root, "resources", "ocr-models");
const modelTarget = join(modelTargetDir, "svtr-small_20e_st_mj-35d800d6.pth");
const platformDir = join(root, "resources", "ocr-runtime", `${process.platform}-${process.arch}`);
const pyInstallerRoot = join(tmpdir(), "nines-flow-mmocr-pyinstaller", `${process.platform}-${process.arch}`);
const distDir = join(pyInstallerRoot, "dist");
const buildDir = join(pyInstallerRoot, "build");

function run(command, args) {
  const res = spawnSync(command, args, { cwd: root, stdio: "inherit" });
  if (res.status !== 0) process.exit(res.status ?? 1);
}

if (!existsSync(python)) {
  console.error(`Python not found: ${python}`);
  process.exit(1);
}
if (!existsSync(worker)) {
  console.error(`Worker not found: ${worker}`);
  process.exit(1);
}
if (!existsSync(modelTarget)) {
  if (!existsSync(modelSource)) {
    console.error(`SVTR model not found. Expected ${modelTarget} or ${modelSource}`);
    process.exit(1);
  }
  mkdirSync(modelTargetDir, { recursive: true });
  copyFileSync(modelSource, modelTarget);
}

mkdirSync(platformDir, { recursive: true });
rmSync(pyInstallerRoot, { recursive: true, force: true });
mkdirSync(pyInstallerRoot, { recursive: true });

run(python, [
  "-c",
  "import mmcv, mmengine, mmdet, mmocr; print('OCR build imports OK:', mmcv.__version__, mmengine.__version__, mmdet.__version__, mmocr.__version__)",
]);

run(python, [
  "-m",
  "PyInstaller",
  "--onefile",
  "--clean",
  "--name",
  "mmocr-svtr-worker",
  "--distpath",
  distDir,
  "--workpath",
  buildDir,
  "--specpath",
  buildDir,
  "--collect-all",
  "mmocr",
  "--collect-all",
  "mmengine",
  "--collect-all",
  "mmcv",
  "--collect-submodules",
  "mmcv",
  "--collect-data",
  "mmcv",
  "--collect-binaries",
  "mmcv",
  "--hidden-import",
  "mmcv",
  "--collect-all",
  "mmdet",
  "--collect-all",
  "torchvision",
  worker,
]);

const exe = process.platform === "win32" ? "mmocr-svtr-worker.exe" : "mmocr-svtr-worker";
copyFileSync(join(distDir, exe), join(platformDir, exe));
rmSync(pyInstallerRoot, { recursive: true, force: true });
console.log(`Built ${join(platformDir, exe)}`);
