"""
Discussion Reply Quality Checker using local Ollama LLM.

Evaluates whether a student's discussion forum reply substantively
engages with the original post, or is just generic agreement/padding.
"""

import re
import subprocess
import time
import logging
import requests


SYSTEM_PROMPT = """You evaluate whether a student's discussion forum reply shows ANY intellectual engagement at all.

Mark the reply SUBSTANTIVE if it does ANY of these (even just one, even briefly):
- Mentions a specific idea, concept, event, or detail from the course or the post
- Connects the topic to the student's own life, identity, background, or experience
- Reflects on how the topic made them think or feel about something specific
- Applies a course concept or framework, even while agreeing
- Asks a genuine question or raises a what-if
- Offers a different angle, even a small one

Mark the reply NOT SUBSTANTIVE only if ALL of these are true:
- The student does not engage with any specific idea — they only express agreement or praise
- There is no personal reflection, no new connection, and no application of concepts
- The reply could be copy-pasted onto any post in the class and still make sense because it says nothing specific

When in doubt, mark SUBSTANTIVE. A reply that tries to engage intellectually — even clumsily — earns credit.

Respond with only: SUBSTANTIVE or NOT SUBSTANTIVE"""


class OllamaReplyChecker:
    """Checks discussion reply quality using a local Ollama model."""

    def __init__(self, model: str = "llama3.1:8b",
                 base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.logger = logging.getLogger("autograder_automation")
        self._available = None  # lazy check

    def _try_launch_ollama(self) -> bool:
        """Attempt to start the Ollama server in the background. Returns True if it comes up."""
        try:
            self.logger.info("      🚀 Ollama not running — attempting to start it...")
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Wait up to 10s for it to become reachable
            for _ in range(10):
                time.sleep(1)
                try:
                    r = requests.get(f"{self.base_url}/api/tags", timeout=2)
                    if r.status_code == 200:
                        self.logger.info("      ✅ Ollama started successfully")
                        return True
                except Exception:
                    pass
            self.logger.warning("      ⚠️  Ollama didn't come up in time — falling back to word-count-only")
            return False
        except FileNotFoundError:
            self.logger.warning("      ⚠️  ollama command not found — falling back to word-count-only")
            return False
        except Exception as e:
            self.logger.warning(f"      ⚠️  Failed to launch Ollama ({e}) — falling back to word-count-only")
            return False

    def _is_available(self) -> bool:
        """Check if Ollama is running and the model is available. Auto-launches if not running."""
        if self._available is not None:
            return self._available
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
        except Exception:
            # Not reachable — try to launch it
            if not self._try_launch_ollama():
                self._available = False
                return False
            try:
                r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            except Exception:
                self._available = False
                return False

        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            # Match model name with or without tag suffix
            self._available = any(
                m == self.model or m.startswith(self.model.split(":")[0])
                for m in models
            )
            if not self._available:
                self.logger.warning(
                    f"      ⚠️  Ollama running but model '{self.model}' "
                    f"not found. Available: {models}"
                )
        else:
            self._available = False
        return self._available

    def _clean_html(self, text: str) -> str:
        """Strip HTML tags from Canvas message content."""
        return re.sub(r'<[^>]+>', ' ', text or "").strip()

    def _truncate(self, text: str, max_words: int = 300) -> str:
        """Truncate text to max_words to keep prompts small."""
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]) + "..."

    def is_substantive(self, original_post: str, reply: str) -> bool:
        """
        Evaluate whether a reply substantively engages with the original post.

        Args:
            original_post: The parent post text (may contain HTML)
            reply: The student's reply text (may contain HTML)

        Returns:
            True if substantive (or on any error — lean toward granting credit)
        """
        if not self._is_available():
            return True  # fallback: grant credit

        clean_post = self._truncate(self._clean_html(original_post))
        clean_reply = self._truncate(self._clean_html(reply))

        user_prompt = f"ORIGINAL POST:\n{clean_post}\n\nSTUDENT REPLY:\n{clean_reply}"

        try:
            r = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.0,
                        "num_predict": 10,  # only need a few tokens
                    },
                },
                timeout=180,
            )
            r.raise_for_status()

            response_text = r.json().get("message", {}).get("content", "").strip().upper()

            if "NOT SUBSTANTIVE" in response_text:
                return False
            elif "SUBSTANTIVE" in response_text:
                return True
            else:
                # Couldn't parse — lean toward granting credit
                self.logger.warning(
                    f"        ⚠️  LLM returned unparseable response: "
                    f"'{response_text[:50]}' — defaulting to substantive"
                )
                return True

        except Exception as e:
            self.logger.warning(
                f"        ⚠️  LLM check failed ({e}) — defaulting to substantive"
            )
            return True
