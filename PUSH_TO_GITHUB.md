# Push Nhanh Tu VSCode (Windows)

## 1) Tao repo tren GitHub
- Tao repo rong (khong add README/.gitignore moi).
- Copy URL repo, vi du:
  - `https://github.com/<username>/<repo>.git`

## 2) Chay lenh trong Terminal VSCode tai thu muc project
```bash
git status
git add .
git commit -m "Add chat backend + Android APK build workflow"
git branch -M main
git remote remove origin 2>nul || true
git remote add origin https://github.com/<username>/<repo>.git
git push -u origin main
```

Neu terminal cua ban la PowerShell va lenh `2>nul || true` khong hop le, dung:
```powershell
git remote remove origin
git remote add origin https://github.com/<username>/<repo>.git
git push -u origin main
```

## 3) Build APK tren GitHub Actions
1. Vao tab `Actions`.
2. Chon workflow `Build Android APK`.
3. Bam `Run workflow`.
4. Tai artifact `appchat-apk`.
