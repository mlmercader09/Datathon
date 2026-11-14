"""Ask the small language model for one letter, A to E."""
import math
import urllib.error

from . import calibration
from .config import CONFIG
from .client import post

URL = f"http://127.0.0.1:{CONFIG['LLM_PORT']}/v1/chat/completions"

# Keep the system prompt stable: llama-server caches the start of the prompt,
# so text that never changes is only read once.
SYSTEM = ("You solve multiple-choice math competition problems for school students. "
          "Read the problem and the options, then reply with the letter of the correct option.")


def format_problem(problem, sees_image=False):
    lines = [problem["text"].strip()]
    options = problem.get("options") or {}
    for letter in "ABCDE":
        if letter in options:
            lines.append(f"{letter}) {options[letter]}")
    if not options:
        lines.append("(The options are in the picture.)" if sees_image else
                     "(The options are in a picture that you can't see. Pick the most likely letter.)")
    return "\n".join(lines)


def build_messages(problem, examples=(), image_b64=None):
    """image_b64 is a PNG as base64 text. Only a server started with --mmproj can see it."""
    messages = [{"role": "system", "content": SYSTEM}]
    for ex in examples:  # solved problems retrieved with RAG, if any
        messages.append({"role": "user", "content": format_problem(ex) + "\nAnswer:"})
        messages.append({"role": "assistant", "content": ex["label"]})
    text = format_problem(problem, sees_image=bool(image_b64)) + "\nAnswer:"
    if image_b64:
        content = [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + image_b64}},
                   {"type": "text", "text": text}]
    else:
        content = text
    messages.append({"role": "user", "content": content})
    return messages


def letter_logprobs(response):
    """{letter: log-probability} for the answer token, or None if the server didn't send them."""
    try:
        top = response["choices"][0]["logprobs"]["content"][0]["top_logprobs"]
    except (KeyError, IndexError, TypeError):
        return None
    probs = {}
    for item in top:
        token = str(item.get("token", "")).strip()
        if len(token) == 1 and token in calibration.LETTERS:  # "B" and " B" are the same answer
            probs[token] = probs.get(token, 0.0) + math.exp(item["logprob"])
    if len(probs) < 2:
        return None
    floor = min(probs.values()) / 10  # a letter outside the top tokens is less likely than all of these
    return {l: math.log(probs.get(l, floor)) for l in calibration.LETTERS}


def ask(problem, examples=(), timeout=60, image_b64=None, url=URL):
    """Return (letter, logprobs, timings). The grammar makes any other output impossible."""
    payload = {
        "messages": build_messages(problem, examples, image_b64),
        "grammar": "root ::= [A-E]",
        "max_tokens": 1,
        "temperature": 0,
        "seed": int(CONFIG["SEED"]),
        "cache_prompt": True,
        "logprobs": True,
        "top_logprobs": 20,
    }
    try:
        response = post(url, payload, timeout=timeout)
    except urllib.error.HTTPError:
        # A server that refuses logprobs still answers the plain request
        del payload["logprobs"], payload["top_logprobs"]
        response = post(url, payload, timeout=timeout)
    letter = response["choices"][0]["message"]["content"].strip()
    return letter, letter_logprobs(response), response.get("timings", {})


def answer_letter(problem, examples=(), timeout=60, image_b64=None, url=URL):
    """Return (letter, timings), with the letter bias corrected if copilot/calibration.json exists."""
    letter, logprobs, timings = ask(problem, examples, timeout, image_b64, url)
    letter = calibration.choose(letter, logprobs, has_options=bool(problem.get("options")),
                                rag=bool(examples))
    return letter, timings
