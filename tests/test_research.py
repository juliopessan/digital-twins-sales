import sys
import types
from types import SimpleNamespace as NS

from digital_twins.research import ResearchError, research_committee


def _fake_exa(monkeypatch):
    class Exa:
        def __init__(self, api_key): ...

        def answer(self, query, system_prompt=None):
            if "CFO" in query:
                raise RuntimeError("boom")
            role_only = query.startswith("Who is")
            ans = (
                "Name: Jane Doe\n- Joined in 2020 as VP Finance\n- Focused on margin expansion"
                if role_only
                else "- Led the 2022 merger integration\n- Publicly bullish on AI"
            )
            return NS(answer=ans, citations=[NS(url="https://a.com/x"), NS(url="https://a.com/x")])

    monkeypatch.setitem(sys.modules, "exa_py", types.SimpleNamespace(Exa=Exa))


def test_committee_research_discovers_names_and_isolates_failures(monkeypatch):
    _fake_exa(monkeypatch)
    out = research_committee("Acme", [("cto", "CTO", None), ("ceo", "CEO", "John Roe"), ("cfo", "CFO", None)], "k")

    assert out["cto"].name == "Jane Doe" and len(out["cto"].facts) == 2
    assert out["ceo"].name == "John Roe"  # a name the seller typed is never overwritten
    assert out["ceo"].sources == ["https://a.com/x"]  # de-duplicated
    assert isinstance(out["cfo"], ResearchError)  # one failure doesn't sink the batch
