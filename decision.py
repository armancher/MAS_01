"""The non-generative decision model. It answers one fixed question per proposed
action by scoring the three answers allow / escalate / block. It never writes text.
The gateway then takes the highest-scored answer that the ruleset still permits.

  SenderMatchStub  placeholder until Jev or a classifier is wired in
  AlwaysPermissive worst case: the model is fully deceived (prefers allow > escalate > block)
  Jev              TODO: TypeSafe Jev choice question with options allow/escalate/block
"""
ANSWERS = ("allow", "escalate", "block")


class DecisionModel:
    name = "base"

    def scores(self, question: str, state: dict) -> dict:
        """Returns a score per answer, e.g. {"allow": 0.7, "escalate": 0.2, "block": 0.1}."""
        raise NotImplementedError


class SenderMatchStub(DecisionModel):
    """Trivial stand-in: favours allow when replying to the sender, block otherwise.
    Not a result: real numbers need Jev or a trained classifier."""
    name = "stub"

    def scores(self, question, state):
        if state["recipient"] == state["sender"]:
            return {"allow": 0.7, "escalate": 0.2, "block": 0.1}
        return {"allow": 0.1, "escalate": 0.2, "block": 0.7}


class AlwaysPermissive(DecisionModel):
    name = "fooled"

    def scores(self, question, state):
        return {"allow": 0.98, "escalate": 0.015, "block": 0.005}


class Jev(DecisionModel):
    name = "jev"

    def scores(self, question, state):
        raise NotImplementedError("call Jev with a choice question over ANSWERS")
