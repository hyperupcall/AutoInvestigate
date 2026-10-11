from orchestrator.sources import as_prompt, citations, parse_atom

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
<entry><id>http://arxiv.org/abs/2305.05904v1</id><published>2023-05-10T00:00:00Z</published>
<title>Revisiting Fully
 Homomorphic Encryption Schemes</title><summary> A survey of FHE. </summary>
<author><name>A. One</name></author><author><name>B. Two</name></author>
<arxiv:primary_category term="cs.CR"/></entry>
</feed>"""


def test_parse_atom_and_prompt():
    p = parse_atom(ATOM)
    assert p == [{"id": "2305.05904", "title": "Revisiting Fully Homomorphic Encryption Schemes", "authors": ["A. One", "B. Two"],
                  "year": "2023", "url": "https://arxiv.org/abs/2305.05904", "category": "cs.CR", "abstract": "A survey of FHE."}]
    assert "[arXiv:2305.05904]" in as_prompt(p) and as_prompt([]) == ""


def test_citations():
    assert citations("see [arXiv:2305.05904] and arXiv 2401.12345, also arXiv:hep-th/0101001") == ["2305.05904", "2401.12345", "hep-th/0101001"]
