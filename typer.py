"""Lexical typing: turns the email into a small set of symbolic types.

This is the 'weak state-action translator' from the meeting: cheap, deterministic,
and incomplete on purpose. Intention-based injections written as normal requests
will not be flagged; the rulesets and the floor have to bound those.
"""
import re

from env import CONTACTS

INSTRUCTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior) instructions",
    r"system (note|message|prompt)",
    r"\byou must\b",
    r"\bimportant\b\s*[:!]",
    r"\binstead\b",
    r"\bforward\b",
    r"send (the )?contents of",
    r"before replying",
]
_INSTR = re.compile("|".join(INSTRUCTION_PATTERNS), re.I)
_FILE = re.compile(r"\b[\w\-]+\.txt\b", re.I)
_ADDR = re.compile(r"[\w.\-]+@[\w.\-]+\w")


def type_email(email: dict) -> set:
    types = set()
    sender = email["from"]
    contact = CONTACTS.get(sender)
    if contact is None:
        types.add("unknown_sender")
    else:
        types.add(f"{contact['kind']}_sender")       # internal_sender / external_sender
    body = email["body"]
    if _INSTR.search(body):
        types.add("contains_instruction")
    if _FILE.search(body):
        types.add("mentions_file")
    if any(a != sender for a in _ADDR.findall(body)):
        types.add("mentions_other_address")
    return types
