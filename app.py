import os
import datetime
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

class AntigravityAI:
    def __init__(self):
        self.api_key = os.getenv("OMNIROUTE_API_KEY", "sk-omni-anyth...")
        self.project = os.getenv("PROJECT_NAME", "antigravity")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://punctured-old-playmaker.ngrok-free.dev/v1"
        )
        self.model = "openai/gpt-oss-120b"
        self.history_file = "chat_history.md"
        self.modes = {
            "coder": "You are an expert programmer. Write clean, optimized, well-documented code.",
            "teacher": "You are a patient teacher. Explain concepts simply with examples.",
            "hacker": "You are a cybersecurity expert. Show secure coding practices and vulnerability analysis.",
            "default": "You are a helpful coding assistant."
        }
        self.messages = [
            {"role": "system", "content": self.modes["coder"]}
        ]
        self._init_history()

    def _init_history(self):
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write("
--- New Session: %s ---

" % datetime.datetime.now())

    def ask(self, prompt):
        try:
            if prompt.lower().startswith("model "):
                self.model = prompt[6:].strip()
                return "[system] Model switched to: %s" % self.model

            if prompt.lower().startswith("mode "):
                mode_name = prompt[5:].strip().lower()
                if mode_name in self.modes:
                    self.messages = [
                        {"role": "system", "content": self.modes[mode_name]}
                    ]
                    return "[system] Mode switched to: %s" % mode_name.upper()
                else:
                    available = ", ".join(self.modes.keys())
                    return "[system] Unknown mode. Available: %s" % available

            if prompt.lower() == "export":
                return self._export_chat()

            self.messages.append({"role": "user", "content": prompt})
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                max_tokens=4000
            )
            reply = response.choices[0].message.content
            self.messages.append({"role": "assistant", "content": reply})

            self._save_to_history(prompt, reply)

            provider = response.model.split("/")[0] if "/" in str(response.model) else "unknown"
            return "[%s] %s" % (provider, reply)
        except Exception as e:
            return "Xato: %s" % str(e)

    def _save_to_history(self, prompt, reply):
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write("**User:** %s

" % prompt)
            f.write("**AI:** %s

---

" % reply)

    def _export_chat(self):
        filename = "export_%s.md" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(filename, "w", encoding="utf-8") as f:
            f.write("# Chat Export --- %s

" % datetime.datetime.now())
            f.write("**Model:** %s

" % self.model)
            for msg in self.messages:
                if msg["role"] == "user":
                    f.write("## User
%s

" % msg["content"])
                elif msg["role"] == "assistant":
                    f.write("## AI
%s

---

" % msg["content"])
        return "[system] Chat exported to: %s" % filename

    def clear_history(self):
        self.messages = [
            {"role": "system", "content": self.modes["coder"]}
        ]
        return "Suhbat tarixi tozalandi! Mode: CODER"

    def show_help(self):
        return """
[system] Available commands:
  model <name>     --- Switch AI model (e.g., model qwen/qwen3.6-27b)
  mode <name>      --- Switch personality (coder, teacher, hacker, default)
  clear             --- Clear conversation history
  export            --- Save full chat to markdown file
  help              --- Show this message
  exit              --- Quit
"""

if __name__ == "__main__":
    ai = AntigravityAI()
    print(">>> %s + OmniRoute ishga tushdi!" % ai.project)
    print("Model: %s | Mode: CODER" % ai.model)
    print("Commands: model, mode, clear, export, help, exit")
    print()
    while True:
        q = input("> ")
        if q.lower() in ["exit", "quit", "chiqish"]:
            break
        if q.lower() in ["clear", "tozala"]:
            print(ai.clear_history())
            continue
        if q.lower() in ["help", "yordam", "?"]:
            print(ai.show_help())
            continue
        print(ai.ask(q))
