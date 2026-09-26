"""Converts Chromium's named-destination links into direct page links.

GoodNotes, Notability and other iPad apps all follow plain "go to page"
links; named destinations are less reliably supported. Run after build.mjs:

    python3 source/fix_links.py product/Planner-2027-Light.pdf product/Planner-2027-Dark.pdf
"""
import sys

import pymupdf


def fix(path: str) -> None:
    doc = pymupdf.open(path)
    converted = 0
    for page in doc:
        for link in page.get_links():
            target = link.get("page", -1)
            if link.get("kind") == pymupdf.LINK_NAMED and target >= 0:
                page.delete_link(link)
                page.insert_link({
                    "kind": pymupdf.LINK_GOTO,
                    "from": link["from"],
                    "page": target,
                    "to": pymupdf.Point(0, 0),
                    "zoom": 0,
                })
                converted += 1
    doc.save(path + ".tmp", garbage=3, deflate=True)
    doc.close()
    import os
    os.replace(path + ".tmp", path)
    print(f"{path}: converted {converted} links")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        fix(p)
