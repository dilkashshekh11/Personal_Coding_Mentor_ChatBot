<<<<<<< HEAD
# Personal_Coding_Mentor_ChatBot
Built Dilkash AI, a personal AI-powered study and coding assistant using Python, Flask, and Google Gemini API. Features include code generation, debugging, code explanations, programming tutoring, quiz generation, study notes, multilingual support (English, Nepali &amp; Hindi), user authentication, and chat history—all in one platform.
=======
# Dilkash AI

A study and coding assistant with user accounts. Built with Python, Flask and the Google Gemini API.

## What it does

- **Accounts** - create a username and password, log in, add a photo and name on the Profile page. Every person sees only their own chats and code checks.
- **Fix My Code** - paste or upload Python code and get what is wrong, how to fix it and the corrected code.
- **Assistant** - Chat, Generate code, Explain code, Fix errors, Programming tutor, Summarize text, Quiz generator and Study notes. Pick a colored tag, then type.
- **Languages** - replies in English, Nepali or Hindi.
- **Follow-up questions** - the assistant remembers the earlier messages of the same chat.
- **History** - chats and code checks in one list. Open or delete them.

## How to run it

1. Open a terminal inside the `dilkash-ai` folder. Keep `templates` and `static` next to `app.py`.
2. Install Python 3.10 or newer, then the packages:

   ```
   python -m pip install -r requirements.txt
   ```

3. Get a free API key at https://aistudio.google.com/apikey and paste it into `.env`:

   ```
   GEMINI_API_KEY=your_real_key_here
   GEMINI_MODEL=gemini-3.8-flash
   GEMINI_FALLBACK_MODELS=gemini-2.5-flash,gemini-2.5-flash-lite
   ```

4. Start the app:

   ```
   python app.py
   ```

   The browser opens on the sign-up page. Create your account, then use the app.

## Why answers can be slow, and what the app does about it

Most of the waiting time is the Google model itself. When it is busy, Google answers "503 high demand".
The app now:

- tries a busy model once more, then switches to the backup models in `GEMINI_FALLBACK_MODELS`
- turns thinking off and asks for short, direct answers
- sends only the last 10 messages of a chat
- connects to Google at start-up, so the first question is not slower

If the main model is often busy, put a steadier model name in `GEMINI_MODEL`.
Model names change over time. If you see "model not available", check the current names at https://ai.google.dev/gemini-api/docs/models.

## Project files

```
app.py                server, accounts, modes and database
templates/            the pages (HTML)
static/style.css      the look
static/app.js         menu, copy buttons, text formatting
static/fix.js         Fix My Code page
static/chat.js        Assistant page
uploads/              profile photos (created automatically)
requirements.txt      packages to install
.env                  your API key and settings (keep it private)
```

## Notes

- Passwords are stored as hashes, never as plain text.
- The first account you create also receives any history saved before accounts existed.
- This is built to run on your own computer. Before putting it on the internet, use HTTPS and set a `SECRET_KEY` in `.env`.
- Never share your `.env` file. It holds your API key.

## License

MIT
>>>>>>> bb6fedb (Add all initial files)
