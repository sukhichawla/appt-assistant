# Prepare Repo and Get a Working Link Using Hugging Face

Follow these steps to put your Appointment Assistant on GitHub and run it as a **Hugging Face Space** so you get a **public working link**.

---

## 1. Prepare the repo (folder structure)

Hugging Face will run your app from the **repository root**. Your app expects to live inside a folder named `appointment_assistant`, so the repo root must **contain** that folder.

**Option A – You already have a parent folder as repo root (recommended)**  
Example: you have `C:\Users\sukh1\my-appointment-assistant\` and inside it the folder `appointment_assistant\` with all the code. Then:

- Repo root = `my-appointment-assistant`
- Inside it: `appointment_assistant\` (with `streamlit_app.py`, `agents.py`, etc.)

**Option B – Your repo is only the `appointment_assistant` folder**  
If you run `git init` inside `appointment_assistant`, the repo root is `appointment_assistant`. To match what Hugging Face expects:

1. Create a **new folder** one level up, e.g. `appointment-assistant-repo`.
2. **Move** the contents of `appointment_assistant` into a subfolder named `appointment_assistant` inside that new folder.
3. Use that new folder as the repo root (so you have `appointment-assistant-repo\appointment_assistant\...`).

---

## 2. Put `requirements.txt` at the repo root

Hugging Face looks for **`requirements.txt` in the root** of the repo.

Create (or copy) **`requirements.txt`** in the **repo root** (same level as the `appointment_assistant` folder). You can copy from `appointment_assistant/requirements.txt` if your repo root contains that folder. It should contain:

```text
streamlit
python-dateutil>=2.9.0.post0
```

So the layout is:

```text
<repo_root>/
├── appointment_assistant/
│   ├── __init__.py
│   ├── streamlit_app.py
│   ├── agents.py
│   ├── calendar_store.py
│   ├── main.py
│   └── ...
├── requirements.txt
├── README.md
└── .gitignore
```

---

## 3. Push the repo to GitHub

From the **repo root** folder (the one that contains `appointment_assistant` and `requirements.txt`):

```bash
git init
git add .
git commit -m "Appointment Assistant – multi-agent Streamlit app"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your GitHub username and repository name. Create the repository on GitHub first (empty, no README) if needed.

---

## 4. Create a Hugging Face Space and get the working link

1. Go to **https://huggingface.co/spaces** and sign in.
2. Click **“Create new Space”**.
3. Set:
   - **Space name:** e.g. `appointment-assistant`
   - **License:** e.g. MIT (or your choice)
   - **SDK:** **Streamlit**
   - **Space hardware:** Free (or upgrade if you want)
4. Under **“Repository”**, choose **“Import from GitHub”** (or similar) and connect your GitHub account, then select the repo you pushed.
   - Alternatively, create the Space first, then in **Settings** → **Repository** connect the GitHub repo or copy the repo contents into the Space repo.
5. **App file (critical):**  
   In the Space settings or in the Space’s **README** (if HF uses it for config), set the **Streamlit app file** to:
   ```text
   appointment_assistant/streamlit_app.py
   ```
   So Hugging Face runs:
   ```text
   streamlit run appointment_assistant/streamlit_app.py
   ```
   with the **working directory = repo root**. That way `appointment_assistant` is found as a package and the app starts correctly.
6. If the Space was created empty (no GitHub import), clone the Space repo, add your code (including `appointment_assistant/` and root `requirements.txt`), then push.
7. Wait for the Space to **build** (it installs from `requirements.txt` and runs the app). When it’s ready, the Space page will show your app.

Your **working link** will be:

```text
https://huggingface.co/spaces/YOUR_HF_USERNAME/appointment-assistant
```

(Use your actual Space name and HF username.)

---

## 5. If the Space repo is created empty (no GitHub import)

Some flows create an empty Space repo. Then:

1. Clone the Space (HF shows the clone URL):
   ```bash
   git clone https://huggingface.co/spaces/YOUR_HF_USERNAME/appointment-assistant
   cd appointment-assistant
   ```
2. Copy into this folder:
   - the whole **`appointment_assistant`** directory (with all Python files),
   - **`requirements.txt`** at the root (with `streamlit` and `python-dateutil`).
3. Commit and push:
   ```bash
   git add .
   git commit -m "Add Appointment Assistant app"
   git push
   ```
4. The Space will rebuild; the same link as above will then open your running app.

---

## 6. Quick checklist

- [ ] Repo root **contains** a folder named **`appointment_assistant`** (with `streamlit_app.py`, `agents.py`, etc.).
- [ ] **`requirements.txt`** is at the **repo root** and lists `streamlit` and `python-dateutil`.
- [ ] Code is pushed to **GitHub** (or to the HF Space repo).
- [ ] Hugging Face Space is set to **Streamlit** and the app file is **`appointment_assistant/streamlit_app.py`**.
- [ ] Build finished without errors; the Space URL is your **working link**.

Using this, your repo is prepared and you get a working link using Hugging Face.
