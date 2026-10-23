# 🤖 Dilkash AI — Personal Coding Mentor ChatBot

A personal AI-powered study and coding assistant built with **Python, Flask, and the Google Gemini API**. Dilkash AI helps users learn programming, generate code, debug errors, understand concepts, and improve their coding skills through an interactive, multilingual AI assistant.

## ✨ Features

- 🤖 **AI Chatbot:** Ask programming questions and receive AI-powered answers.
- 💻 **Code Generation:** Generate code based on your requirements.
- 🐛 **Fix My Code:** Paste or upload Python code to identify errors, understand issues, and get corrected code.
- 📚 **Code Explanation:** Understand programming logic and code functionality in simple language.
- 👨‍🏫 **Programming Tutor:** Learn programming concepts with AI-guided explanations.
- 📝 **Quiz Generator:** Generate quizzes to test your programming knowledge.
- 📖 **Study Notes:** Create useful study notes from your learning topics.
- 🌐 **Multilingual Support:** Interact with the assistant in English, Nepali, and Hindi.
- 👤 **User Authentication:** Create an account, log in, and manage your personal profile.
- 💬 **Chat History:** Save, revisit, and delete previous conversations and code checks.
- 🔄 **Contextual Conversations:** Ask follow-up questions based on earlier messages in the same chat.
- 🎨 **User-Friendly Interface:** Access different assistant features through a simple, organized interface.

## 🛠️ Technologies Used

- **Python** – Core programming language and application logic.
- **Flask** – Backend web framework.
- **Google Gemini API** – AI-powered chat, programming assistance, and content generation.
- **HTML5** – Structures the web application.
- **CSS3** – Styles the interface and layout.
- **JavaScript** – Handles frontend interactions and dynamic functionality.
- **Database** – Stores user accounts, chat history, and code-check records.
- **Python Libraries** – Additional packages required to run the application.

## 🚀 Getting Started

Follow these steps to run the project on your computer.

### 1. Clone the Repository

```bash
git clone https://github.com/dilkashshekh11/Personal_Coding_Mentor_ChatBot.git
```

### 2. Open the Project

```bash
cd Personal_Coding_Mentor_ChatBot
```

Open the project folder in Visual Studio Code or your preferred code editor.

### 3. Install Python Dependencies

Make sure Python 3.10 or newer is installed.

```bash
python -m pip install -r requirements.txt
```

### 4. Get a Google Gemini API Key

- Visit [Google AI Studio](https://aistudio.google.com/apikey).
- Create or sign in to your Google account.
- Generate an API key.

### 5. Configure Environment Variables

Create a `.env` file in the project root directory and add your API key and model settings.

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_FALLBACK_MODELS=gemini-2.5-flash-lite
```

Use model names currently supported by your Gemini API account. The values above are examples and may need updating.

**Important:** Never upload your real API key or `.env` file to GitHub.

### 6. Run the Application

```bash
python app.py
```

Open the local URL displayed in your terminal if the browser does not open automatically. Create an account and start using Dilkash AI.

## 📂 Project Structure

```text
Personal_Coding_Mentor_ChatBot/
│
├── app.py                  # Flask application and backend logic
├── templates/              # HTML templates and application pages
├── static/
│   ├── style.css           # Application styling
│   ├── app.js              # Shared frontend functionality
│   ├── chat.js             # Assistant page functionality
│   └── fix.js              # Fix My Code functionality
├── uploads/                 # Profile photos (created automatically)
├── requirements.txt        # Python dependencies
├── .env                    # Private API keys and configuration
├── .gitignore              # Files excluded from Git
└── README.md               # Project documentation
```

## 📸 How It Works

1. Create an account or log in to your existing account.
2. Open the AI Assistant or Fix My Code section.
3. Enter a programming question, request code, or submit code for debugging.
4. The application sends the request to the Google Gemini API.
5. Review the AI-generated explanation, code, or learning materials.
6. Continue the conversation with follow-up questions.
7. Revisit your saved conversations and code checks through the history section.

## 🎯 Project Purpose

Dilkash AI was developed to make programming education more accessible through AI-powered learning assistance. The project combines web development, API integration, user authentication, database management, and generative AI to create a personal coding mentor for students and programming enthusiasts.

## 👨‍💻 Developer

**Dilkash Shekh**

BSc (Hons) Computer Science with AI Student | AI Enthusiast | Python Developer | Technology Enthusiast

- **GitHub:** [@dilkashshekh11](https://github.com/dilkashshekh11)

## 🔐 Security Note

- Keep your Gemini API key and `.env` file private.
- Use secure password hashing for account credentials.
- Set a strong Flask `SECRET_KEY` through environment variables.
- Before deploying publicly, configure HTTPS, secure session cookies, production-grade settings, and appropriate upload validation.
- Review database access and user authorization to ensure that users can access only their own data.

## 📄 License

This project is intended for educational and personal learning purposes. Add a `LICENSE` file to specify the terms under which others may use, modify, or distribute the project.

---

⭐ If you find Dilkash AI useful, consider giving the repository a star on GitHub!
