"""The phone handbook artifact is generated from the same data as the dashboard."""
import html
import re

from scripts.build_artifact import OUTPUT, build, render, rich
from scripts.project import Project


def test_committed_handbook_matches_data_sources():
    assert build(Project(), check=True) is False


def test_handbook_covers_every_topic_prompt_and_voice():
    project = Project()
    page = render(project)
    brand = project.brand()
    for topic in project.topics():
        assert f'id="t{topic["id"]}"' in page
        for test in topic["tests"]:
            assert html.escape(test["text"], quote=True) in page, (topic["id"], test["id"])
        for title in topic["titles"]:
            assert html.escape(title, quote=True) in page
    assert "{{opener}}" not in page and "{{closer}}" not in page
    assert html.escape(brand["opener"], quote=True) in page
    assert "第01期截图放好了" in page and "第12期复核好了" in page


def test_handbook_loads_nothing_but_google_fonts():
    page = render(Project())
    assert "<script src" not in page
    hosts = set(re.findall(r'(?:href|src)="https?://([^/"]+)', page))
    assert hosts <= {"fonts.googleapis.com", "fonts.gstatic.com"}


def test_topic_snippets_keep_only_bold_and_breaks():
    assert rich("<b>答案：</b>5段<br><img src=x onerror=alert(1)>") == "<b>答案：</b>5段<br>&lt;img src=x onerror=alert(1)&gt;"
    assert rich("A:A,&quot;&lt;&quot;") == "A:A,&quot;&lt;&quot;"


def test_build_writes_into_the_project_copy(project):
    assert build(project) is True
    target = project.root / OUTPUT
    assert target.is_file() and "科技试吃员 选题手册" in target.read_text(encoding="utf-8")
    assert build(project, check=True) is False
