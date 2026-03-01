# How to Push Changes to GitHub and Hugging Face

Follow these steps from your project folder (e.g. `my-appointment-assistant` or your repo root).

---

## Prerequisites

- **Git** installed ([git-scm.com](https://git-scm.com))
- **GitHub account** and (optional) **Hugging Face account**
- **GitHub**: a repository created on GitHub (empty or with initial commit)
- **Hugging Face**: you already have an existing Space to push to

---

## Part 1: Push to GitHub

### If this folder is not yet a Git repo

```powershell
cd C:\Users\sukh1\my-appointment-assistant

git init
git add .
git commit -m "Initial commit: Appointment Assistant with cancel/reschedule/confirm flows"
```

### If it is already a Git repo (just commit your changes)

```powershell
cd C:\Users\sukh1\my-appointment-assistant

git add .
git status
git commit -m "Cancel/reschedule/delete: list appointments when vague, confirm before book/cancel/reschedule"
```

### Add GitHub as remote and push

Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your GitHub username and repository name (e.g. `my-appointment-assistant`).

```powershell
# Add GitHub remote (only needed once)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# If you already have 'origin' but want to point to a new URL:
# git remote set-url origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# Push (first time: set upstream branch)
git push -u origin main
```

If your default branch is `master` instead of `main`:

```powershell
git push -u origin master
```

- **First time:** GitHub may ask you to sign in (browser or credential manager).
- If the repo already has commits (e.g. README), do a pull first:  
  `git pull origin main --rebase`  
  then  
  `git push -u origin main`.

---

## Part 2: Push to Your Existing Hugging Face Space

You already have a Space. Add it as a remote and push your local code there.

### 1. Get your Space URL

- Open your Space on Hugging Face (e.g. `https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME`).
- Click **"Clone repository"** or open the **Files** tab; the Git URL is shown (e.g. `https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME`). The URL you use for push is that + `.git`.

### 2. Add the Space as a remote and push

Run these in your project folder. Replace `YOUR_USERNAME` and `YOUR_SPACE_NAME` with your actual Hugging Face username and Space name.

```powershell
cd C:\Users\sukh1\my-appointment-assistant

# Add your existing Space as a remote (only needed once)
git remote add huggingface https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME.git
```

If you already added a remote named `huggingface` and want to point it at this Space:

```powershell
git remote set-url huggingface https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME.git
```

Then push (use `main` or the branch your Space uses):

```powershell
git push huggingface main
```

- If Git asks for login, use your Hugging Face token (Settings → Access Tokens on huggingface.co). When prompted for password, paste the token.

---

## Quick reference

| Task                    | Command |
|-------------------------|--------|
| Commit changes          | `git add .` then `git commit -m "Your message"` |
| Push to GitHub          | `git push origin main` (or `master`) |
| Push to Hugging Face    | `git push huggingface main` |
| See remotes             | `git remote -v` |
| See status              | `git status` |

---

## Summary

1. **Commit** your changes: `git add .` → `git commit -m "Description of changes"`.
2. **GitHub:** Add `origin` if needed, then `git push -u origin main`.
3. **Hugging Face (existing Space):** Add your Space as `huggingface` remote once, then `git push huggingface main`.

After that, push to both whenever you have new commits: `git push origin main` and `git push huggingface main`.
