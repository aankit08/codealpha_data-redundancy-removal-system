# DataGuard — Data Redundancy Removal System

A local Flask + SQLite prototype for exact duplicate detection, similar-record review, verified record storage, and an audit log.

## Windows quick start
1. Extract the entire ZIP into a normal folder (do not run it from inside the ZIP preview).
2. Double-click `START_DataGuard.bat`.
3. Keep the terminal window open and visit `http://127.0.0.1:5000`.
4. The launcher creates `.venv` and installs Flask on first run. Internet access is needed for the initial install.

If double-click closes immediately, open Command Prompt in this folder (File Explorer address bar: type `cmd` and press Enter), then run `START_DataGuard.bat` to see any error.

## Behavior
- Exact normalized matches are blocked using a SHA-256 fingerprint and a database uniqueness constraint.
- Similar records are flagged for manual review and are **not saved automatically**.
- On the review screen, a reviewer can confirm a genuinely distinct record or reject the candidate.
- `/api/check` is a classification-only endpoint; it does not save records.
- `/health` returns service status; `/api/records` returns saved records.
- Data is stored in `dataguard.db` beside `app.py`.

## API example (Command Prompt)
```cmd
.venv\Scripts\python.exe -c "import urllib.request,json; d=json.dumps({'title':'API Demo','category':'IT','content':'An example record.'}).encode(); r=urllib.request.Request('http://127.0.0.1:5000/api/check',data=d,headers={'Content-Type':'application/json'},method='POST'); print(urllib.request.urlopen(r).read().decode())"
```

## Notes
This is a local demonstration prototype, not a production cloud deployment. Similarity scoring is heuristic and should be tuned/tested with representative data before real use. Do not use the development server for public internet deployment.
